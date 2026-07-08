from arena_chain.params import SCALE

from arena_agents.runner import normalize_scores

BUILDERS = ["a" * 40, "b" * 40, "c" * 40]


def test_somme_exactement_scale() -> None:
    scores = normalize_scores(BUILDERS, {BUILDERS[0]: 80, BUILDERS[1]: 45, BUILDERS[2]: 60})
    assert sum(scores.values()) == SCALE
    assert scores[BUILDERS[0]] > scores[BUILDERS[2]] > scores[BUILDERS[1]]


def test_poids_nuls_deviennent_egalite() -> None:
    scores = normalize_scores(BUILDERS, {})
    assert sum(scores.values()) == SCALE
    assert max(scores.values()) - min(scores.values()) <= 1


def test_poids_negatifs_ecrases() -> None:
    scores = normalize_scores(BUILDERS, {BUILDERS[0]: -10, BUILDERS[1]: 100})
    assert scores[BUILDERS[0]] == 0
    assert sum(scores.values()) == SCALE
