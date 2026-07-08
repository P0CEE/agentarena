"""Moteur Yuma : agrégation des notes des juges, pondérée par le stake.

100 % fixed-point entier (SCALE) : le moindre float ici forke la chaîne au
premier règlement. Les lignes (juges) et colonnes (builders) de W sont en ordre
canonique — adresses triées — sous la responsabilité de l'appelant (arena).

Pipeline : consensus (médiane pondérée, KAPPA) -> clipping -> rank ->
incentive (part du prix aux builders) -> bonds EMA -> dividends (juges).
"""

from arena_chain.params import ALPHA_BONDS_DEN, ALPHA_BONDS_NUM, KAPPA, SCALE

Matrix = list[list[int]]


def fixed_div(a: int, b: int) -> int:
    """Division fixed-point, arrondi déterministe au plus proche. 0 si b == 0."""
    return (a * SCALE + b // 2) // b if b else 0


def fixed_mul(a: int, b: int) -> int:
    return (a * b) // SCALE


def normalize_stakes(stakes: list[int]) -> list[int]:
    total = sum(stakes)
    if total <= 0:
        raise ValueError("stake total nul : aucun juge a ponderer")
    return [fixed_div(stake, total) for stake in stakes]


def weighted_median(column: list[int], stakes_norm: list[int]) -> int:
    """Plus grande note w telle que le stake cumulé des juges notant >= w atteigne KAPPA.

    Tie-break total et canonique : note décroissante, puis stake décroissant,
    puis indice croissant (l'indice suit l'ordre canonique des adresses).
    Indispensable avec des stakes strictement égaux (chemin nominal au genesis).
    """
    pairs = sorted(
        ((column[i], stakes_norm[i], i) for i in range(len(column))),
        key=lambda t: (-t[0], -t[1], t[2]),
    )
    acc = 0
    for note, stake, _ in pairs:
        acc += stake
        if acc >= KAPPA:
            return note
    return 0


def _validate(weights: Matrix, stakes: list[int]) -> None:
    if not weights or not weights[0]:
        raise ValueError("matrice de notes vide")
    if len(stakes) != len(weights):
        raise ValueError("un stake par juge requis")
    width = len(weights[0])
    for row in weights:
        if len(row) != width:
            raise ValueError("matrice de notes non rectangulaire")
        for value in row:
            if type(value) is not int:
                raise ValueError(f"note non entiere: {value!r} (float interdit)")
    for stake in stakes:
        if type(stake) is not int or stake < 0:
            raise ValueError(f"stake invalide: {stake!r}")


def yuma_consensus(
    weights: Matrix, stakes: list[int], bonds_prev: Matrix | None = None
) -> dict:
    """Un règlement Yuma. weights[i][j] = note du juge i pour le builder j (int SCALE).

    stakes = stakes bruts des juges (normalisés ici). Retourne consensus,
    clipped, incentive (par builder), bonds et dividends (par juge).
    """
    _validate(weights, stakes)
    stakes_norm = normalize_stakes(stakes)
    n_judges, n_builders = len(weights), len(weights[0])

    consensus = [
        weighted_median([weights[i][j] for i in range(n_judges)], stakes_norm)
        for j in range(n_builders)
    ]
    clipped = [
        [min(weights[i][j], consensus[j]) for j in range(n_builders)] for i in range(n_judges)
    ]
    rank = [
        sum(fixed_mul(stakes_norm[i], clipped[i][j]) for i in range(n_judges))
        for j in range(n_builders)
    ]
    rank_total = sum(rank)
    incentive = (
        [fixed_div(r, rank_total) for r in rank] if rank_total > 0 else [0] * n_builders
    )
    bonds_delta = [
        [
            fixed_div(fixed_mul(stakes_norm[i], clipped[i][j]), rank[j]) if rank[j] > 0 else 0
            for j in range(n_builders)
        ]
        for i in range(n_judges)
    ]
    if bonds_prev is None:
        bonds = bonds_delta
    else:
        bonds = [
            [
                (
                    ALPHA_BONDS_NUM * bonds_delta[i][j]
                    + (ALPHA_BONDS_DEN - ALPHA_BONDS_NUM) * bonds_prev[i][j]
                )
                // ALPHA_BONDS_DEN
                for j in range(n_builders)
            ]
            for i in range(n_judges)
        ]
    dividends = [
        sum(fixed_mul(bonds[i][j], incentive[j]) for j in range(n_builders))
        for i in range(n_judges)
    ]
    return {
        "consensus": consensus,
        "clipped": clipped,
        "incentive": incentive,
        "bonds": bonds,
        "dividends": dividends,
    }
