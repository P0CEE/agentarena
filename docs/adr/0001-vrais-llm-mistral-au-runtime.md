# Vrais LLM (Mistral) au runtime, stub uniquement pour les tests

Les notes de conception recommandaient des stubs seedés pour ne jamais dépendre d'un appel LLM live — mais ce garde-fou visait une soutenance qui n'existe pas ici. Nous avons décidé que les agents (Builders et Juges) appellent réellement l'API Mistral au runtime (clé unique `MISTRAL_API_KEY`, modèle éco, pas d'abstraction multi-provider), parce que c'est l'esprit même du projet. La sûreté du consensus n'en dépend pas : le LLM vit off-chain, seuls des hash et des vecteurs de notes entiers entrent on-chain.

## Consequences

- Les tests (pytest, CI) ne doivent jamais appeler Mistral : l'interface `Agent` a une implémentation stub déterministe injectée dans les tests.
- Le rythme de bloc (2 s) et les fenêtres en hauteurs sont dimensionnés pour laisser le temps aux appels LLM (~40 s de build).
- Un timeout ou une erreur Mistral se traduit par un no-show de l'agent → jail avec grâce, comportement déjà prévu par le protocole.
