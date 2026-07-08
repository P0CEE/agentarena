"""Interface des agents : la couche applicative off-chain (ADR-0001).

Un agent produit (build) ou note (judge). Ses sorties sont des données brutes :
le rendu est un texte libre, les notes sont des poids relatifs positifs — c'est
le runner qui les normalise en vecteur protocolaire (somme == SCALE). Le
non-déterminisme du LLM ne touche jamais le consensus.
"""

from typing import Protocol


class AgentError(Exception):
    """Échec d'un agent (timeout, API en panne, réponse inexploitable).

    Traité comme un no-show : l'agent ne poste pas sa tx, le protocole le
    jail avec grâce au premier incident.
    """


class Agent(Protocol):
    async def build(self, task_id: str, brief: str) -> str:
        """Produit le rendu pour un brief."""
        ...

    async def judge(self, task_id: str, brief: str, submissions: dict[str, str]) -> dict[str, int]:
        """Note les rendus (adresse builder -> poids relatif >= 0)."""
        ...
