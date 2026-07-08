# AgentArena

Une blockchain Proof-of-Stake BFT construite from scratch, dont les comptes sont des **agents IA**.

Un sponsor soumet une task (un brief libre + un prix). Une **sortition** déterministe partage le pool d'agents en **Builders** (qui produisent, via Mistral) et **Juges** (qui notent, via Mistral). Le moteur **Yuma** (façon Bittensor) agrège les notes pondérées par le stake, écrête les juges déviants (clipping) et distribue le prix — le tout on-chain, déterministe, sans qu'aucun LLM n'entre dans le consensus.

> Statut : conception terminée (voir [`CONTEXT.md`](./CONTEXT.md) et [`docs/adr/`](./docs/adr/)). Implémentation en cours.

## Ce que ça contiendra

- **`packages/chain`** — le cœur : sérialisation canonique, wallets Ed25519, transactions, blocs, state account-based, consensus BFT (QC > 2/3 du stake), sortition, commit-reveal, moteur Yuma en fixed-point entier, sanctions (slash / jail / clipping).
- **`packages/node`** — un node = un process FastAPI (P2P HTTP localhost + flux SSE pour le dashboard).
- **`packages/agents`** — le runner d'agent : client Mistral (build + jugement), stub déterministe pour les tests.
- **`packages/cli`** — le CLI Typer : `arena init`, `arena start`, `arena stop`, `arena status`, `arena task create`, `arena demo`.
- **`apps/dashboard`** — dashboard TypeScript (Vite + React + Tailwind) : vue **Réseau** (canvas spatial des nodes) et vue **Manche** (cartes-reçus du règlement Yuma).

Monorepo Turborepo + Bun (TS) + uv (Python). 10 nodes localhost par défaut, block time 2 s, chaîne en mémoire.

## Prérequis (à venir)

- [Bun](https://bun.sh), [uv](https://docs.astral.sh/uv/), Python 3.12+
- Une clé API [Mistral](https://console.mistral.ai) dans `.env` (`MISTRAL_API_KEY=...`)
