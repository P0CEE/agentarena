"""Sortition : partition déterministe du pool d'agents en Builders et Juges.

Chaque node calcule la même partition sans communication : tri des adresses
par hash(seed || adresse), les k premiers construisent, le reste juge.
Builders et Juges sont disjoints par construction ; le sponsor et les agents
jailed sont exclus en amont via `exclude`.

Limites assumées (voir audit) : le seed dérive du dernier bloc finalisé, donc
un proposer peut en théorie le grinder — pas de VRF ici. Le tirage est
uniforme, non pondéré par le stake : équivalent au genesis (stakes égaux).
"""

from arena_chain.canonical import tagged_hash

SEED_TAG = "agentarena/sortition/seed/v1"
RANK_TAG = "agentarena/sortition/rank/v1"


def sortition_seed(finalized_block_hash: str, task_id: str) -> str:
    return tagged_hash(SEED_TAG, {"block": finalized_block_hash, "task": task_id})


def select_builders(
    seed: str,
    eligibles: list[str],
    k: int,
    exclude: tuple[str, ...] = (),
) -> tuple[list[str], list[str]]:
    """Retourne (builders, juges). Exige au moins 1 builder ET 1 juge."""
    pool = sorted(set(eligibles) - set(exclude))
    if k < 1 or k >= len(pool):
        raise ValueError(f"k={k} impossible pour un pool de {len(pool)} agents")
    ranked = sorted(pool, key=lambda addr: tagged_hash(RANK_TAG, {"seed": seed, "addr": addr}))
    return ranked[:k], ranked[k:]
