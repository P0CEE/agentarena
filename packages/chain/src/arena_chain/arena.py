"""Machine à manche : create_task -> commits -> reveals -> notes -> règlement Yuma.

États d'une Task : OPEN (commits des rendus) -> SCORING (reveals, puis notes en
commit-reveal) -> SETTLED. Toutes les transitions automatiques vivent dans le
hook de fin de bloc, rejoué à l'identique par tous les nodes à chaque hauteur ;
le règlement se déclenche à la clôture de la dernière fenêtre — pas de tx de
crank ni d'état d'attente (déviation assumée des notes de conception).

Fenêtres (bornes incluses, séquencement strict) :
  submit  : création < H <= submit_until          (state OPEN)
  reveal  : submit_until < H <= reveal_until      (state SCORING)
  commit notes : reveal_until < H <= commit_score_until
  reveal notes : commit_score_until < H <= reveal_score_until
"""

from arena_chain.canonical import tagged_hash
from arena_chain.errors import InvalidTx
from arena_chain.params import (
    BUILD_WINDOW,
    COMMIT_SCORE_WINDOW,
    JUDGE_RESERVE_PCT,
    K_BUILDERS,
    MAX_BRIEF_LEN,
    MAX_CONTENT_LEN,
    MAX_TASK_ID_LEN,
    MIN_JUDGES,
    MIN_PRICE,
    REVEAL_SCORE_WINDOW,
    REVEAL_SOL_WINDOW,
    SALT_MAX_LEN,
    SALT_MIN_LEN,
    SCALE,
    SLASH_PLAGIARISM_PCT,
)
from arena_chain.slashing import jail, slash
from arena_chain.sortition import select_builders, sortition_seed
from arena_chain.split import split
from arena_chain.state import BLOCK_END_HOOKS, HANDLERS, State
from arena_chain.yuma import yuma_consensus

SOLUTION_COMMIT_TAG = "agentarena/commit/solution/v1"
SCORES_COMMIT_TAG = "agentarena/commit/scores/v1"


def solution_commit(task_id: str, builder: str, content: str, salt: str) -> str:
    """Commit d'un rendu, lié au builder et à la task (un commit ne se copie pas)."""
    return tagged_hash(
        SOLUTION_COMMIT_TAG,
        {"task": task_id, "builder": builder, "content": content, "salt": salt},
    )


def scores_commit(task_id: str, judge: str, scores: dict[str, int], salt: str) -> str:
    return tagged_hash(
        SCORES_COMMIT_TAG, {"task": task_id, "judge": judge, "scores": scores, "salt": salt}
    )


def eligible_agents(state: State, height: int, exclude: tuple[str, ...] = ()) -> list[str]:
    return [
        addr
        for addr, agent in sorted(state.data["agents"].items())
        if agent["jailed_until"] <= height and addr not in exclude
    ]


def revealed_builders(state: State, task_id: str) -> list[str]:
    task = state.data["tasks"][task_id]
    return sorted(
        addr
        for addr in task["builders"]
        if state.data["submissions"].get(f"{task_id}|{addr}", {}).get("status") == "REVEAL_OK"
    )


# --- garde-fous communs ---


def _height(state: State) -> int:
    if state.ctx_height is None:
        raise InvalidTx("tx de manche hors contexte de bloc")
    return state.ctx_height


def _require_str(payload: dict, field: str, max_len: int, min_len: int = 1) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not (min_len <= len(value) <= max_len):
        raise InvalidTx(f"champ {field} invalide")
    return value


def _require_salt(payload: dict) -> str:
    return _require_str(payload, "salt", SALT_MAX_LEN, SALT_MIN_LEN)


def _task(state: State, payload: dict) -> tuple[str, dict]:
    task_id = _require_str(payload, "task", MAX_TASK_ID_LEN)
    task = state.data["tasks"].get(task_id)
    if task is None:
        raise InvalidTx(f"task inconnue: {task_id}")
    return task_id, task


def _not_jailed(state: State, addr: str, height: int) -> None:
    agent = state.data["agents"].get(addr)
    if agent is None or agent["jailed_until"] > height:
        raise InvalidTx(f"agent absent ou jailed: {addr}")


