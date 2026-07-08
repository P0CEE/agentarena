"""Coeur de la chaine AgentArena : tout ce qui touche au state_root vit ici."""

from arena_chain.block import block_hash, make_block, make_header, tx_root, verify_block
from arena_chain.canonical import canonical, tagged_hash
from arena_chain.errors import ChainError, InvalidBlock, InvalidTx
from arena_chain.genesis import make_genesis
from arena_chain.sortition import select_builders, sortition_seed
from arena_chain.split import split
from arena_chain.state import State, apply_block, seal_block
from arena_chain.tx import make_tx, txid, verify_tx
from arena_chain.wallet import Wallet, address_of, verify_signature
from arena_chain.yuma import yuma_consensus

__version__ = "0.1.0"

__all__ = [
    "ChainError",
    "InvalidBlock",
    "InvalidTx",
    "State",
    "Wallet",
    "address_of",
    "apply_block",
    "block_hash",
    "canonical",
    "make_block",
    "make_genesis",
    "make_header",
    "make_tx",
    "seal_block",
    "select_builders",
    "sortition_seed",
    "split",
    "tagged_hash",
    "tx_root",
    "txid",
    "verify_block",
    "verify_signature",
    "verify_tx",
    "yuma_consensus",
]
