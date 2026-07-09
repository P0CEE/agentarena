"""Genesis : bloc 0, pré-généré et identique pour tous les nodes.

Jamais généré dynamiquement par un node (divergence dès le bloc 0) : le CLI le
construit une fois, chaque node le charge tel quel.
"""

from arena_chain.block import GENESIS_PREV, make_block, make_header, tx_root
from arena_chain.state import State


def make_genesis(
    allocations: dict[str, int], agents: dict[str, int] | None = None, timestamp: int = 0
) -> tuple[State, dict]:
    """Construit le state initial et le bloc 0 : soldes + validateurs initiaux.

    Le timestamp vient de la config (fixé à la création du réseau) : la même valeur
    pour tous les nodes, sinon divergence dès le bloc 0.
    """
    state = State.from_allocations(allocations, agents)
    header = make_header(0, GENESIS_PREV, "genesis", 0, tx_root([]), state.root(), timestamp)
    return state, make_block(header, [])
