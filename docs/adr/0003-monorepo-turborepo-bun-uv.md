# Monorepo Turborepo + Bun orchestrant des packages Python (uv)

Le repo mélange une chaîne Python et un dashboard TypeScript. Nous avons choisi Turborepo + Bun à la racine (workspaces, pipeline build/test/lint/dev) alors que la majorité du code est en Python — un lecteur pourrait s'attendre à un simple Makefile ou à un workspace uv seul. Raison : le monorepo « à packages » orchestré est un objectif d'apprentissage explicite du projet, et Turbo donne le cache et le graphe de tâches pour les deux mondes.

## Consequences

- Les packages Python (`chain`, `node`, `agents`, `cli`) sont gérés par un workspace uv, et chacun expose un petit `package.json` dont les scripts délèguent à `uv run ...` pour que Turbo puisse les piloter.
- Bun est le package manager et le runtime des scripts TS ; le dashboard (Vite + React) vit dans `apps/dashboard`.