# --- handlers de tx ---


def _apply_create_task(state: State, tx: dict) -> None:
    height = _height(state)
    payload = tx["payload"]
    task_id = _require_str(payload, "task", MAX_TASK_ID_LEN)
    brief = _require_str(payload, "brief", MAX_BRIEF_LEN)
    prize = payload.get("prize")
    if type(prize) is not int or prize < MIN_PRICE:
        raise InvalidTx(f"prize < MIN_PRICE {MIN_PRICE} (correctif audit)")
    if task_id in state.data["tasks"]:
        raise InvalidTx(f"task deja existante: {task_id}")
    sponsor = tx["sender"]
    eligibles = eligible_agents(state, height, exclude=(sponsor,))
    if len(eligibles) < K_BUILDERS + MIN_JUDGES:
        raise InvalidTx(
            f"pool insuffisant: {len(eligibles)} agents pour {K_BUILDERS}+{MIN_JUDGES} requis"
        )
    state.debit(sponsor, prize)  # escrow : le prix est verrouille dans la task
    seed = sortition_seed(state.ctx_prev_hash, task_id)
    builders, judges = select_builders(seed, eligibles, K_BUILDERS)
    state.data["tasks"][task_id] = {
        "sponsor": sponsor,
        "prize": prize,
        "brief": brief,
        "state": "OPEN",
        "builders": builders,
        "judges": judges,
        "submit_until": height + BUILD_WINDOW,
        "reveal_until": height + BUILD_WINDOW + REVEAL_SOL_WINDOW,
        "commit_score_until": height + BUILD_WINDOW + REVEAL_SOL_WINDOW + COMMIT_SCORE_WINDOW,
        "reveal_score_until": height
        + BUILD_WINDOW
        + REVEAL_SOL_WINDOW
        + COMMIT_SCORE_WINDOW
        + REVEAL_SCORE_WINDOW,
        "slashed": [],
        "result": None,
    }


def _apply_submit_solution(state: State, tx: dict) -> None:
    height = _height(state)
    task_id, task = _task(state, tx["payload"])
    commit = _require_str(tx["payload"], "commit", 64, 64)
    builder = tx["sender"]
    if task["state"] != "OPEN" or height > task["submit_until"]:
        raise InvalidTx("fenetre de submit fermee")
    if builder not in task["builders"]:
        raise InvalidTx("sender n'est pas un builder designe de cette task")
    _not_jailed(state, builder, height)
    key = f"{task_id}|{builder}"
    if key in state.data["submissions"]:
        raise InvalidTx("commit deja depose (commit unique)")
    state.data["submissions"][key] = {
        "commit": commit,
        "content": None,
        "height": height,
        "status": "COMMITTED",
    }


def _apply_reveal_solution(state: State, tx: dict) -> None:
    height = _height(state)
    task_id, task = _task(state, tx["payload"])
    content = _require_str(tx["payload"], "content", MAX_CONTENT_LEN)
    salt = _require_salt(tx["payload"])
    builder = tx["sender"]
    if task["state"] != "SCORING" or height > task["reveal_until"]:
        raise InvalidTx("fenetre de reveal fermee")
    submission = state.data["submissions"].get(f"{task_id}|{builder}")
    if submission is None or submission["status"] != "COMMITTED":
        raise InvalidTx("aucun commit en attente de reveal")
    if solution_commit(task_id, builder, content, salt) != submission["commit"]:
        submission["status"] = "MISMATCH"  # enregistre, traite comme no-show a la deadline
        return
    submission["content"] = content
    submission["status"] = "REVEAL_OK"


def _apply_commit_scores(state: State, tx: dict) -> None:
    height = _height(state)
    task_id, task = _task(state, tx["payload"])
    commit = _require_str(tx["payload"], "commit", 64, 64)
    judge = tx["sender"]
    if task["state"] != "SCORING" or not (
        task["reveal_until"] < height <= task["commit_score_until"]
    ):
        raise InvalidTx("fenetre de commit des notes fermee")
    if judge not in task["judges"]:
        raise InvalidTx("sender n'est pas un juge designe de cette task")
    _not_jailed(state, judge, height)
    key = f"{task_id}|{judge}"
    if key in state.data["scores"]:
        raise InvalidTx("commit de notes deja depose (commit unique)")
    state.data["scores"][key] = {"commit": commit, "scores": None, "status": "COMMITTED"}


