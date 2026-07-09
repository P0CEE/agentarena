"""Proposer pondéré, votes, quorum, QC, double-sign."""

from collections import Counter

import pytest
from conftest import AGENTS, REPORTER, net_with_agents

from arena_chain.block import block_hash
from arena_chain.consensus import (
    check_double_sign,
    make_vote,
    proposer_for,
    quorum,
    validators_of,
    verify_qc,
    verify_vote,
)
from arena_chain.errors import InvalidBlock, InvalidTx
from arena_chain.params import DOUBLESIGN_JAIL_BLOCKS, SLASH_DOUBLESIGN_PCT
from arena_chain.wallet import Wallet

V = [Wallet.from_seed(bytes([200 + i]) * 32) for i in range(4)]
EQUAL = {w.address: 10_000 for w in V}


def test_proposer_rotation_equitable_stakes_egaux() -> None:
    seen = Counter(proposer_for(EQUAL, step) for step in range(1, 5))
    assert set(seen) == set(EQUAL)  # chacun propose exactement une fois par cycle
    assert all(count == 1 for count in seen.values())


def test_proposer_pondere_par_le_stake() -> None:
    weighted = {V[0].address: 20_000, V[1].address: 10_000}
    seen = Counter(proposer_for(weighted, step) for step in range(1, 31))
    assert seen[V[0].address] == 20  # 2x le stake -> 2x les propositions
    assert seen[V[1].address] == 10


def test_proposer_deterministe() -> None:
    assert proposer_for(EQUAL, 7) == proposer_for(dict(reversed(EQUAL.items())), 7)


def test_vote_roundtrip_et_alteration() -> None:
    vote = make_vote(V[0], 5, 0, "a" * 64)
    assert verify_vote(vote) == V[0].address
    vote["block_hash"] = "b" * 64
    with pytest.raises(InvalidTx):
        verify_vote(vote)


def test_quorum_strictement_superieur_a_deux_tiers() -> None:
    voters3 = [w.address for w in V[:3]]
    assert quorum(EQUAL, voters3)  # 3/4 > 2/3
    assert not quorum(EQUAL, voters3[:2])  # 2/4 < 2/3
    three = {w.address: 1 for w in V[:3]}
    assert not quorum(three, [V[0].address, V[1].address])  # exactement 2/3 : rejete


def test_verify_qc() -> None:
    header = {"height": 1, "round": 0, "proposer": V[0].address,
              "prev_hash": "0" * 64, "tx_root": "0" * 64, "state_root": "0" * 64,
              "timestamp": 1}
    hash_ = block_hash(header)
    votes = {w.address: make_vote(w, 1, 0, hash_) for w in V[:3]}
    verify_qc(EQUAL, header, hash_, votes)  # passe

    with pytest.raises(InvalidBlock, match="quorum"):
        verify_qc(EQUAL, header, hash_, {V[0].address: votes[V[0].address]})

    wrong = {w.address: make_vote(w, 1, 0, "f" * 64) for w in V[:3]}
    with pytest.raises(InvalidBlock, match="autre bloc"):
        verify_qc(EQUAL, header, hash_, wrong)


def test_double_sign_detecte() -> None:
    vote_a = make_vote(V[0], 3, 1, "a" * 64)
    vote_b = make_vote(V[0], 3, 1, "b" * 64)
    assert check_double_sign(vote_a, vote_b) == V[0].address


def test_revote_a_un_autre_round_licite() -> None:
    vote_a = make_vote(V[0], 3, 0, "a" * 64)
    vote_b = make_vote(V[0], 3, 1, "b" * 64)
    with pytest.raises(InvalidTx, match="round"):
        check_double_sign(vote_a, vote_b)


def test_meme_bloc_deux_fois_licite() -> None:
    vote = make_vote(V[0], 3, 1, "a" * 64)
    with pytest.raises(InvalidTx, match="meme bloc"):
        check_double_sign(vote, dict(vote))


def test_slash_double_sign_via_tx() -> None:
    net = net_with_agents()
    equivocator = AGENTS[0]
    proof = {
        "type": "slash_proof",
        "kind": "double_sign",
        "vote_a": make_vote(equivocator, 9, 0, "a" * 64),
        "vote_b": make_vote(equivocator, 9, 0, "b" * 64),
    }
    stake_avant = net.state.data["stakes"][equivocator.address]
    total_avant = stake_avant["free"] + stake_avant["locked"]

    block = net.tick([net.send(REPORTER, proof)])

    stake_apres = net.state.data["stakes"][equivocator.address]
    slashed = total_avant * SLASH_DOUBLESIGN_PCT // 100
    assert stake_apres["free"] + stake_apres["locked"] == total_avant - slashed
    # Jail court SANS grace : faute de surete, pas de liveness.
    jailed_until = net.state.data["agents"][equivocator.address]["jailed_until"]
    assert jailed_until == block["header"]["height"] + DOUBLESIGN_JAIL_BLOCKS
    # Idempotent : la meme preuve ne se rejoue pas.
    import pytest as _pytest

    with _pytest.raises(InvalidTx, match="deja slashee"):
        net.tick([net.build(REPORTER, proof)])


def test_validators_of_exclut_stake_nul() -> None:
    net = net_with_agents()
    validators = validators_of(net.state)
    assert set(validators) == {w.address for w in AGENTS}
    net.state.data["stakes"][AGENTS[0].address] = {"free": 0, "locked": 0}
    assert AGENTS[0].address not in validators_of(net.state)
