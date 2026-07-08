"""La manche complète : create_task -> commits -> reveals -> notes -> règlement."""

import pytest
from conftest import AGENTS, SPONSOR, WALLETS, Net, net_with_agents, supply

from arena_chain.arena import scores_commit, solution_commit
from arena_chain.errors import InvalidTx
from arena_chain.genesis import make_genesis
from arena_chain.params import JUDGE_RESERVE_PCT, MIN_PRICE, SCALE
from arena_chain.state import apply_block

PRIZE = 50_000
SALT = "s" * 32
BY_ADDRESS = {w.address: w for w in AGENTS}


def _s(milliemes: int) -> int:
    return milliemes * SCALE // 1000


def create_task(net: Net, task_id: str = "task-1", prize: int = PRIZE) -> dict:
    net.tick(
        [
            net.send(
                SPONSOR,
                {
                    "type": "create_task",
                    "task": task_id,
                    "prize": prize,
                    "brief": "ecris une fonction is_prime",
                },
            )
        ]
    )
    return net.state.data["tasks"][task_id]


def submit_and_reveal(net: Net, task: dict, task_id: str, contents: dict[str, str]) -> None:
    builders = task["builders"]
    net.tick(
        [
            net.send(
                BY_ADDRESS[b],
                {
                    "type": "submit_solution",
                    "task": task_id,
                    "commit": solution_commit(task_id, b, contents[b], SALT),
                },
            )
            for b in builders
        ]
    )
    net.until(task["submit_until"])
    net.tick(
        [
            net.send(
                BY_ADDRESS[b],
                {"type": "reveal_solution", "task": task_id, "content": contents[b], "salt": SALT},
            )
            for b in builders
        ]
    )
    net.until(task["reveal_until"])


def run_manche(net: Net, task_id: str = "task-1", deviant_index: int | None = None) -> dict:
    """Joue une manche entière et retourne la task réglée."""
    task = create_task(net, task_id)
    contents = {b: f"solution de {b}" for b in task["builders"]}
    submit_and_reveal(net, task, task_id, contents)

    revealed = sorted(task["builders"])
    honest = dict(zip(revealed, [_s(500), _s(300), _s(200)]))
    all_on_last = dict.fromkeys(revealed, 0) | {revealed[-1]: SCALE}
    deviant = task["judges"][deviant_index] if deviant_index is not None else None
    vectors = {j: (all_on_last if j == deviant else honest) for j in task["judges"]}

    net.tick(
        [
            net.send(
                BY_ADDRESS[j],
                {
                    "type": "commit_scores",
                    "task": task_id,
                    "commit": scores_commit(task_id, j, vectors[j], SALT),
                },
            )
            for j in task["judges"]
        ]
    )
    net.until(task["commit_score_until"])
    net.tick(
        [
            net.send(
                BY_ADDRESS[j],
                {"type": "reveal_scores", "task": task_id, "scores": vectors[j], "salt": SALT},
            )
            for j in task["judges"]
        ]
    )
    net.until(task["reveal_score_until"])
    return net.state.data["tasks"][task_id]


def test_manche_complete_jusqu_au_reglement() -> None:
    net = net_with_agents()
    initial_supply = supply(net)
    task = run_manche(net)

    assert task["state"] == "SETTLED"
    payouts = task["result"]["payouts"]
    # Le prix est integralement distribue : 80% builders, 20% juges, au token pres.
    reserve = PRIZE * JUDGE_RESERVE_PCT // 100
    assert sum(payouts["builders"].values()) == PRIZE - reserve
    assert sum(payouts["judges"].values()) == reserve
    # Le mieux note (0.5) touche plus que le moins bien note (0.2).
    ordered = [payouts["builders"][b] for b in task["result"]["builders"]]
    assert ordered[0] > ordered[1] > ordered[2]
    assert supply(net) == initial_supply  # aucun token cree ni detruit


def test_manche_rejouable_deux_fois_identique() -> None:
    net_a = net_with_agents()
    run_manche(net_a)
    net_b = net_with_agents()
    run_manche(net_b)
    assert net_a.state.root() == net_b.state.root()


def test_replay_des_blocs_sur_un_node_frais() -> None:
    # Un node qui rejoue tous les blocs converge exactement (catch-up).
    net = net_with_agents()
    run_manche(net)
    replica, genesis = make_genesis({w.address: 1_000_000 for w in WALLETS})
    prev = genesis["header"]
    for block in net.blocks[1:]:
        apply_block(replica, prev, block)
        prev = block["header"]
    assert replica.root() == net.state.root()


def test_juge_deviant_clippe_et_sous_paye() -> None:
    net = net_with_agents()
    task = run_manche(net, deviant_index=0)
    deviant = task["judges"][0]
    judge_payouts = task["result"]["payouts"]["judges"]
    honest = [j for j in task["result"]["judges"] if j != deviant]
    assert judge_payouts[deviant] < min(judge_payouts[j] for j in honest)


# --- create_task : les garde-fous ---


def test_prize_sous_min_price_rejete() -> None:
    net = net_with_agents()
    tx = net.build(
        SPONSOR, {"type": "create_task", "task": "t", "prize": MIN_PRICE - 1, "brief": "b"}
    )
    with pytest.raises(InvalidTx, match="MIN_PRICE"):
        net.tick([tx])


