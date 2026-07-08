import hashlib

import pytest

from arena_chain.wallet import ADDRESS_LEN, Wallet, address_of, verify_signature

SEED = bytes(range(32))


def test_from_seed_deterministe() -> None:
    a = Wallet.from_seed(SEED)
    b = Wallet.from_seed(SEED)
    assert a.address == b.address
    assert a.pubkey == b.pubkey


def test_seed_de_mauvaise_taille_rejete() -> None:
    with pytest.raises(ValueError):
        Wallet.from_seed(b"court")


def test_adresse_est_un_hash_tronque_de_la_pubkey() -> None:
    wallet = Wallet.from_seed(SEED)
    assert len(wallet.address) == ADDRESS_LEN
    assert wallet.address == hashlib.sha256(wallet.pubkey).hexdigest()[:ADDRESS_LEN]
    assert address_of(wallet.pubkey) == wallet.address


def test_sign_verify() -> None:
    wallet = Wallet.from_seed(SEED)
    digest = hashlib.sha256(b"message").digest()
    signature = wallet.sign(digest)
    assert verify_signature(wallet.pubkey, digest, signature)


def test_verify_echoue_mauvaise_cle() -> None:
    wallet = Wallet.from_seed(SEED)
    autre = Wallet.generate()
    digest = hashlib.sha256(b"message").digest()
    assert not verify_signature(autre.pubkey, digest, wallet.sign(digest))


def test_verify_echoue_digest_altere() -> None:
    wallet = Wallet.from_seed(SEED)
    signature = wallet.sign(hashlib.sha256(b"message").digest())
    assert not verify_signature(wallet.pubkey, hashlib.sha256(b"autre").digest(), signature)
