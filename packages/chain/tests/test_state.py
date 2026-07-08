import pytest

from arena_chain.errors import InvalidBlock, InvalidTx
from arena_chain.genesis import make_genesis
from arena_chain.params import MIN_STAKE
from arena_chain.state import apply_block, seal_block
from arena_chain.tx import make_tx
from arena_chain.wallet import Wallet

ALICE = Wallet.from_seed(b"a" * 32)
BOB = Wallet.from_seed(b"b" * 32)
ALLOCATIONS = {ALICE.address: 10_000, BOB.address: 10_000}


def _transfer(nonce: int, amount: int) -> dict:
    return make_tx(ALICE, nonce, {"type": "transfer", "to": BOB.address, "amount": amount})


def test_transfer() -> None:
    state, _ = make_genesis(ALLOCATIONS)
    state.apply_tx(_transfer(0, 100))
    assert state.balance(ALICE.address) == 9_900
    assert state.balance(BOB.address) == 10_100
    assert state.account(ALICE.address)["nonce"] == 1


def test_rejeu_rejete() -> None:
    state, _ = make_genesis(ALLOCATIONS)
    tx = _transfer(0, 100)
    state.apply_tx(tx)
    with pytest.raises(InvalidTx, match="nonce"):
        state.apply_tx(tx)


def test_solde_insuffisant_sans_effet_de_bord() -> None:
    state, _ = make_genesis(ALLOCATIONS)
    root = state.root()
    with pytest.raises(InvalidTx, match="insuffisant"):
        state.apply_tx(_transfer(0, 999_999))
    assert state.root() == root  # une tx rejetee ne laisse aucune trace


def test_montant_negatif_rejete() -> None:
    state, _ = make_genesis(ALLOCATIONS)
    with pytest.raises(InvalidTx):
        state.apply_tx(_transfer(0, -5))


def test_register_agent_debite_le_stake() -> None:
    # LE correctif audit : le stake sort reellement du solde.
    state, _ = make_genesis(ALLOCATIONS)
    state.apply_tx(make_tx(ALICE, 0, {"type": "register_agent", "stake": MIN_STAKE}))
    assert state.balance(ALICE.address) == 10_000 - MIN_STAKE
    assert state.data["stakes"][ALICE.address] == {"free": MIN_STAKE, "locked": 0}
    assert ALICE.address in state.data["agents"]


def test_register_agent_sous_min_stake_rejete() -> None:
    state, _ = make_genesis(ALLOCATIONS)
    with pytest.raises(InvalidTx, match="MIN_STAKE"):
        state.apply_tx(make_tx(ALICE, 0, {"type": "register_agent", "stake": MIN_STAKE - 1}))


def test_double_register_rejete() -> None:
    state, _ = make_genesis(ALLOCATIONS)
    state.apply_tx(make_tx(ALICE, 0, {"type": "register_agent", "stake": MIN_STAKE}))
    with pytest.raises(InvalidTx, match="deja"):
        state.apply_tx(make_tx(ALICE, 1, {"type": "register_agent", "stake": MIN_STAKE}))


def test_type_inconnu_rejete() -> None:
    state, _ = make_genesis(ALLOCATIONS)
    with pytest.raises(InvalidTx, match="inconnu"):
        state.apply_tx(make_tx(ALICE, 0, {"type": "n_existe_pas"}))


def test_seal_ne_mute_pas_le_state_d_origine() -> None:
    state, genesis = make_genesis(ALLOCATIONS)
    root = state.root()
    seal_block(state, genesis["header"], [_transfer(0, 100)], ALICE.address, 0)
    assert state.root() == root


def test_apply_block_deterministe() -> None:
    # Deux nodes partant du meme genesis convergent vers le meme state_root.
    txs = [_transfer(0, 100), make_tx(BOB, 0, {"type": "register_agent", "stake": MIN_STAKE})]
    state_a, genesis = make_genesis(ALLOCATIONS)
    sealed_state, block = seal_block(state_a, genesis["header"], txs, ALICE.address, 0)

    state_b, _ = make_genesis(ALLOCATIONS)
    apply_block(state_b, genesis["header"], block)
    assert state_b.root() == sealed_state.root() == block["header"]["state_root"]
    assert state_b.height == 1


def test_apply_block_detecte_state_root_divergent() -> None:
    state, genesis = make_genesis(ALLOCATIONS)
    _, block = seal_block(state, genesis["header"], [_transfer(0, 100)], ALICE.address, 0)
    block["header"]["state_root"] = "f" * 64
    fresh, _ = make_genesis(ALLOCATIONS)
    with pytest.raises(InvalidBlock, match="state_root"):
        apply_block(fresh, genesis["header"], block)
