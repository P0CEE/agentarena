"""Sérialisation canonique unique du projet.

Tout hash du protocole passe par ici : mêmes octets sur tous les nodes, sinon
le réseau fork. Règles non négociables : entiers uniquement (jamais de float),
clés de dict triées, ascii pur (anti divergences Unicode NFC/NFD selon l'OS).
"""

import hashlib
import json


class NonCanonicalError(TypeError):
    """L'objet contient une valeur interdite dans le protocole (ex. float)."""


def _check(obj: object) -> None:
    if isinstance(obj, bool) or obj is None or isinstance(obj, int | str):
        return
    if isinstance(obj, float):
        raise NonCanonicalError("float interdit dans le protocole (fixed-point int uniquement)")
    if isinstance(obj, dict):
        for key, value in obj.items():
            if not isinstance(key, str):
                raise NonCanonicalError(f"cle de dict non-str: {key!r}")
            _check(value)
        return
    if isinstance(obj, list | tuple):
        for value in obj:
            _check(value)
        return
    raise NonCanonicalError(f"type non canonique: {type(obj).__name__}")


def canonical(obj: object) -> bytes:
    """Octets canoniques d'un objet : identiques sur tous les nodes ou exception."""
    _check(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def tagged_hash(tag: str, obj: object) -> str:
    """sha256 hex avec séparation de domaine (anti-rejeu entre types de messages)."""
    hasher = hashlib.sha256()
    hasher.update(tag.encode("ascii"))
    hasher.update(b"\x00")
    hasher.update(canonical(obj))
    return hasher.hexdigest()
