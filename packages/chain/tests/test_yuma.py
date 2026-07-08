import pytest

from arena_chain.canonical import tagged_hash
from arena_chain.params import SCALE
from arena_chain.yuma import normalize_stakes, yuma_consensus


def _s(milliemes: int) -> int:
    """Note en milliemes -> fixed-point SCALE (0.6 -> _s(600))."""
    return milliemes * SCALE // 1000


# L'exemple de reference des notes : V3 (20% du stake) gonfle le builder 3.
GOLDEN_W = [
    [_s(600), _s(300), _s(100)],  # V1
    [_s(500), _s(400), _s(100)],  # V2
    [_s(100), _s(100), _s(800)],  # V3 le tricheur
]
GOLDEN_STAKES = [50, 30, 20]


def test_golden_consensus() -> None:
    result = yuma_consensus(GOLDEN_W, GOLDEN_STAKES)
    # Le 0.8 de V3, minoritaire a 20%, ne deplace PAS le consensus.
    assert result["consensus"] == [_s(600), _s(300), _s(100)]


def test_golden_clipping_neutralise_le_tricheur() -> None:
    result = yuma_consensus(GOLDEN_W, GOLDEN_STAKES)
    assert result["clipped"][2] == [_s(100), _s(100), _s(100)]  # 0.8 -> 0.1
    assert result["clipped"][1][1] == _s(300)  # V2: 0.4 -> 0.3


def test_golden_incentive() -> None:
    result = yuma_consensus(GOLDEN_W, GOLDEN_STAKES)
    # Valeurs exactes de l'algorithme fixed-point (0.566 / 0.313 / 0.120).
    assert result["incentive"] == [566_265_060, 313_253_012, 120_481_928]
    assert sum(result["incentive"]) == SCALE  # rien ne fuit


def test_golden_dividends() -> None:
    result = yuma_consensus(GOLDEN_W, GOLDEN_STAKES)
    assert [d // 10**6 for d in result["dividends"]] == [602, 325, 72]


def test_golden_le_tricheur_sous_paye() -> None:
    # V3 detient 20% du stake mais touche ~7.2% des dividends.
    result = yuma_consensus(GOLDEN_W, GOLDEN_STAKES)
    dividends = result["dividends"]
    part_v3 = dividends[2] * 1000 // sum(dividends)
    assert part_v3 == 72


def test_rejouable_1000x_hash_identique() -> None:
    reference = tagged_hash("test", yuma_consensus(GOLDEN_W, GOLDEN_STAKES))
    for _ in range(1000):
        assert tagged_hash("test", yuma_consensus(GOLDEN_W, GOLDEN_STAKES)) == reference


def test_bonds_ema_stationnaire() -> None:
    # Si les notes ne changent pas, l'EMA converge sur elle-meme.
    first = yuma_consensus(GOLDEN_W, GOLDEN_STAKES)
    second = yuma_consensus(GOLDEN_W, GOLDEN_STAKES, bonds_prev=first["bonds"])
    assert second["bonds"] == first["bonds"]


def test_bonds_ema_lisse_depuis_zero() -> None:
    n_judges, n_builders = len(GOLDEN_W), len(GOLDEN_W[0])
    zeros = [[0] * n_builders for _ in range(n_judges)]
    fresh = yuma_consensus(GOLDEN_W, GOLDEN_STAKES)
    smoothed = yuma_consensus(GOLDEN_W, GOLDEN_STAKES, bonds_prev=zeros)
    for i in range(n_judges):
        for j in range(n_builders):
            assert smoothed["bonds"][i][j] == fresh["bonds"][i][j] // 10


def test_stakes_strictement_egaux_deterministe() -> None:
    # Le chemin NOMINAL au genesis : egalites partout, tie-break canonique.
    weights = [[SCALE, 0], [0, SCALE]]
    result = yuma_consensus(weights, [1, 1])
    assert result["consensus"] == [SCALE, SCALE]
    reference = tagged_hash("test", result)
    for _ in range(100):
        assert tagged_hash("test", yuma_consensus(weights, [1, 1])) == reference


def test_un_seul_juge() -> None:
    result = yuma_consensus([[_s(700), _s(300)]], [123])
    assert result["consensus"] == [_s(700), _s(300)]
    assert result["dividends"] == [SCALE]  # il touche tout


def test_notes_toutes_nulles_sans_crash() -> None:
    # sumR == 0 : pas de division par zero, personne n'est paye.
    result = yuma_consensus([[0, 0], [0, 0]], [1, 1])
    assert result["incentive"] == [0, 0]
    assert result["dividends"] == [0, 0]


def test_matrice_vide_rejetee() -> None:
    with pytest.raises(ValueError):
        yuma_consensus([], [])


def test_matrice_non_rectangulaire_rejetee() -> None:
    with pytest.raises(ValueError, match="rectangulaire"):
        yuma_consensus([[1, 2], [1]], [1, 1])


def test_float_rejete() -> None:
    with pytest.raises(ValueError, match="float"):
        yuma_consensus([[0.5, 0.5]], [1])


def test_stake_total_nul_rejete() -> None:
    with pytest.raises(ValueError, match="stake"):
        normalize_stakes([0, 0])
