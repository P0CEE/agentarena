import asyncio

from arena_agents.stub import StubAgent


def test_build_deterministe() -> None:
    agent = StubAgent("a" * 40)
    one = asyncio.run(agent.build("task-1", "un brief"))
    two = asyncio.run(agent.build("task-1", "un brief"))
    assert one == two


def test_judge_deterministe_et_positif() -> None:
    agent = StubAgent("a" * 40)
    submissions = {"b" * 40: "rendu b", "c" * 40: "rendu c"}
    one = asyncio.run(agent.judge("task-1", "brief", submissions))
    two = asyncio.run(agent.judge("task-1", "brief", submissions))
    assert one == two
    assert all(weight >= 1 for weight in one.values())


def test_deux_juges_notent_differemment() -> None:
    submissions = {"b" * 40: "rendu b", "c" * 40: "rendu c", "d" * 40: "rendu d"}
    juge_1 = asyncio.run(StubAgent("1" * 40).judge("task-1", "brief", submissions))
    juge_2 = asyncio.run(StubAgent("2" * 40).judge("task-1", "brief", submissions))
    assert juge_1 != juge_2  # diversite : la mediane Yuma a du grain a moudre
