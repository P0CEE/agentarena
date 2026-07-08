"""Paramètres du protocole.

Immuables : leur hash sera fixé dans le genesis (étape 4). Deux seuils à ne
jamais confondre : le quorum BFT (>2/3 du stake, finalité des blocs) et le
kappa Yuma (1/2, médiane du scoring) — constantes séparées à dessein.
"""

SCALE = 10**9  # fixed-point : 1.0 == 1_000_000_000

BFT_QUORUM_NUM = 2
BFT_QUORUM_DEN = 3

MIN_STAKE = 1_000  # stake minimal d'un agent, reellement debite (correctif audit)
MIN_PRICE = 10 * MIN_STAKE  # prix minimal d'une task, rejette le spam (correctif audit)
