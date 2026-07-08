"""Wallet Ed25519 (PyNaCl).

La clé privée signe un digest sha256 ; l'adresse est un hash tronqué de la clé
publique (jamais la clé publique elle-même).
"""

import hashlib

import nacl.exceptions
import nacl.signing

ADDRESS_LEN = 40  # 20 octets en hex
SEED_LEN = 32


def address_of(pubkey: bytes) -> str:
    return hashlib.sha256(pubkey).hexdigest()[:ADDRESS_LEN]


class Wallet:
    def __init__(self, signing_key: nacl.signing.SigningKey) -> None:
        self._signing_key = signing_key
        self.pubkey: bytes = bytes(signing_key.verify_key)
        self.address: str = address_of(self.pubkey)

    @classmethod
    def generate(cls) -> "Wallet":
        return cls(nacl.signing.SigningKey.generate())

    @classmethod
    def from_seed(cls, seed: bytes) -> "Wallet":
        """Wallet déterministe (genesis, tests). seed = 32 octets exactement."""
        if len(seed) != SEED_LEN:
            raise ValueError(f"seed de {SEED_LEN} octets attendu, recu {len(seed)}")
        return cls(nacl.signing.SigningKey(seed))

    def sign(self, digest: bytes) -> str:
        """Signature hex (64 octets) d'un digest."""
        return self._signing_key.sign(digest).signature.hex()


def verify_signature(pubkey: bytes, digest: bytes, signature_hex: str) -> bool:
    try:
        nacl.signing.VerifyKey(pubkey).verify(digest, bytes.fromhex(signature_hex))
    except (nacl.exceptions.BadSignatureError, nacl.exceptions.CryptoError, ValueError):
        return False
    return True