def _apply_reveal_scores(state: State, tx: dict) -> None:
    height = _height(state)
    task_id, task = _task(state, tx["payload"])
    salt = _require_salt(tx["payload"])
    judge = tx["sender"]
    if task["state"] != "SCORING" or not (
        task["commit_score_until"] < height <= task["reveal_score_until"]
    ):
        raise InvalidTx("fenetre de reveal des notes fermee")
    record = state.data["scores"].get(f"{task_id}|{judge}")
    if record is None or record["status"] != "COMMITTED":
        raise InvalidTx("aucun commit de notes en attente de reveal")
    scores = tx["payload"].get("scores")
    if not isinstance(scores, dict):
        raise InvalidTx("scores absents")
    if scores_commit(task_id, judge, scores, salt) != record["commit"]:
        record["status"] = "MISMATCH"
        return
    targets = revealed_builders(state, task_id)
    if sorted(scores) != targets:
        raise InvalidTx("les notes doivent couvrir exactement les rendus reveles")
    for value in scores.values():
        if type(value) is not int or not (0 <= value <= SCALE):
            raise InvalidTx("note hors bornes [0, SCALE]")
    if sum(scores.values()) != SCALE:
        raise InvalidTx("somme des notes != SCALE (strict)")
    record["scores"] = scores
    record["status"] = "REVEAL_OK"


def _apply_slash_proof(state: State, tx: dict) -> None:
    """Plagiat : contenus révélés identiques, le plus tardif est fautif.

    La chronologie on-chain (hauteur du commit) départage ; à hauteur égale on
    ne peut pas prouver qui a copié, la preuve est rejetée. Le double-sign BFT
    arrive avec le consensus (étape 5).
    """
    _height(state)
    payload = tx["payload"]
    if payload.get("kind") != "plagiarism":
        raise InvalidTx(f"kind de preuve inconnu: {payload.get('kind')}")
    task_id, task = _task(state, payload)
    accused = _require_str(payload, "accused", 64)
    earlier = _require_str(payload, "earlier", 64)
    if accused == earlier or accused not in task["builders"] or earlier not in task["builders"]:
        raise InvalidTx("accuse et temoin doivent etre deux builders de la task")
    if accused in task["slashed"]:
        raise InvalidTx("deja slashe pour cette task")
    sub_accused = state.data["submissions"].get(f"{task_id}|{accused}")
    sub_earlier = state.data["submissions"].get(f"{task_id}|{earlier}")
    if (
        sub_accused is None
        or sub_earlier is None
        or sub_accused["status"] != "REVEAL_OK"
        or sub_earlier["status"] != "REVEAL_OK"
    ):
        raise InvalidTx("les deux rendus doivent etre reveles")
    if sub_accused["content"] != sub_earlier["content"]:
        raise InvalidTx("contenus differents: pas de plagiat prouvable")
    if sub_accused["height"] <= sub_earlier["height"]:
        raise InvalidTx("chronologie non prouvante (l'accuse n'est pas le plus tardif)")
    slash(state, accused, SLASH_PLAGIARISM_PCT, reporter=tx["sender"])
    task["slashed"].append(accused)


# --- transitions automatiques de fin de bloc ---


def _end_submit_window(state: State, task_id: str, task: dict, height: int) -> None:
    committed = [
        addr for addr in task["builders"] if f"{task_id}|{addr}" in state.data["submissions"]
    ]
    for addr in sorted(set(task["builders"]) - set(committed)):
        jail(state, addr, height)  # no-show de commit
    if committed:
        task["state"] = "SCORING"
    else:
        _abort(state, task, "no_submission")


def _end_reveal_window(state: State, task_id: str, task: dict, height: int) -> None:
    for addr in sorted(task["builders"]):
        submission = state.data["submissions"].get(f"{task_id}|{addr}")
        if submission is not None and submission["status"] != "REVEAL_OK":
            jail(state, addr, height)  # commit sans reveal, ou reveal mismatch
    if not revealed_builders(state, task_id):
        _abort(state, task, "no_reveal")


