"""Transport réseau injectable : HTTP en production, direct en tests.

Full mesh localhost : chaque message est posté à tous les peers, sans
re-forward (le gossip idempotent est assuré par les sets de deja-vu côté
réception). Les peers morts sont silencieusement ignorés — c'est le consensus
qui gère l'absence, pas le transport.
"""

from typing import Protocol

import httpx


class Transport(Protocol):
    async def send(self, peer: str, path: str, payload: dict) -> None: ...

    async def fetch_blocks(self, peer: str, from_height: int) -> list[dict]: ...


class HttpTransport:
    def __init__(self, timeout: float = 2.0) -> None:
        self._client = httpx.AsyncClient(timeout=timeout)

    async def send(self, peer: str, path: str, payload: dict) -> None:
        try:
            await self._client.post(f"{peer}{path}", json=payload)
        except httpx.HTTPError:
            pass  # peer mort ou lent : le consensus s'en charge

    async def fetch_blocks(self, peer: str, from_height: int) -> list[dict]:
        response = await self._client.get(f"{peer}/blocks", params={"from": from_height})
        response.raise_for_status()
        return response.json()["blocks"]
