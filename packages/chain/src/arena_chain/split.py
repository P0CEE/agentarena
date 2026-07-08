"""Répartition entière conservatrice (largest remainder).

Invariant absolu : sum(payouts) == total, au token près. Aucune poussière
créée ni détruite — la monnaie du protocole ne fuit jamais dans les arrondis.
"""


def split(total: int, weights: list[int]) -> list[int]:
    """Répartit total proportionnellement aux poids, en entiers exacts.

    Le reste de la division est distribué aux plus grands restes ; à reste
    égal, l'indice le plus bas gagne (tie-break canonique : l'indice suit
    l'ordre canonique des adresses).
    """
    if type(total) is not int or total < 0:
        raise ValueError(f"total invalide: {total!r}")
    for weight in weights:
        if type(weight) is not int or weight < 0:
            raise ValueError(f"poids invalide: {weight!r}")
    weight_sum = sum(weights)
    if weight_sum == 0:
        raise ValueError("poids tous nuls : rien a repartir")

    base = [total * weight // weight_sum for weight in weights]
    remainders = [total * weight % weight_sum for weight in weights]
    leftover = total - sum(base)
    by_remainder = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))
    payouts = list(base)
    for i in by_remainder[:leftover]:
        payouts[i] += 1
    return payouts
