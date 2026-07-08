"""Moteur de consensus d'un node : propose, vote, finalise, rattrape.

Boucle par hauteur : le proposer (round-robin pondéré stake) scelle un bloc
depuis le mempool, les validateurs le vérifient en l'appliquant sur un clone
puis votent ; au quorum (>2/3 du stake) le bloc est final — one-block finality,
pas de fork. Pacemaker : au timeout local chacun émet un message Timeout ; un
quorum de timeouts fait passer au round suivant (compteur logique, pas
d'horloge partagée). Si moins de 2/3 du stake répond, la chaîne s'arrête :
comportement BFT correct (la sûreté avant la liveness).
"""

import asyncio
import time

from arena_chain.block import block_hash
from arena_chain.consensus import (
    make_timeout,
    make_vote,
    proposer_for,
    quorum,
    validators_of,
    verify_qc,
    verify_timeout,
    verify_vote,
)
from arena_chain.errors import ChainError, InvalidBlock, InvalidTx
from arena_chain.state import State, apply_block, seal_block
from arena_chain.tx import txid, verify_tx
from arena_chain.wallet import Wallet

from arena_node.transport import Transport


class Engine:
    def __init__(
        self,
        wallet: Wallet,
        state: State,
        genesis_block: dict,
        peers: list[str],
        transport: Transport,
        block_time: float = 2.0,
        round_timeout: float = 8.0,
    ) -> None:
        self.wallet = wallet
        self.state = state
        self.last_header = genesis_block["header"]
        self.blocks: list[dict] = [{"block": genesis_block, "qc": {}}]
        self.peers = peers
        self.transport = transport
        self.block_time = block_time
        self.round_timeout = round_timeout

        self.round = 0
        self.mempool: dict[str, dict] = {}
        self.seen_txs: set[str] = set()
        self.proposals: dict[str, dict] = {}  # "h|r" -> bloc propose
        self.votes: dict[str, dict[str, dict]] = {}  # "h|r|hash" -> voter -> vote
        self.timeouts: dict[str, dict[str, dict]] = {}  # "h|r" -> voter -> timeout
        self.voted: set[str] = set()  # "h|r" deja votes par CE node (anti double-sign)
        self.fired: set[str] = set()  # timeouts deja emis par CE node
        self.behind = False
        self.subscribers: list[asyncio.Queue] = []
        self._last_progress = time.monotonic()

    # --- lectures ---

    @property
    def height(self) -> int:
        return self.last_header["height"]

    @property
    def next_height(self) -> int:
        return self.height + 1

    def validators(self) -> dict[str, int]:
        return validators_of(self.state)

    def is_proposer(self) -> bool:
        return (
            proposer_for(self.validators(), self.next_height + self.round)
            == self.wallet.address
        )

    # --- evenements (SSE) ---

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self.subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self.subscribers:
            self.subscribers.remove(queue)

    def _publish(self, event: dict) -> None:
        for queue in self.subscribers:
            queue.put_nowait(event)

    # --- reception des messages ---

    async def handle_tx(self, tx: dict) -> str:
        tid = verify_tx(tx)  # validation isolee ; le nonce/solde est revalide au seal
        if tid in self.seen_txs:
            return tid
        self.seen_txs.add(tid)
        self.mempool[tid] = tx
        await self._broadcast("/tx", tx)
        return tid

    async def handle_proposal(self, block: dict) -> None:
        header = block["header"]
        height, round_ = header["height"], header["round"]
        if height > self.next_height:
            self.behind = True
            return
        if height != self.next_height:
            return
        key = f"{height}|{round_}"
        if key in self.proposals:
            return  # premier arrive, premier garde
        validators = self.validators()
        if header["proposer"] != proposer_for(validators, height + round_):
            return  # proposer illegitime pour ce (hauteur, round)
        work = self.state.clone()
        try:
            apply_block(work, self.last_header, block)  # verification complete sur clone
        except ChainError:
            return
        self.proposals[key] = block
        if key not in self.voted:
            self.voted.add(key)  # un seul vote par (hauteur, round) : anti double-sign
            vote = make_vote(self.wallet, height, round_, block_hash(header))
            await self._broadcast("/consensus/vote", vote)
            await self.handle_vote(vote)
        else:
            await self._try_finalize(height, round_, block_hash(header))

    async def handle_vote(self, vote: dict) -> None:
        try:
            voter = verify_vote(vote)
        except InvalidTx:
            return
        if vote["height"] > self.next_height:
            self.behind = True
        if voter not in self.validators():
            return
        key = f"{vote['height']}|{vote['round']}|{vote['block_hash']}"
        self.votes.setdefault(key, {}).setdefault(voter, vote)
        await self._try_finalize(vote["height"], vote["round"], vote["block_hash"])

    async def handle_timeout(self, message: dict) -> None:
        try:
            voter = verify_timeout(message)
        except InvalidTx:
            return
        if voter not in self.validators():
            return
        key = f"{message['height']}|{message['round']}"
        self.timeouts.setdefault(key, {}).setdefault(voter, message)
        if (
            message["height"] == self.next_height
            and message["round"] == self.round
            and quorum(self.validators(), self.timeouts[key])
        ):
            self.round += 1  # compteur logique : avance par quorum, pas par horloge
            self._last_progress = time.monotonic()

    # --- actions ---

    async def propose_if_leader(self) -> None:
        if not self.is_proposer():
            return
        key = f"{self.next_height}|{self.round}"
        if key in self.proposals:
            return
        if time.monotonic() - self._last_progress < self.block_time:
            return
        _, block = seal_block(
            self.state, self.last_header, self._select_txs(), self.wallet.address, self.round
        )
        await self._broadcast("/consensus/proposal", block)
        await self.handle_proposal(block)

    def _select_txs(self) -> list[dict]:
        """Revalide le mempool sur un clone : une tx valide hier peut ne plus l'être."""
        work = self.state.clone()
        work.begin_block(self.next_height, block_hash(self.last_header))
        kept = []
        for tx in sorted(self.mempool.values(), key=txid):
            try:
                work.apply_tx(tx)
            except InvalidTx:
                continue  # reste en mempool (ex. nonce futur), retentee plus tard
            kept.append(tx)
        return kept

    async def fire_timeout(self) -> None:
        key = f"{self.next_height}|{self.round}"
        if key in self.fired:
            return
        self.fired.add(key)
        message = make_timeout(self.wallet, self.next_height, self.round)
        await self._broadcast("/consensus/timeout", message)
        await self.handle_timeout(message)

    async def _try_finalize(self, height: int, round_: int, hash_: str) -> None:
        if height != self.next_height:
            return
        block = self.proposals.get(f"{height}|{round_}")
        if block is None or block_hash(block["header"]) != hash_:
            return
        votes = self.votes.get(f"{height}|{round_}|{hash_}", {})
        if not quorum(self.validators(), votes):
            return
        self._finalize(block, dict(sorted(votes.items())))

    def _finalize(self, block: dict, qc: dict) -> None:
        tasks_before = {tid: t["state"] for tid, t in self.state.data["tasks"].items()}
        apply_block(self.state, self.last_header, block)
        self.last_header = block["header"]
        self.blocks.append({"block": block, "qc": qc})
        self.round = 0
        self.proposals.clear()
        self.votes.clear()
        self.timeouts.clear()
        self._last_progress = time.monotonic()
        accounts = self.state.data["accounts"]
        self.mempool = {
            tid: tx
            for tid, tx in self.mempool.items()
            if tx["nonce"] >= accounts.get(tx["sender"], {"nonce": 0})["nonce"]
        }  # purge les tx incluses et les nonces perimes
        self._publish(
            {"type": "block", "height": self.height, "hash": block_hash(block["header"]),
             "txs": len(block["txs"])}
        )
        for tid, task in self.state.data["tasks"].items():
            if tasks_before.get(tid) != task["state"]:
                self._publish({"type": "task", "task": tid, "state": task["state"]})

    # --- catch-up ---

    async def sync(self) -> None:
        """Rattrape la chaîne depuis un peer, en validant chaque bloc ET son QC."""
        for peer in self.peers:
            try:
                batch = await self.transport.fetch_blocks(peer, self.next_height)
            except Exception:
                continue
            for entry in batch:
                block = entry["block"]
                header = block["header"]
                try:
                    verify_qc(self.validators(), header, block_hash(header), entry["qc"])
                    self._finalize(block, entry["qc"])
                except ChainError:
                    break  # peer menteur : on ne lui fait pas confiance
            if not batch:
                continue
            return

    # --- boucle principale ---

    async def run(self) -> None:
        while True:
            try:
                if self.behind:
                    self.behind = False
                    await self.sync()
                await self.propose_if_leader()
                if time.monotonic() - self._last_progress > self.round_timeout:
                    await self.fire_timeout()
            except (ChainError, InvalidBlock):
                pass
            await asyncio.sleep(0.05)

    async def _broadcast(self, path: str, payload: dict) -> None:
        await asyncio.gather(
            *(self.transport.send(peer, path, payload) for peer in self.peers),
            return_exceptions=True,
        )
