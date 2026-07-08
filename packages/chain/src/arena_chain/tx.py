"""Transaction signée, account-based.

Le txid couvre {sender, nonce, payload} — jamais la signature (sinon dépendance
circulaire). La signature porte sur les octets du txid, avec séparation de
domaine. Le pubkey n'est pas signé : il est lié au sender par l'adresse.
"""

from arena_chain.canonical import NonCanonicalError, tagged_hash
from arena_chain.errors import InvalidTx
from arena_chain.wallet import ADDRESS_LEN, Wallet, address_of, verify_signature

TX_TAG = "agentarena/tx/v1"
PUBKEY_HEX_LEN = 64  # 32 octets


def tx_digest(sender: str, nonce: int, payload: dict) -> str:
    return tagged_hash(TX_TAG, {"sender": sender, "nonce": nonce, "payload": payload})


def txid(tx: dict) -> str:
    return tx_digest(tx["sender"], tx["nonce"], tx["payload"])


def make_tx(wallet: Wallet, nonce: int, payload: dict) -> dict:
    digest = tx_digest(wallet.address, nonce, payload)
    return {
        "sender": wallet.address,
        "pubkey": wallet.pubkey.hex(),
        "nonce": nonce,
        "payload": payload,
        "signature": wallet.sign(bytes.fromhex(digest)),
    }


def verify_tx(tx: dict) -> str:
    """Valide la tx isolément (structure, adresse, signature) et retourne son txid.

    Le nonce exact et le solde sont vérifiés par le state à l'application.
    """
    if not isinstance(tx, dict):
        raise InvalidTx("tx non-dict")
    if set(tx) != {"sender", "pubkey", "nonce", "payload", "signature"}:
        raise InvalidTx(f"champs de tx invalides: {sorted(tx)}")
    sender, nonce, payload = tx["sender"], tx["nonce"], tx["payload"]
    if not isinstance(sender, str) or len(sender) != ADDRESS_LEN:
        raise InvalidTx("sender invalide")
    if type(nonce) is not int or nonce < 0:
        raise InvalidTx("nonce invalide")
    if not isinstance(payload, dict) or not isinstance(payload.get("type"), str):
        raise InvalidTx("payload sans type")
    if not isinstance(tx["pubkey"], str) or len(tx["pubkey"]) != PUBKEY_HEX_LEN:
        raise InvalidTx("pubkey invalide")
    try:
        pubkey = bytes.fromhex(tx["pubkey"])
    except ValueError as exc:
        raise InvalidTx("pubkey non-hex") from exc
    if address_of(pubkey) != sender:
        raise InvalidTx("le pubkey ne correspond pas au sender")
    try:
        digest = tx_digest(sender, nonce, payload)
    except NonCanonicalError as exc:
        raise InvalidTx(f"payload non canonique: {exc}") from exc
    if not isinstance(tx["signature"], str) or not verify_signature(
        pubkey, bytes.fromhex(digest), tx["signature"]
    ):
        raise InvalidTx("signature invalide")
    return digest
