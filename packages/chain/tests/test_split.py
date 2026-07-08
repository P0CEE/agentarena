import pytest

from arena_chain.split import split


def test_somme_exacte() -> None:
    assert sum(split(1_000, [566_265_060, 313_253_012, 120_481_928])) == 1_000


def test_proportions() -> None:
    assert split(100, [60, 30, 10]) == [60, 30, 10]


def test_reste_aux_plus_grands_restes() -> None:
    # 100 / 3 : deux unites de reste, aux plus grands restes d'abord.
    assert split(100, [1, 1, 1]) == [34, 33, 33]


def test_tie_break_par_indice() -> None:
    # Restes strictement egaux : l'indice le plus bas gagne l'unite.
    assert split(3, [1, 1]) == [2, 1]


def test_poids_nul_ne_recoit_rien() -> None:
    assert split(10, [0, 1]) == [0, 10]


def test_total_zero() -> None:
    assert split(0, [3, 7]) == [0, 0]


def test_invariant_sur_grille() -> None:
    # Aucun token cree ni detruit, quel que soit le decoupage.
    for total in (1, 7, 99, 1_000, 999_983):
        for weights in ([1], [1, 2, 3], [10, 10, 10, 1], [7, 0, 13, 29, 5]):
            payouts = split(total, weights)
            assert sum(payouts) == total
            assert all(p >= 0 for p in payouts)


def test_poids_tous_nuls_rejetes() -> None:
    with pytest.raises(ValueError, match="nuls"):
        split(10, [0, 0])


def test_total_negatif_rejete() -> None:
    with pytest.raises(ValueError):
        split(-1, [1])


def test_float_rejete() -> None:
    with pytest.raises(ValueError):
        split(10, [0.5, 0.5])
