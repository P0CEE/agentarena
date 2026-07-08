"""Consensus BFT simplifié : proposer pondéré, votes, Quorum Certificate.

Un seul tour de vote par bloc (pas les 3 phases HotStuff) : la sûreté tient
tant que chaque node honnête vote au plus une fois par (hauteur, round) et que
le quorum est STRICTEMENT > 2/3 du stake — deux blocs distincts ne peuvent pas
tous deux atteindre le quorum sans qu'un votant ait signé deux fois (faute de
double-sign, slashable). Limite assumée pour un réseau localhost fiable,
documentée dans le README.

Les validateurs sont les agents du state (voting power = stake total). Un agent
jailed reste validateur : le jail est une sanction de manche, pas de consensus.
"""

from arena_chain.canonical import tagged_hash
from arena_chain.errors import InvalidBlock, InvalidTx
from arena_chain.params import BFT_QUORUM_DEN, BFT_QUORUM_NUM
from arena_chain.state import State
from arena_chain.tx import PUBKEY_HEX_LEN
from arena_chain.wallet import Wallet, address_of, verify_signature

VOTE_TAG = "agentarena/vote/v1"
TIMEOUT_TAG = "agentarena/timeout/v1"


def validators_of(state: State) -> dict[str, int]:
    """Adresse -> voting power (stake free + locked), agents a stake nul exclus."""
    stakes = state.data["stakes"]
    result = {}
    for addr in sorted(state.data["agents"]):
        power = stakes.get(addr, {"free": 0, "locked": 0})
        total = power["free"] + power["locked"]
        if total > 0:
            result[addr] = total
    return result


def quorum(validators: dict[str, int], voters) -> bool:
    """STRICTEMENT > 2/3 du stake — exactement 2/3 est rejeté."""
    voted = sum(validators.get(v, 0) for v in set(voters))
    total = sum(validators.values())
    return voted * BFT_QUORUM_DEN > total * BFT_QUORUM_NUM


def proposer_for(validators: dict[str, int], step: int) -> str:
    """Round-robin pondéré déterministe (algo Tendermint). step = hauteur + round.

    Chaque validateur propose à une fréquence proportionnelle à son stake ;
    tie-break canonique par adresse. Calculé localement par tous les nodes.
    """
    if not validators:
        raise ValueError("aucun validateur")
    if step < 1:
        raise ValueError("step >= 1 requis")
    accum = dict.fromkeys(sorted(validators), 0)
    total = sum(validators.values())
    chosen = ""
    for _ in range(step):
        for addr in accum:
            accum[addr] += validators[addr]
        chosen = min(accum, key=lambda addr: (-accum[addr], addr))
        accum[chosen] -= total
    return chosen


# --- votes ---


def _message_digest(tag: str, body: dict) -> bytes:
    return bytes.fromhex(tagged_hash(tag, body))


def _vote_body(height: int, round_: int, block_hash: str, voter: str) -> dict:
    return {"height": height, "round": round_, "block_hash": block_hash, "voter": voter}


def make_vote(wallet: Wallet, height: int, round_: int, block_hash: str) -> dict:
    body = _vote_body(height, round_, block_hash, wallet.address)
    return body | {
        "pubkey": wallet.pubkey.hex(),
        "signature": wallet.sign(_message_digest(VOTE_TAG, body)),
    }


def _verify_signed(message: dict, tag: str, fields: tuple[str, ...]) -> str:
    if not isinstance(message, dict) or set(message) != {*fields, "pubkey", "signature"}:
        raise InvalidTx("message de consensus mal forme")
    if not isinstance(message["pubkey"], str) or len(message["pubkey"]) != PUBKEY_HEX_LEN:
        raise InvalidTx("pubkey invalide")
    pubkey = bytes.fromhex(message["pubkey"])
    if address_of(pubkey) != message["voter"]:
        raise InvalidTx("le pubkey ne correspond pas au voter")
    body = {field: message[field] for field in fields}
    if not verify_signature(pubkey, _message_digest(tag, body), message["signature"]):
        raise InvalidTx("signature de consensus invalide")
    return message["voter"]


def verify_vote(vote: dict) -> str:
    return _verify_signed(vote, VOTE_TAG, ("height", "round", "block_hash", "voter"))


def make_timeout(wallet: Wallet, height: int, round_: int) -> dict:
    body = {"height": height, "round": round_, "voter": wallet.address}
    return body | {
        "pubkey": wallet.pubkey.hex(),
        "signature": wallet.sign(_message_digest(TIMEOUT_TAG, body)),
    }


def verify_timeout(message: dict) -> str:
    return _verify_signed(message, TIMEOUT_TAG, ("height", "round", "voter"))


def verify_qc(validators: dict[str, int], header: dict, block_hash_: str, votes: dict) -> None:
    """Vérifie un Quorum Certificate lors d'un catch-up : signatures + quorum."""
    for voter, vote in sorted(votes.items()):
        if verify_vote(vote) != voter or voter not in validators:
            raise InvalidBlock(f"vote de QC invalide: {voter}")
        if (
            vote["height"] != header["height"]
            or vote["round"] != header["round"]
            or vote["block_hash"] != block_hash_
        ):
            raise InvalidBlock("vote de QC pour un autre bloc")
    if not quorum(validators, votes):
        raise InvalidBlock("QC sous le quorum de 2/3 du stake")


def check_double_sign(vote_a: dict, vote_b: dict) -> str:
    """Preuve d'équivocation : deux votes valides, même (hauteur, round), blocs différents."""
    voter = verify_vote(vote_a)
    if verify_vote(vote_b) != voter:
        raise InvalidTx("les deux votes ne viennent pas du meme voter")
    if vote_a["height"] != vote_b["height"] or vote_a["round"] != vote_b["round"]:
        raise InvalidTx("hauteur/round differents: revoter n'est pas une faute")
    if vote_a["block_hash"] == vote_b["block_hash"]:
        raise InvalidTx("meme bloc signe deux fois: pas une equivocation")
    return voter
