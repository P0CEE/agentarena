import pytest

from arena_chain.block import block_hash, verify_block
from arena_chain.errors import InvalidBlock
from arena_chain.genesis import make_genesis
from arena_chain.state import seal_block
from arena_chain.tx import make_tx
from arena_chain.wallet import Wallet

ALICE = Wallet.from_seed(b"a" * 32)
BOB = Wallet.from_seed(b"b" * 32)
ALLOCATIONS = {ALICE.address: 10_000, BOB.address: 10_000}


def _chain_with_one_block() -> tuple[dict, dict]:
    state, genesis = make_genesis(ALLOCATIONS)
    tx = make_tx(ALICE, 0, {"type": "transfer", "to": BOB.address, "amount": 100})
    _, block1 = seal_block(state, genesis["header"], [tx], proposer=ALICE.address, round_=0)
    return genesis, block1


def test_genesis_deterministe() -> None:
    _, g1 = make_genesis(ALLOCATIONS)
    _, g2 = make_genesis(dict(reversed(list(ALLOCATIONS.items()))))
    assert block_hash(g1["header"]) == block_hash(g2["header"])


def test_bloc_valide_passe() -> None:
    genesis, block1 = _chain_with_one_block()
    verify_block(block1, genesis["header"])


def test_alterer_une_tx_invalide_le_bloc() -> None:
    # La signature de la tx casse en premier : le bloc entier est rejete.
    genesis, block1 = _chain_with_one_block()
    block1["txs"][0]["payload"]["amount"] = 9_999
    with pytest.raises(InvalidBlock, match="tx invalide"):
        verify_block(block1, genesis["header"])


def test_tx_root_falsifie_rejete() -> None:
    genesis, block1 = _chain_with_one_block()
    block1["header"]["tx_root"] = "f" * 64
    with pytest.raises(InvalidBlock, match="tx_root"):
        verify_block(block1, genesis["header"])


def test_alterer_le_bloc_precedent_casse_le_chainage() -> None:
    genesis, block1 = _chain_with_one_block()
    genesis["header"]["state_root"] = "0" * 64  # falsifie l'histoire
    with pytest.raises(InvalidBlock, match="prev_hash"):
        verify_block(block1, genesis["header"])


def test_hauteur_incoherente_rejetee() -> None:
    genesis, block1 = _chain_with_one_block()
    block1["header"]["height"] = 5
    with pytest.raises(InvalidBlock):
        verify_block(block1, genesis["header"])


def test_tx_dupliquee_rejetee() -> None:
    genesis, block1 = _chain_with_one_block()
    block1["txs"] = block1["txs"] * 2
    with pytest.raises(InvalidBlock, match="canonique"):
        verify_block(block1, genesis["header"])


def test_hash_du_header_seul() -> None:
    # Ajouter des donnees hors header (futurs votes) ne change pas le hash.
    genesis, block1 = _chain_with_one_block()
    before = block_hash(block1["header"])
    block1["votes"] = {"quelqu'un": "signature"}
    assert block_hash(block1["header"]) == before
