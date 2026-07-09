"""Bloc = header + transactions.

block_hash = hash du header SEUL, sans les signatures/votes (les votes portent
sur ce hash : les inclure créerait une dépendance circulaire). Les tx d'un bloc
sont en ordre canonique strict (txid croissant), rejoué à l'identique partout.
"""

from arena_chain.canonical import tagged_hash
from arena_chain.errors import InvalidBlock, InvalidTx
from arena_chain.tx import verify_tx

BLOCK_TAG = "agentarena/block/v1"
TXROOT_TAG = "agentarena/txroot/v1"
GENESIS_PREV = "0" * 64

HEADER_FIELDS = {"height", "prev_hash", "proposer", "round", "tx_root", "state_root", "timestamp"}


def tx_root(txids: list[str]) -> str:
    return tagged_hash(TXROOT_TAG, txids)


def block_hash(header: dict) -> str:
    return tagged_hash(BLOCK_TAG, header)


def make_header(
    height: int,
    prev_hash: str,
    proposer: str,
    round_: int,
    tx_root_: str,
    state_root: str,
    timestamp: int,
) -> dict:
    return {
        "height": height,
        "prev_hash": prev_hash,
        "proposer": proposer,
        "round": round_,
        "tx_root": tx_root_,
        "state_root": state_root,
        "timestamp": timestamp,
    }


def make_block(header: dict, txs: list[dict]) -> dict:
    return {"header": header, "txs": txs}


def verify_block(block: dict, prev_header: dict) -> None:
    """Vérifie la structure, le chaînage et l'ordre canonique des tx.

    Le state_root est vérifié à l'application (apply_block), pas ici.
    """
    if not isinstance(block, dict) or set(block) != {"header", "txs"}:
        raise InvalidBlock("structure de bloc invalide")
    header = block["header"]
    if not isinstance(header, dict) or set(header) != HEADER_FIELDS:
        raise InvalidBlock("header invalide")
    if header["height"] != prev_header["height"] + 1:
        raise InvalidBlock(f"hauteur {header['height']} != {prev_header['height'] + 1}")
    if header["prev_hash"] != block_hash(prev_header):
        raise InvalidBlock("prev_hash ne chaine pas sur le bloc precedent")
    # Monotonie seule, jamais l'horloge locale : le replay/catch-up reste deterministe.
    if header["timestamp"] <= prev_header["timestamp"]:
        raise InvalidBlock("timestamp non strictement croissant")
    try:
        ids = [verify_tx(tx) for tx in block["txs"]]
    except InvalidTx as exc:
        raise InvalidBlock(f"tx invalide dans le bloc: {exc}") from exc
    if ids != sorted(set(ids)):
        raise InvalidBlock("tx non triees par txid (ordre canonique) ou dupliquees")
    if header["tx_root"] != tx_root(ids):
        raise InvalidBlock("tx_root ne correspond pas aux tx du bloc")