def test_pool_insuffisant_rejete() -> None:
    net = Net()  # personne n'est enregistre
    tx = net.build(SPONSOR, {"type": "create_task", "task": "t", "prize": PRIZE, "brief": "b"})
    with pytest.raises(InvalidTx, match="pool insuffisant"):
        net.tick([tx])


def test_task_id_duplique_rejete() -> None:
    net = net_with_agents()
    create_task(net, "task-1")
    tx = net.build(
        SPONSOR, {"type": "create_task", "task": "task-1", "prize": PRIZE, "brief": "b"}
    )
    with pytest.raises(InvalidTx, match="deja existante"):
        net.tick([tx])


def test_le_prix_part_en_escrow() -> None:
    net = net_with_agents()
    before = net.state.balance(SPONSOR.address)
    create_task(net)
    assert net.state.balance(SPONSOR.address) == before - PRIZE


def test_sponsor_exclu_et_partition_3_7() -> None:
    net = net_with_agents()
    task = create_task(net)
    assert SPONSOR.address not in task["builders"] + task["judges"]
    assert len(task["builders"]) == 3
    assert len(task["judges"]) == 7


# --- fenetres et roles ---


def test_non_builder_ne_peut_pas_soumettre() -> None:
    net = net_with_agents()
    task = create_task(net)
    judge = task["judges"][0]
    tx = net.build(
        BY_ADDRESS[judge], {"type": "submit_solution", "task": "task-1", "commit": "0" * 64}
    )
    with pytest.raises(InvalidTx, match="builder designe"):
        net.tick([tx])


def test_submit_apres_deadline_rejete() -> None:
    net = net_with_agents()
    task = create_task(net)
    net.until(task["submit_until"])  # la fenetre se ferme en fin de ce bloc
    builder = task["builders"][0]
    tx = net.build(
        BY_ADDRESS[builder], {"type": "submit_solution", "task": "task-1", "commit": "0" * 64}
    )
    with pytest.raises(InvalidTx, match="fermee"):
        net.tick([tx])


def test_reveal_mismatch_enregistre_puis_grace() -> None:
    net = net_with_agents()
    task = create_task(net)
    builder = task["builders"][0]
    net.tick(
        [
            net.send(
                BY_ADDRESS[builder],
                {
                    "type": "submit_solution",
                    "task": "task-1",
                    "commit": solution_commit("task-1", builder, "contenu", SALT),
                },
            )
        ]
    )
    net.until(task["submit_until"])
    net.tick(
        [
            net.send(
                BY_ADDRESS[builder],
                {"type": "reveal_solution", "task": "task-1", "content": "AUTRE", "salt": SALT},
            )
        ]
    )
    assert net.state.data["submissions"][f"task-1|{builder}"]["status"] == "MISMATCH"
    net.until(task["reveal_until"])
    # Mismatch traite comme no-show : offense enregistree, grace au 1er incident.
    agent = net.state.data["agents"][builder]
    assert agent["offenses"] == 1
    assert agent["jailed_until"] == 0


def test_somme_des_notes_stricte() -> None:
    net = net_with_agents()
    task = create_task(net)
    contents = {b: f"solution de {b}" for b in task["builders"]}
    submit_and_reveal(net, task, "task-1", contents)
    bad = dict.fromkeys(sorted(task["builders"]), 1)  # somme != SCALE
    judge = task["judges"][0]
    net.tick(
        [
            net.send(
                BY_ADDRESS[judge],
                {
                    "type": "commit_scores",
                    "task": "task-1",
                    "commit": scores_commit("task-1", judge, bad, SALT),
                },
            )
        ]
    )
    net.until(task["commit_score_until"])
    tx = net.build(
        BY_ADDRESS[judge], {"type": "reveal_scores", "task": "task-1", "scores": bad, "salt": SALT}
    )
    with pytest.raises(InvalidTx, match="SCALE"):
        net.tick([tx])


# --- aborts : l'escrow ne reste jamais bloque ---


def test_abort_sans_soumission_rembourse_le_sponsor() -> None:
    net = net_with_agents()
    before = net.state.balance(SPONSOR.address)
    task = create_task(net)
    initial_supply = supply(net)
    net.until(task["submit_until"])
    task = net.state.data["tasks"]["task-1"]
    assert task["state"] == "SETTLED"
    assert task["result"] == {"aborted": "no_submission"}
    assert net.state.balance(SPONSOR.address) == before  # rembourse
    assert supply(net) == initial_supply
    # Tous les builders no-show ont pris une offense (grace au 1er incident).
    for builder in task["builders"]:
        assert net.state.data["agents"][builder]["offenses"] == 1


def test_abort_sans_notes_rembourse_le_sponsor() -> None:
    net = net_with_agents()
    before = net.state.balance(SPONSOR.address)
    task = create_task(net)
    contents = {b: f"solution de {b}" for b in task["builders"]}
    submit_and_reveal(net, task, "task-1", contents)
    net.until(task["reveal_score_until"])  # aucun juge ne note
    task = net.state.data["tasks"]["task-1"]
    assert task["result"] == {"aborted": "no_scores"}
    assert net.state.balance(SPONSOR.address) == before
    # Les 7 juges no-show ont chacun une offense.
    assert all(net.state.data["agents"][j]["offenses"] == 1 for j in task["judges"])
