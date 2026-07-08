"""Sanctions : slash (perte de capital, faute prouvable) et jail (liveness).

Trois régimes à ne pas confondre (ADR-0004) : SLASH = confiscation partielle
pour faute objectivement prouvable ; JAIL = suspension temporaire, capital
intact, grâce au premier incident puis durée escaladante ; CLIPPING = note
minoritaire écrêtée par Yuma, jamais sanctionnée.
"""

from arena_chain.errors import InvalidTx
from arena_chain.params import BOUNTY_PCT, JAIL_BASE, OFFENSE_FORGET_WINDOW
from arena_chain.state import State


def slash(state: State, accused: str, pct: int, reporter: str) -> int:
    """Confisque pct% du stake total (free + locked) de l'accusé.

    Le dénonciateur touche BOUNTY_PCT% du montant slashé (jamais 100% : sinon
    pompe a extraction entre complices, cf. audit) ; le reste va au treasury.
    Retourne le montant slashé.
    """
    stakes = state.data["stakes"].get(accused)
    if stakes is None:
        raise InvalidTx(f"accuse sans stake: {accused}")
    amount = (stakes["free"] + stakes["locked"]) * pct // 100
    if amount == 0:
        raise InvalidTx("stake nul, rien a slasher")
    from_free = min(amount, stakes["free"])
    stakes["free"] -= from_free
    stakes["locked"] -= amount - from_free
    bounty = amount * BOUNTY_PCT // 100
    state.credit(reporter, bounty)
    state.data["treasury"] += amount - bounty
    return amount


def jail(state: State, addr: str, height: int) -> None:
    """Enregistre une offense de liveness (no-show).

    Grâce au premier incident dans la fenêtre d'oubli ; ensuite la durée de
    jail double à chaque offense : JAIL_BASE * 2^(offenses - 2).
    """
    agent = state.data["agents"][addr]
    if height - agent["last_offense"] > OFFENSE_FORGET_WINDOW:
        agent["offenses"] = 0
    agent["offenses"] += 1
    agent["last_offense"] = height
    if agent["offenses"] >= 2:
        agent["jailed_until"] = height + JAIL_BASE * 2 ** (agent["offenses"] - 2)
