class ChainError(Exception):
    """Erreur de protocole."""


class InvalidTx(ChainError):
    """Transaction rejetée (signature, nonce, solde, payload)."""


class InvalidBlock(ChainError):
    """Bloc rejeté (chaînage, tx_root, state_root, ordre des tx)."""
