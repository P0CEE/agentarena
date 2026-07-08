"""AgentRunner : le pont entre la chaîne et l'agent.

Observe le state du node à chaque bloc et joue le rôle assigné par la sortition
au bon moment : build -> commit -> reveal quand builder, judge -> commit des
notes -> reveal quand juge. Les appels LLM tournent en tâches de fond pour ne
jamais bloquer le consensus ; un échec d'agent = pas de tx = no-show, le
protocole s'en charge (jail avec grâce).

Le runner ne dépend pas du package node : il duck-type l'engine
(.state, .height, .mempool, .handle_tx).
"""

import asyncio
import secrets as _secrets
from collections.abc import Callable, Coroutine

from arena_chain.arena import revealed_builders, scores_commit, solution_commit
from arena_chain.errors import InvalidTx
from arena_chain.params import MAX_CONTENT_LEN, SCALE
from arena_chain.split import split
from arena_chain.tx import make_tx
from arena_chain.wallet import Wallet

from arena_agents.base import Agent


def normalize_scores(builders: list[str], raw: dict[str, int]) -> dict[str, int]:
    """Poids relatifs bruts de l'agent -> vecteur protocolaire (somme == SCALE)."""
    weights = [max(0, int(raw.get(builder, 0))) for builder in builders]
    if sum(weights) == 0:
        weights = [1] * len(builders)
    return dict(zip(builders, split(SCALE, weights)))


class AgentRunner:
    def __init__(self, engine, wallet: Wallet, agent: Agent, poll_s: float = 0.2) -> None:
        self.engine = engine
        self.wallet = wallet
        self.agent = agent
        self.poll_s = poll_s
        self.secrets: dict[str, dict] = {}  # "sol|task" / "scores|task" -> {..., "salt"}
        self.started: set[str] = set()  # actions deja lancees (une seule fois chacune)
        self._background: set[asyncio.Task] = set()
        self._send_lock = asyncio.Lock()

    async def run(self) -> None:
        while True:
            try:
                await self.step()
            except Exception:
                pass  # le runner ne doit jamais tuer le node
            await asyncio.sleep(self.poll_s)

    async def step(self) -> None:
        """Un tour d'observation : lance les actions dues à cette hauteur."""
        me = self.wallet.address
        state = self.engine.state
        height = self.engine.height
        for task_id, task in sorted(state.data["tasks"].items()):
            if task["state"] == "OPEN":
                if me in task["builders"] and height < task["submit_until"]:
                    self._once(f"build|{task_id}", lambda t=task_id, b=task["brief"]:
                               self._build(t, b))
            elif task["state"] == "SCORING":
                if me in task["builders"] and height < task["reveal_until"]:
                    submission = state.data["submissions"].get(f"{task_id}|{me}")
                    if (
                        submission is not None
                        and submission["status"] == "COMMITTED"
                        and f"sol|{task_id}" in self.secrets
                    ):
                        self._once(f"reveal_sol|{task_id}", lambda t=task_id:
                                   self._reveal_solution(t))
                if me in task["judges"]:
                    if (
                        task["reveal_until"] <= height < task["commit_score_until"]
                        and f"{task_id}|{me}" not in state.data["scores"]
                    ):
                        self._once(f"judge|{task_id}", lambda t=task_id, b=task["brief"]:
                                   self._judge(t, b))
                    record = state.data["scores"].get(f"{task_id}|{me}")
                    if (
                        record is not None
                        and record["status"] == "COMMITTED"
                        and task["commit_score_until"] <= height < task["reveal_score_until"]
                        and f"scores|{task_id}" in self.secrets
                    ):
                        self._once(f"reveal_scores|{task_id}", lambda t=task_id:
                                   self._reveal_scores(t))

    async def drain(self) -> None:
        """Attend la fin des tâches de fond (tests et arrêts propres)."""
        while self._background:
            await asyncio.gather(*list(self._background), return_exceptions=True)

    # --- actions ---

    async def _build(self, task_id: str, brief: str) -> None:
        try:
            content = await self.agent.build(task_id, brief)
        except Exception:
            return  # no-show : le protocole jail avec grace
        content = str(content)[:MAX_CONTENT_LEN] or "(vide)"
        salt = _secrets.token_hex(16)
        self.secrets[f"sol|{task_id}"] = {"content": content, "salt": salt}
        commit = solution_commit(task_id, self.wallet.address, content, salt)
        await self._send({"type": "submit_solution", "task": task_id, "commit": commit})

    async def _reveal_solution(self, task_id: str) -> None:
        secret = self.secrets[f"sol|{task_id}"]
        await self._send(
            {
                "type": "reveal_solution",
                "task": task_id,
                "content": secret["content"],
                "salt": secret["salt"],
            }
        )

    async def _judge(self, task_id: str, brief: str) -> None:
        state = self.engine.state
        builders = revealed_builders(state, task_id)
        contents = {
            builder: state.data["submissions"][f"{task_id}|{builder}"]["content"]
            for builder in builders
        }
        if not contents:
            return
        try:
            raw = await self.agent.judge(task_id, brief, contents)
        except Exception:
            return  # no-show
        scores = normalize_scores(builders, raw)
        salt = _secrets.token_hex(16)
        self.secrets[f"scores|{task_id}"] = {"scores": scores, "salt": salt}
        commit = scores_commit(task_id, self.wallet.address, scores, salt)
        await self._send({"type": "commit_scores", "task": task_id, "commit": commit})

    async def _reveal_scores(self, task_id: str) -> None:
        secret = self.secrets[f"scores|{task_id}"]
        await self._send(
            {
                "type": "reveal_scores",
                "task": task_id,
                "scores": secret["scores"],
                "salt": secret["salt"],
            }
        )

    # --- plomberie ---

    def _once(self, key: str, factory: Callable[[], Coroutine]) -> None:
        if key in self.started:
            return
        self.started.add(key)
        task = asyncio.create_task(factory())
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    def _next_nonce(self) -> int:
        account = self.engine.state.data["accounts"].get(self.wallet.address)
        chain_nonce = account["nonce"] if account else 0
        pending = sum(
            1 for tx in self.engine.mempool.values() if tx["sender"] == self.wallet.address
        )
        return chain_nonce + pending

    async def _send(self, payload: dict) -> None:
        async with self._send_lock:
            tx = make_tx(self.wallet, self._next_nonce(), payload)
            try:
                await self.engine.handle_tx(tx)
            except InvalidTx:
                pass  # tx devenue invalide (fenetre fermee) : no-show assume
