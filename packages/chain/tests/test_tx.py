import pytest

from arena_chain.errors import InvalidTx
from arena_chain.tx import make_tx, txid, verify_tx
from arena_chain.wallet import Wallet

ALICE = Wallet.from_seed(b"a" * 32)
BOB = Wallet.from_seed(b"b" * 32)


def _tx(nonce: int = 0) -> dict:
    return make_tx(ALICE, nonce, {"type": "transfer", "to": BOB.address, "amount": 5})


def test_verify_retourne_le_txid() -> None:
    tx = _tx()
    assert verify_tx(tx) == txid(tx)


def test_txid_independant_de_la_signature() -> None:
    tx = _tx()
    before = txid(tx)
    tx["signature"] = "0" * 128
    assert txid(tx) == before  # le txid ne couvre jamais la signature


def test_signature_alteree_rejetee() -> None:
    tx = _tx()
    tx["signature"] = "0" * 128
    with pytest.raises(InvalidTx):
        verify_tx(tx)


def test_payload_altere_rejete() -> None:
    tx = _tx()
    tx["payload"]["amount"] = 500
    with pytest.raises(InvalidTx):
        verify_tx(tx)


def test_pubkey_substituee_rejetee() -> None:
    # BOB tente de rejouer la tx d'ALICE avec sa propre cle.
    tx = _tx()
    tx["pubkey"] = BOB.pubkey.hex()
    with pytest.raises(InvalidTx, match="sender"):
        verify_tx(tx)


def test_payload_avec_float_rejete() -> None:
    tx = make_tx(ALICE, 0, {"type": "transfer", "to": BOB.address, "amount": 5})
    tx["payload"] = {"type": "transfer", "to": BOB.address, "amount": 5.0}
    with pytest.raises(InvalidTx):
        verify_tx(tx)


def test_champs_manquants_rejetes() -> None:
    tx = _tx()
    del tx["pubkey"]
    with pytest.raises(InvalidTx):
        verify_tx(tx)
