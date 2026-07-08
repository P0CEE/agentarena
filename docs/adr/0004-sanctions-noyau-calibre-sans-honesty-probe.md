# Sanctions : noyau calibré de l'audit, sans honesty-probe ni dividend-penalty

L'audit du design a montré que le clipping seul rend le free-riding des juges gratuit, et recommandait deux mécanismes correctifs lourds : le honesty-probe (tâches pièges à vérité connue) et la dividend-penalty plafonnée. Nous implémentons le noyau calibré — slash plagiat 40 % avec preuve de chronologie, slash double-signature 7 %, jail escaladant avec grâce au premier no-show, clipping Yuma, réserve juges de 20 % du prix — et nous sautons délibérément honesty-probe et dividend-penalty pour rester dans le budget de complexité d'un projet étudiant.

## Consequences

- Le free-riding des juges reste économiquement possible sous 50 % du stake : limite connue, documentée dans le README (héritée de Bittensor), pas un oubli.
- Les constantes vivent dans un `params.py` unique dont le hash est fixé au genesis ; réintroduire les deux mécanismes plus tard est une évolution, pas une refonte.
