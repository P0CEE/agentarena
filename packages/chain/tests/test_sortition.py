import pytest

from arena_chain.sortition import select_builders, sortition_seed

AGENTS = [f"agent-{i:02d}" for i in range(10)]
SEED = sortition_seed("a" * 64, "task-1")


def test_meme_partition_partout() -> None:
    # Deux nodes avec le meme seed calculent la meme partition,
    # quel que soit l'ordre dans lequel ils connaissent les agents.
    builders_a, judges_a = select_builders(SEED, AGENTS, k=3)
    builders_b, judges_b = select_builders(SEED, list(reversed(AGENTS)), k=3)
    assert builders_a == builders_b
    assert judges_a == judges_b


def test_partition_complete_et_disjointe() -> None:
    builders, judges = select_builders(SEED, AGENTS, k=3)
    assert len(builders) == 3
    assert len(judges) == 7
    assert set(builders) | set(judges) == set(AGENTS)
    assert set(builders) & set(judges) == set()


def test_exclusion_du_sponsor() -> None:
    sponsor = AGENTS[0]
    builders, judges = select_builders(SEED, AGENTS, k=3, exclude=(sponsor,))
    assert sponsor not in builders
    assert sponsor not in judges


def test_le_seed_change_la_partition() -> None:
    partitions = {
        tuple(select_builders(sortition_seed("b" * 64, f"task-{i}"), AGENTS, k=3)[0])
        for i in range(20)
    }
    assert len(partitions) > 1  # des seeds differents brassent les roles


def test_chaque_agent_construit_parfois() -> None:
    # Frequences raisonnables : sur 200 tasks, personne n'est jamais builder.
    seen = set()
    for i in range(200):
        builders, _ = select_builders(sortition_seed("c" * 64, f"task-{i}"), AGENTS, k=3)
        seen.update(builders)
    assert seen == set(AGENTS)


def test_il_faut_au_moins_un_juge() -> None:
    with pytest.raises(ValueError):
        select_builders(SEED, AGENTS, k=10)


def test_il_faut_au_moins_un_builder() -> None:
    with pytest.raises(ValueError):
        select_builders(SEED, AGENTS, k=0)
