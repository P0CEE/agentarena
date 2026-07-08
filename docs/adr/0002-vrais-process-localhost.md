# Nodes = vrais process localhost, pas une simulation en mémoire

Les notes de conception proposaient un MVP avec BFT simulé dans un seul process (plus simple, 100 % reproductible). Nous avons choisi l'inverse : chaque node est un vrai process Python (FastAPI, ports localhost) lancé et arrêté par le CLI, parce que le cœur de la demande est « un CLI qui crée les nodes » et un dashboard qui les regarde vivre. Le déterminisme du consensus est garanti par le design (fixed-point, deadlines en hauteurs, ordre canonique des tx), pas par le fait de tourner dans un seul process.

## Consequences

- La chaîne vit en mémoire le temps des process : `stop` puis `start` repart du genesis (pas de persistance disque, décision assumée pour un projet démo).
- Les tests d'intégration du consensus utilisent les mêmes classes en mémoire, sans process ni réseau.
