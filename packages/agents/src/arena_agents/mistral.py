"""Agent Mistral : le vrai LLM derrière chaque node (ADR-0001).

Une seule clé (MISTRAL_API_KEY), un modèle éco. Le juge reçoit les rendus
anonymisés (A, B, C...) pour ne pas être biaisé par les adresses, et répond en
JSON avec des notes 0-100. Tout échec (timeout, API, JSON illisible) lève
AgentError -> no-show -> jail avec grâce.
"""

import asyncio
import json
from string import ascii_uppercase

from mistralai.client import Mistral

from arena_chain.params import MAX_CONTENT_LEN

from arena_agents.base import AgentError

BUILDER_SYSTEM = (
    "Tu es un agent builder sur AgentArena, une blockchain ou des agents IA "
    "produisent des livrables en competition. Reponds UNIQUEMENT avec le livrable "
    "demande par le brief, sans preambule ni conclusion. Sois concis et de qualite : "
    "des juges noteront ton rendu face a ceux des autres builders."
)

JUDGE_SYSTEM = (
    "Tu es un agent juge sur AgentArena. On te donne un brief et des rendus anonymises. "
    "Evalue la qualite de chaque rendu par rapport au brief (correction, completude, "
    "clarte). Reponds UNIQUEMENT avec un objet JSON associant chaque lettre a une note "
    'entiere de 0 a 100, par exemple {"A": 80, "B": 45, "C": 60}. Aucun autre texte.'
)

MAX_SUBMISSION_CHARS = 4_000  # tronque ce que voit le juge, pas ce qui est on-chain


class MistralAgent:
    def __init__(
        self,
        api_key: str,
        model: str = "mistral-small-latest",
        timeout_s: float = 30.0,
    ) -> None:
        self._client = Mistral(api_key=api_key)
        self.model = model
        self.timeout_s = timeout_s

    async def build(self, task_id: str, brief: str) -> str:
        content = await self._complete(BUILDER_SYSTEM, brief)
        return content[:MAX_CONTENT_LEN]

    async def judge(
        self, task_id: str, brief: str, submissions: dict[str, str]
    ) -> dict[str, int]:
        addresses = sorted(submissions)
        labels = dict(zip(ascii_uppercase, addresses))
        parts = [f"Brief:\n{brief}"]
        parts += [
            f"### Rendu {label}\n{submissions[addr][:MAX_SUBMISSION_CHARS]}"
            for label, addr in labels.items()
        ]
        text = await self._complete(JUDGE_SYSTEM, "\n\n".join(parts))
        grades = parse_grades(text, list(labels))
        return {labels[label]: grade for label, grade in grades.items()}

    async def _complete(self, system: str, user: str) -> str:
        try:
            response = await asyncio.wait_for(
                self._client.chat.complete_async(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                ),
                self.timeout_s,
            )
        except Exception as exc:
            raise AgentError(f"appel Mistral en echec: {exc}") from exc
        content = response.choices[0].message.content if response.choices else None
        if not isinstance(content, str) or not content.strip():
            raise AgentError("reponse Mistral vide")
        return content


def parse_grades(text: str, labels: list[str]) -> dict[str, int]:
    """Extrait le JSON de notes d'une réponse LLM (tolère le texte autour)."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise AgentError("pas de JSON dans la reponse du juge")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AgentError(f"JSON de notes illisible: {exc}") from exc
    if not isinstance(data, dict):
        raise AgentError("le JSON de notes n'est pas un objet")
    grades = {}
    for label in labels:
        value = data.get(label)
        grades[label] = max(0, int(value)) if isinstance(value, int | float) else 0
    if sum(grades.values()) == 0:
        grades = dict.fromkeys(labels, 1)  # tout le monde a zero -> egalite
    return grades
