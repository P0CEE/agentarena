# Roadmap

Les étapes dans l'ordre. Chaque étape a un critère de sortie testable — on ne passe pas à la suivante tant qu'il n'est pas vert. L'ordre n'est pas négociable sur un point : Yuma et la sortition (étape 3) avant le réseau, parce que ce sont eux qui portent les golden tests de déterminisme.

## 1. Squelette du monorepo ✅

- [x] Racine Turborepo + Bun (workspaces `apps/*`, `packages/*`)
- [x] Workspace uv avec 4 packages Python : `chain`, `node`, `agents`, `cli`
- [x] Dashboard Vite + React + Tailwind vide dans `apps/dashboard`
- [x] `package.json` par package Python déléguant à `uv run` (pytest, ruff)

**Sortie** : `bun run test` (turbo) exécute les tests de tous les packages et passe. ✅

## 2. Fondations chaîne (`packages/chain`) ✅

- [x] `canonical.py` — sérialisation canonique unique (sort_keys, ascii, entiers only) + test de déterminisme
- [x] `wallet.py` — Ed25519 (PyNaCl), adresse = sha256(pubkey) tronqué
- [x] `tx.py` — tx signée, `txid` sur les signing bytes, signature jamais dans le hash
- [x] `block.py` — header (height, prev_hash, proposer, round, tx_root, state_root), hash sans signatures
- [x] `state.py` — account-based `{balance, nonce}` + stake **réellement débité** par `register_agent` (correctif audit)
- [x] Faucet supprimé par design : les soldes viennent uniquement des allocations du genesis (correctif audit, plus fort que le plafonnement)
- [x] `MIN_PRICE` défini dans `params.py` — appliqué par `create_task` à l'étape 4 (correctif audit)

**Sortie** : sign/verify OK, txid stable, altérer un bloc casse la chaîne, apply_block déterministe. ✅ (40 tests)

## 3. Moteur économique ✅

- [x] `yuma.py` — fixed-point int (SCALE=1e9), médiane pondérée stake, clipping, rank, incentive, bonds EMA, dividends
- [x] Golden test obligatoire : `C=[0.6,0.3,0.1]`, `I=[0.566,0.313,0.120]`*, `D=[0.602,0.325,0.072]` (V3 le tricheur clippé), rejouable 1000x = hash identique
- [x] `split.py` — largest remainder, invariant `sum(payouts) == prize` exact
- [x] `sortition.py` — partition Builders/Juges déterministe, seed = hash du dernier bloc finalisé, sponsor exclu, builder ≠ juge
- [x] Cas dégénérés couverts : `sumR==0`, 1 juge, égalités de médiane (tie-break canonique), stakes strictement égaux

\* Les notes d'origine annonçaient `I₃=0.121` ; l'algorithme fixed-point exact donne `120_481_928` (0.120), et `sum(I) == SCALE` exactement.

**Sortie** : golden tests verts, deux instances calculent la même partition et le même règlement. ✅ (72 tests)

## 4. Machine à manche (`arena.py`) ✅

- [x] Machine à états OPEN → SCORING → SETTLED, transitions dans `on_block_end` (déviation assumée : le règlement est automatique à la clôture de la dernière fenêtre — pas de tx de crank ni d'état d'attente CONSENSUS)
- [x] Fenêtres en hauteurs de bloc (BUILD=20, REVEAL=10, COMMIT_SCORE=10, REVEAL_SCORE=10)
- [x] Commit-reveal : sel ≥128 bits + domain separator liant task et auteur (un commit ne se copie pas), commit unique, états COMMITTED / REVEAL_OK / MISMATCH
- [x] Escrow du prix + réserve juges 20% + toute manche vide remboursée au sponsor (jamais d'escrow bloqué)
- [x] Sanctions noyau calibré : slash plagiat 40% + chronologie on-chain, bounty 15% au dénonciateur (reste au treasury), jail escaladant avec grâce et fenêtre d'oubli, clipping (ADR-0004). Double-sign 7% : le vérificateur arrive avec le format des votes BFT (étape 5)
- [x] `params.py` unique, `params_hash()` écrit dans le state du genesis (des params différents ⇒ divergence au bloc 0)

**Sortie** : une manche complète en mémoire, du create_task au règlement, rejouable 2x identique + replay des blocs sur un node frais. ✅ (94 tests)

## 5. Consensus BFT + nodes (`packages/node`)

- [ ] `consensus.py` — proposer round-robin pondéré stake, votes, QC > 2/3 du stake, pacemaker (compteur logique)
- [ ] Node FastAPI : POST /tx /vote /block, GET /chain /status /tasks, gossip idempotent
- [ ] Flux SSE (nouveau bloc, transitions de manche, règlements)
- [ ] Catch-up d'un node en retard (validation de chaque bloc)
- [ ] Block time 2 s, chaîne en mémoire (ADR-0002)

**Sortie** : 4 nodes localhost finalisent des blocs ; 1 node coupé sur 4 → ça continue ; 2 coupés → ça s'arrête (comportement BFT correct).

## 6. Agents Mistral (`packages/agents`)

- [ ] Interface `Agent` (build, judge) + stub déterministe pour les tests (ADR-0001)
- [ ] Client Mistral (clé unique `MISTRAL_API_KEY`, modèle éco), prompts builder et juge
- [ ] Timeout/erreur Mistral → no-show → jail (avec grâce)

**Sortie** : une manche avec vrais appels Mistral aboutit ; les tests passent sans réseau (stub).

## 7. CLI (`packages/cli`)

- [ ] `arena init` — genesis (10 agents, stakes égaux), wallets, wallet sponsor financé
- [ ] `arena start` / `arena stop` — lance/arrête les process nodes
- [ ] `arena status` — hauteur, proposer, état des nodes
- [ ] `arena task create` — soumet une task signée par le sponsor
- [ ] `arena demo` — une manche scriptée de bout en bout

**Sortie** : `arena init && arena start && arena demo` fonctionne depuis un clone frais.

## 8. Dashboard (`apps/dashboard`)

- [ ] Vue **Réseau** : canvas spatial (@xyflow/react), 10 agents autour du centre-chaîne, badges proposer/jailed/rôle, side panel composer « créer une task »
- [ ] Vue **Manche** : cartes-reçus reliées (task → rendus → notes → règlement Yuma avec montants)
- [ ] SSE du node de référence + poll léger `/status` par node
- [ ] Création de task depuis le composer (POST, signature déléguée au node de référence)

**Sortie** : on voit une manche vivre en temps réel du brief au paiement.

## 9. README final

- [ ] Architecture (2 couches : off-chain LLM / on-chain déterministe) avec schéma
- [ ] Mode d'emploi complet (installation → démo)
- [ ] Limites assumées : <16 agents, capture 51%, free-riding des juges (pas de honesty-probe), pas de persistance

**Sortie** : quelqu'un qui clone le repo comprend et fait tourner le projet sans aide.

## Hors périmètre (coupé volontairement)

- DISPUTE / challenger bond
- Honesty-probe et dividend-penalty (ADR-0004)
- Persistance disque (ADR-0002)
- Multi-provider LLM (ADR-0001)
- Mode hybride à vérité objective