def _end_scoring_window(state: State, task_id: str, task: dict, height: int) -> None:
    valid_judges = sorted(
        addr
        for addr in task["judges"]
        if state.data["scores"].get(f"{task_id}|{addr}", {}).get("status") == "REVEAL_OK"
    )
    for addr in sorted(set(task["judges"]) - set(valid_judges)):
        jail(state, addr, height)  # juge no-show (pas de commit, pas de reveal, ou mismatch)
    if valid_judges:
        _settle(state, task_id, task, valid_judges)
    else:
        _abort(state, task, "no_scores")


def _abort(state: State, task: dict, reason: str) -> None:
    state.credit(task["sponsor"], task["prize"])  # l'escrow ne reste jamais bloque
    task["state"] = "SETTLED"
    task["result"] = {"aborted": reason}


def _settle(state: State, task_id: str, task: dict, valid_judges: list[str]) -> None:
    """Règlement Yuma : 100% déterministe, rejoué à l'identique par tous les nodes."""
    builders = revealed_builders(state, task_id)
    weights = [
        [state.data["scores"][f"{task_id}|{judge}"]["scores"][b] for b in builders]
        for judge in valid_judges
    ]
    stakes = [
        state.data["stakes"][judge]["free"] + state.data["stakes"][judge]["locked"]
        for judge in valid_judges
    ]
    if sum(stakes) == 0:
        _abort(state, task, "no_judge_stake")
        return
    bonds_prev = [
        [state.data["bonds"].get(f"{judge}|{b}", 0) for b in builders] for judge in valid_judges
    ]
    result = yuma_consensus(weights, stakes, bonds_prev)

    judge_reserve = task["prize"] * JUDGE_RESERVE_PCT // 100
    builders_pot = task["prize"] - judge_reserve
    builder_payouts = dict.fromkeys(builders, 0)
    judge_payouts = dict.fromkeys(valid_judges, 0)
    refund = 0
    if sum(result["incentive"]) > 0:
        for addr, amount in zip(builders, split(builders_pot, result["incentive"])):
            builder_payouts[addr] = amount
            state.credit(addr, amount)
    else:
        refund += builders_pot  # cas degenere sumR==0 : jamais d'escrow bloque
    if sum(result["dividends"]) > 0:
        for addr, amount in zip(valid_judges, split(judge_reserve, result["dividends"])):
            judge_payouts[addr] = amount
            state.credit(addr, amount)
    else:
        refund += judge_reserve
    if refund:
        state.credit(task["sponsor"], refund)

    for i, judge in enumerate(valid_judges):
        for j, builder in enumerate(builders):
            state.data["bonds"][f"{judge}|{builder}"] = result["bonds"][i][j]

    task["state"] = "SETTLED"
    task["result"] = {
        "builders": builders,
        "judges": valid_judges,
        "consensus": result["consensus"],
        "incentive": result["incentive"],
        "dividends": result["dividends"],
        "payouts": {"builders": builder_payouts, "judges": judge_payouts},
    }


def on_block_end(state: State) -> None:
    height = state.ctx_height
    for task_id, task in sorted(state.data["tasks"].items()):
        if task["state"] == "OPEN" and height == task["submit_until"]:
            _end_submit_window(state, task_id, task, height)
        elif task["state"] == "SCORING" and height == task["reveal_until"]:
            _end_reveal_window(state, task_id, task, height)
        elif task["state"] == "SCORING" and height == task["reveal_score_until"]:
            _end_scoring_window(state, task_id, task, height)


HANDLERS.update(
    {
        "create_task": _apply_create_task,
        "submit_solution": _apply_submit_solution,
        "reveal_solution": _apply_reveal_solution,
        "commit_scores": _apply_commit_scores,
        "reveal_scores": _apply_reveal_scores,
        "slash_proof": _apply_slash_proof,
    }
)

if on_block_end not in BLOCK_END_HOOKS:
    BLOCK_END_HOOKS.append(on_block_end)
