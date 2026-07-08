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

## 5. Consensus BFT + nodes (`packages/node`) ✅

- [x] `consensus.py` (chain) — proposer round-robin pondéré stake (algo Tendermint), votes signés, QC strictement > 2/3 du stake (2/3 pile rejeté), pacemaker par quorum de timeouts (compteur logique)
- [x] Vérificateur de double-sign + slash 7% + jail court SANS grâce (faute de sûreté), idempotent
- [x] Genesis avec agents pré-enregistrés (le set de validateurs initial — résout l'œuf-et-la-poule du bloc 1)
- [x] `packages/node` : Engine asyncio avec transport injectable (HTTP en prod, direct en tests), mempool revalidé au seal, gossip idempotent
- [x] Serveur FastAPI : POST /tx /consensus/*, GET /status /blocks /chain /tasks /tasks/{id} /agents, CORS pour le dashboard
- [x] Flux SSE /events (nouveau bloc, transitions de manche)
- [x] Catch-up : validation de chaque bloc ET de son QC (un peer menteur est abandonné)
- [x] Limite assumée (README) : un seul tour de vote, pas les 3 phases HotStuff — sûr tant qu'un node honnête vote une fois par (hauteur, round), le double-vote étant slashable

**Sortie** : ✅ testé en transport direct (1 mort sur 4 → timeout, round suivant, ça continue ; 2 morts → halt, la sûreté avant la liveness ; catch-up exact) + smoke test réel : 4 process uvicorn localhost finalisent en synchro (h=16 à 6 s, h=24 à 9 s, block_time 0.3 s). (105 tests chain + 10 node)

## 6. Agents Mistral (`packages/agents`) ✅

- [x] Interface `Agent` (build, judge) + stub déterministe pour les tests (ADR-0001) — les agents rendent des poids bruts, le runner normalise en vecteur protocolaire (somme == SCALE, via split exact)
- [x] Client Mistral (clé unique `MISTRAL_API_KEY`, `mistral-small-latest`) : prompts builder et juge, rendus anonymisés (A, B, C) côté juge, parsing JSON tolérant
- [x] Timeout/erreur Mistral → pas de tx → no-show → jail (avec grâce) — testé avec un builder dont le LLM tombe en panne : la manche aboutit avec les 2 autres
- [x] `AgentRunner` : observe la chaîne et joue le rôle assigné aux bonnes fenêtres (build → commit → reveal → judge → notes), appels LLM en tâches de fond, nonces auto-gérés
- [x] Câblage node : `config.agent.kind` (stub | mistral), runner lancé avec l'engine

**Sortie** : ✅ e2e : 10 nodes + 10 runners jouent une manche entière en totale autonomie (3 rendus, 7 vecteurs de notes, règlement Yuma, state_root identique partout). Les tests passent sans réseau (stub). ⏳ La manche « vrais appels Mistral » attend une `MISTRAL_API_KEY` dans `.env` (code prêt, smoke à l'étape 7 via le CLI). (105+14+12 tests)

## 7. CLI (`packages/cli`) ✅

- [x] `arena init` — genesis (10 agents pré-enregistrés, stakes égaux), wallets, sponsor financé ; `--agent auto|stub|mistral` (auto = mistral si `MISTRAL_API_KEY` trouvée dans `.env`), `--nodes`, `--block-time`, `--base-port`, `--force`
- [x] `arena start` / `arena stop` — process détachés (`python -m arena_node`), pids + logs dans `.arena/`, redémarrage idempotent
- [x] `arena status` — table hauteur/round/mempool/proposer par node, tolère les nodes down
- [x] `arena task create` — tx signée par le sponsor (nonce lu via `GET /accounts/{addr}`), `--watch` optionnel
- [x] `arena demo` — manche de bout en bout avec suivi live (état, rendus, notes, hauteur) et affichage du règlement Yuma

**Sortie** : ✅ vérifié en réel : `arena init && arena start && arena demo` sur 10 process localhost — sortition (3 builders / 7 juges), commits, reveals, notes, SETTLED à h=55, paiements exacts (40 000 builders + 10 000 juges). (137 tests)

## 8. Dashboard (`apps/dashboard`) ✅

- [x] Vue **Réseau** : canvas spatial (@xyflow/react), agents en cercle autour du centre-chaîne (écran sombre, hauteur en gros), fils pointillés vers le centre, badges proposer (olive, fil animé) / jailed / rôle builder-juge de la manche active
- [x] Vue **Manche** : cartes-reçus punaisées et inclinées (task → rendus → notes des juges en mini-barres → règlement Yuma), contenus scellés en ▓▓▓ avant reveal, tampons d'état (scellé/révélé/mismatch), barre de phases avec fenêtres
- [x] SSE `/events` du node de référence + refetch de `/status` de chaque node (peers exposés en liste dans /status)
- [x] Composer sponsor : POST `/sponsor/tasks` — le node de référence détient le wallet sponsor (seed dans sa config via `arena init`) et valide la tx sur un clone avant de l'accepter (erreurs en 400, pas de drop silencieux)
- [x] Direction visuelle : « atelier papier » — fond grain, IBM Plex Mono (reçus) + Instrument Serif (titres), palette olive/ambre/violet des références, fonts bundlées (offline)

**Sortie** : ✅ pipeline de données vérifié en réel (composer → manche jouée par les agents → règlement affiché) ; build TypeScript strict OK. `bun run dev` dans `apps/dashboard` (ou `turbo run dev`) avec le réseau lancé pour la voir vivre. (138 tests)

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
