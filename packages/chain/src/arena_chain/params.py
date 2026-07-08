"""Paramètres du protocole.

Immuables : leur hash (params_hash) est écrit dans le state du genesis — deux
nodes avec des paramètres différents divergent dès le bloc 0, par construction.
Deux seuils à ne jamais confondre : le quorum BFT (>2/3 du stake, finalité des
blocs) et le kappa Yuma (1/2, médiane du scoring) — constantes séparées à dessein.
"""

from arena_chain.canonical import tagged_hash

SCALE = 10**9  # fixed-point : 1.0 == 1_000_000_000

BFT_QUORUM_NUM = 2
BFT_QUORUM_DEN = 3

KAPPA = SCALE // 2  # seuil de la mediane ponderee Yuma (0.5) — PAS le quorum BFT
ALPHA_BONDS_NUM = 1  # EMA des bonds : B = (1*dB + 9*B_prev) // 10
ALPHA_BONDS_DEN = 10

MIN_STAKE = 1_000  # stake minimal d'un agent, reellement debite (correctif audit)
MIN_PRICE = 10 * MIN_STAKE  # prix minimal d'une task, rejette le spam (correctif audit)

# --- sortition / pool ---
K_BUILDERS = 3
MIN_JUDGES = 7  # impair : interdit le juge dictateur

# --- fenetres d'une manche, en hauteurs de bloc (sequencement strict) ---
BUILD_WINDOW = 20
REVEAL_SOL_WINDOW = 10
COMMIT_SCORE_WINDOW = 10
REVEAL_SCORE_WINDOW = 10

# --- economie de la manche ---
JUDGE_RESERVE_PCT = 20  # part du prix reservee aux juges AVANT le split builders

# --- sanctions (noyau calibre par l'audit, voir ADR-0004) ---
SLASH_PLAGIARISM_PCT = 40  # jamais 100% : faux positifs ruineux sur code trivial
SLASH_DOUBLESIGN_PCT = 7
BOUNTY_PCT = 15  # part du montant slashe versee au denonciateur, le reste au treasury
JAIL_BASE = 5  # blocs ; grace au 1er incident puis base * 2^(offenses - 2)
OFFENSE_FORGET_WINDOW = 1_000  # fenetre d'oubli des offenses, en blocs
DOUBLESIGN_JAIL_BLOCKS = 20  # jail court SANS grace : le double-sign est une faute de surete

# --- bornes anti-bloat du state ---
MAX_TASK_ID_LEN = 64
MAX_BRIEF_LEN = 4_000
MAX_CONTENT_LEN = 20_000
SALT_MIN_LEN = 32  # 128 bits en hex
SALT_MAX_LEN = 128

BLOCK_TIME_S = 2  # rythme cible de production (parametre reseau, hors consensus)


def params_hash() -> str:
    """Hash canonique de tous les paramètres, fixé dans le state du genesis."""
    return tagged_hash(
        "agentarena/params/v1",
        {
            "SCALE": SCALE,
            "BFT_QUORUM_NUM": BFT_QUORUM_NUM,
            "BFT_QUORUM_DEN": BFT_QUORUM_DEN,
            "KAPPA": KAPPA,
            "ALPHA_BONDS_NUM": ALPHA_BONDS_NUM,
            "ALPHA_BONDS_DEN": ALPHA_BONDS_DEN,
            "MIN_STAKE": MIN_STAKE,
            "MIN_PRICE": MIN_PRICE,
            "K_BUILDERS": K_BUILDERS,
            "MIN_JUDGES": MIN_JUDGES,
            "BUILD_WINDOW": BUILD_WINDOW,
            "REVEAL_SOL_WINDOW": REVEAL_SOL_WINDOW,
            "COMMIT_SCORE_WINDOW": COMMIT_SCORE_WINDOW,
            "REVEAL_SCORE_WINDOW": REVEAL_SCORE_WINDOW,
            "JUDGE_RESERVE_PCT": JUDGE_RESERVE_PCT,
            "SLASH_PLAGIARISM_PCT": SLASH_PLAGIARISM_PCT,
            "SLASH_DOUBLESIGN_PCT": SLASH_DOUBLESIGN_PCT,
            "BOUNTY_PCT": BOUNTY_PCT,
            "JAIL_BASE": JAIL_BASE,
            "OFFENSE_FORGET_WINDOW": OFFENSE_FORGET_WINDOW,
            "DOUBLESIGN_JAIL_BLOCKS": DOUBLESIGN_JAIL_BLOCKS,
            "MAX_TASK_ID_LEN": MAX_TASK_ID_LEN,
            "MAX_BRIEF_LEN": MAX_BRIEF_LEN,
            "MAX_CONTENT_LEN": MAX_CONTENT_LEN,
            "SALT_MIN_LEN": SALT_MIN_LEN,
            "SALT_MAX_LEN": SALT_MAX_LEN,
        },
    )
