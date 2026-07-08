"""Sanctions : slash plagiat calibre, bounty, jail avec grace et escalade."""

import pytest
from conftest import AGENTS, REPORTER, SPONSOR, Net, net_with_agents, supply

from arena_chain.arena import solution_commit
from arena_chain.errors import InvalidTx
from arena_chain.params import (
    BOUNTY_PCT,
    JAIL_BASE,
    OFFENSE_FORGET_WINDOW,
    SLASH_PLAGIARISM_PCT,
)
from arena_chain.slashing import jail

PRIZE = 50_000
SALT = "s" * 32
BY_ADDRESS = {w.address: w for w in AGENTS}


def _submit(net: Net, task_id: str, builder: str, content: str) -> dict:
    return net.send(
        BY_ADDRESS[builder],
        {
            "type": "submit_solution",
            "task": task_id,
            "commit": solution_commit(task_id, builder, content, SALT),
        },
    )


def _manche_avec_plagiat(net: Net) -> tuple[str, str, dict]:
    """Deux builders revelent le MEME contenu, a des hauteurs differentes."""
    net.tick(
        [
            net.send(
                SPONSOR,
                {"type": "create_task", "task": "task-1", "prize": PRIZE, "brief": "brief"},
            )
        ]
    )
    task = net.state.data["tasks"]["task-1"]
    innocent, copieur, autre = task["builders"]
    contents = {innocent: "MEME CONTENU", copieur: "MEME CONTENU", autre: "autre solution"}
    # L'innocent commit en premier (hauteur plus basse), le copieur au bloc suivant.
    net.tick(
        [
            _submit(net, "task-1", innocent, contents[innocent]),
            _submit(net, "task-1", autre, contents[autre]),
        ]
    )
    net.tick([_submit(net, "task-1", copieur, contents[copieur])])
    net.until(task["submit_until"])
    net.tick(
        [
            net.send(
                BY_ADDRESS[b],
                {"type": "reveal_solution", "task": "task-1", "content": contents[b],
                 "salt": SALT},
            )
            for b in task["builders"]
        ]
    )
    return innocent, copieur, task


def test_slash_plagiat_calibre() -> None:
    net = net_with_agents()
    innocent, copieur, _ = _manche_avec_plagiat(net)
    initial_supply = supply(net)
    stake_avant = net.state.data["stakes"][copieur]
    total_avant = stake_avant["free"] + stake_avant["locked"]
    reporter_avant = net.state.balance(REPORTER.address)
    treasury_avant = net.state.data["treasury"]

    net.tick(
        [
            net.send(
                REPORTER,
                {
                    "type": "slash_proof",
                    "kind": "plagiarism",
                    "task": "task-1",
                    "accused": copieur,
                    "earlier": innocent,
                },
            )
        ]
    )

    slashed = total_avant * SLASH_PLAGIARISM_PCT // 100
    bounty = slashed * BOUNTY_PCT // 100
    stake_apres = net.state.data["stakes"][copieur]
    assert stake_apres["free"] + stake_apres["locked"] == total_avant - slashed
    assert net.state.balance(REPORTER.address) == reporter_avant + bounty
    assert net.state.data["treasury"] == treasury_avant + slashed - bounty
    assert supply(net) == initial_supply  # le slash redistribue, ne cree rien


def test_slash_ne_se_rejoue_pas() -> None:
    net = net_with_agents()
    innocent, copieur, _ = _manche_avec_plagiat(net)
    proof = {
        "type": "slash_proof",
        "kind": "plagiarism",
        "task": "task-1",
        "accused": copieur,
        "earlier": innocent,
    }
    net.tick([net.send(REPORTER, proof)])
    with pytest.raises(InvalidTx, match="deja slashe"):
        net.tick([net.build(REPORTER, proof)])


def test_accuser_le_premier_arrivant_rejete() -> None:
    # La chronologie protege l'innocent : on ne peut pas slasher le plus ancien.
    net = net_with_agents()
    innocent, copieur, _ = _manche_avec_plagiat(net)
    tx = net.build(
        REPORTER,
        {
            "type": "slash_proof",
            "kind": "plagiarism",
            "task": "task-1",
            "accused": innocent,
            "earlier": copieur,
        },
    )
    with pytest.raises(InvalidTx, match="chronologie"):
        net.tick([tx])


def test_contenus_differents_rejetes() -> None:
    net = net_with_agents()
    innocent, copieur, task = _manche_avec_plagiat(net)
    autre = next(b for b in task["builders"] if b not in (innocent, copieur))
    tx = net.build(
        REPORTER,
        {
            "type": "slash_proof",
            "kind": "plagiarism",
            "task": "task-1",
            "accused": autre,
            "earlier": innocent,
        },
    )
    with pytest.raises(InvalidTx, match="differents"):
        net.tick([tx])


def test_jail_grace_puis_escalade() -> None:
    net = net_with_agents()
    addr = AGENTS[0].address
    agent = net.state.data["agents"][addr]

    jail(net.state, addr, height=100)  # 1re offense : grace
    assert agent["offenses"] == 1
    assert agent["jailed_until"] == 0

    jail(net.state, addr, height=200)  # 2e offense : JAIL_BASE blocs
    assert agent["jailed_until"] == 200 + JAIL_BASE

    jail(net.state, addr, height=300)  # 3e offense : la duree double
    assert agent["jailed_until"] == 300 + JAIL_BASE * 2


def test_jail_fenetre_d_oubli() -> None:
    net = net_with_agents()
    addr = AGENTS[0].address
    agent = net.state.data["agents"][addr]
    jail(net.state, addr, height=100)
    # Bien plus tard : l'offense est oubliee, retour a la grace.
    jail(net.state, addr, height=100 + OFFENSE_FORGET_WINDOW + 1)
    assert agent["offenses"] == 1
    assert agent["jailed_until"] == 0


def test_agent_jailed_sort_du_pool_eligible() -> None:
    # 10 agents - 1 jailed = 9 eligibles < 3 builders + 7 juges requis.
    net = net_with_agents()
    net.state.data["agents"][AGENTS[0].address]["jailed_until"] = 10_000
    tx = net.build(
        SPONSOR, {"type": "create_task", "task": "task-1", "prize": PRIZE, "brief": "b"}
    )
    with pytest.raises(InvalidTx, match="pool insuffisant"):
        net.tick([tx])
