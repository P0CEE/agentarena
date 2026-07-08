"""State account-based, entièrement en entiers.

Le state est un unique dict imbriqué à clés str : son root est le hash canonique
de ce dict, identique sur tous les nodes. Règle des handlers : valider AVANT de
muter (une tx rejetée ne laisse aucun effet de bord).

Les handlers de manche (arena.py) et les hooks de fin de bloc s'enregistrent
dans HANDLERS et BLOCK_END_HOOKS ; l'application d'un bloc est :
begin_block -> txs en ordre canonique -> hooks -> height -> root.
"""

import copy
from collections.abc import Callable

from arena_chain.block import block_hash, make_block, make_header, tx_root, verify_block
from arena_chain.canonical import tagged_hash
from arena_chain.errors import InvalidBlock, InvalidTx
from arena_chain.params import MIN_STAKE, params_hash
from arena_chain.tx import txid, verify_tx

STATE_TAG = "agentarena/state/v1"


class State:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.ctx_height: int | None = None  # hauteur du bloc en cours d'application
        self.ctx_prev_hash: str | None = None  # hash du dernier bloc finalise

    @classmethod
    def from_allocations(
        cls, allocations: dict[str, int], agents: dict[str, int] | None = None
    ) -> "State":
        """State initial du genesis : des soldes, les paramètres, et les agents
        pré-enregistrés (le set de validateurs initial, stakes égaux au genesis)."""
        accounts = {
            addr: {"balance": amount, "nonce": 0} for addr, amount in sorted(allocations.items())
        }
        agents = agents or {}
        return cls(
            {
                "accounts": accounts,
                "agents": {
                    addr: {"jailed_until": 0, "offenses": 0, "last_offense": 0}
                    for addr in sorted(agents)
                },
                "stakes": {
                    addr: {"free": stake, "locked": 0} for addr, stake in sorted(agents.items())
                },
                "tasks": {},
                "submissions": {},
                "scores": {},
                "bonds": {},
                "double_signed": {},
                "treasury": 0,
                "params": params_hash(),
                "height": 0,
            }
        )

    def clone(self) -> "State":
        return State(copy.deepcopy(self.data))

    def root(self) -> str:
        return tagged_hash(STATE_TAG, self.data)

    @property
    def height(self) -> int:
        return self.data["height"]

    def begin_block(self, height: int, prev_hash: str) -> None:
        self.ctx_height = height
        self.ctx_prev_hash = prev_hash

    def account(self, addr: str) -> dict:
        return self.data["accounts"].setdefault(addr, {"balance": 0, "nonce": 0})

    def balance(self, addr: str) -> int:
        return self.data["accounts"].get(addr, {"balance": 0})["balance"]

    def credit(self, addr: str, amount: int) -> None:
        self.account(addr)["balance"] += amount

    def debit(self, addr: str, amount: int) -> None:
        account = self.account(addr)
        if account["balance"] < amount:
            raise InvalidTx(f"solde insuffisant pour {addr}")
        account["balance"] -= amount

    def apply_tx(self, tx: dict) -> str:
        """Vérifie et applique une tx. Retourne son txid."""
        tid = verify_tx(tx)
        account = self.account(tx["sender"])
        if tx["nonce"] != account["nonce"]:
            raise InvalidTx(f"nonce {tx['nonce']} != attendu {account['nonce']} (rejeu ?)")
        handler = HANDLERS.get(tx["payload"]["type"])
        if handler is None:
            raise InvalidTx(f"type de tx inconnu: {tx['payload']['type']}")
        handler(self, tx)
        account["nonce"] += 1
        return tid


def _require_int(payload: dict, field: str) -> int:
    value = payload.get(field)
    if type(value) is not int:
        raise InvalidTx(f"champ {field} entier requis")
    return value


def _apply_transfer(state: State, tx: dict) -> None:
    payload = tx["payload"]
    amount = _require_int(payload, "amount")
    to = payload.get("to")
    if not isinstance(to, str) or not to:
        raise InvalidTx("destinataire invalide")
    if amount <= 0:
        raise InvalidTx("montant non positif")
    state.debit(tx["sender"], amount)
    state.credit(to, amount)


def _apply_register_agent(state: State, tx: dict) -> None:
    """Le stake est REELLEMENT debite du solde et verrouille (correctif audit)."""
    sender = tx["sender"]
    stake = _require_int(tx["payload"], "stake")
    if stake < MIN_STAKE:
        raise InvalidTx(f"stake {stake} < MIN_STAKE {MIN_STAKE}")
    if sender in state.data["agents"]:
        raise InvalidTx("agent deja enregistre")
    if state.balance(sender) < stake:
        raise InvalidTx("solde insuffisant pour le stake")
    state.debit(sender, stake)
    state.data["stakes"][sender] = {"free": stake, "locked": 0}
    state.data["agents"][sender] = {"jailed_until": 0, "offenses": 0, "last_offense": 0}


Handler = Callable[[State, dict], None]

HANDLERS: dict[str, Handler] = {
    "transfer": _apply_transfer,
    "register_agent": _apply_register_agent,
}

# Hooks executes en fin de bloc (transitions de manche, jails, reglements).
# Enregistres par arena.py ; rejoues a l'identique par tous les nodes.
BLOCK_END_HOOKS: list[Callable[[State], None]] = []


def _run_block(state: State, height: int, prev_hash: str, ordered_txs: list[dict]) -> list[str]:
    state.begin_block(height, prev_hash)
    ids = [state.apply_tx(tx) for tx in ordered_txs]
    for hook in BLOCK_END_HOOKS:
        hook(state)
    state.data["height"] = height
    return ids


def seal_block(
    state: State, prev_header: dict, txs: list[dict], proposer: str, round_: int
) -> tuple[State, dict]:
    """Côté proposer : applique les tx sur un clone et scelle le bloc.

    Le state d'origine n'est pas modifié ; le nouveau state et le bloc sont
    retournés ensemble.
    """
    work = state.clone()
    ordered = sorted(txs, key=txid)
    prev_hash = block_hash(prev_header)
    height = prev_header["height"] + 1
    ids = _run_block(work, height, prev_hash, ordered)
    header = make_header(height, prev_hash, proposer, round_, tx_root(ids), work.root())
    return work, make_block(header, ordered)


def apply_block(state: State, prev_header: dict, block: dict) -> None:
    """Côté validateur : vérifie puis applique un bloc, state_root compris."""
    verify_block(block, prev_header)
    header = block["header"]
    _run_block(state, header["height"], header["prev_hash"], block["txs"])
    if state.root() != header["state_root"]:
        raise InvalidBlock("state_root divergent apres application (bloc ou state corrompu)")
