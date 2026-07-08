"""Agent stub : déterministe, instantané, sans réseau. Pour les tests (ADR-0001)."""

from arena_chain.canonical import tagged_hash

STUB_TAG = "agentarena/stub/judge/v1"


class StubAgent:
    def __init__(self, address: str) -> None:
        self.address = address

    async def build(self, task_id: str, brief: str) -> str:
        return (
            f"Solution deterministe de l'agent {self.address[:8]} "
            f"pour la task {task_id}: {brief[:60]}"
        )

    async def judge(
        self, task_id: str, brief: str, submissions: dict[str, str]
    ) -> dict[str, int]:
        # Poids pseudo-aleatoires mais deterministes, propres a CE juge :
        # deux juges stub ne donnent pas les memes notes (diversite).
        return {
            builder: 1
            + int(
                tagged_hash(
                    STUB_TAG, {"judge": self.address, "task": task_id, "builder": builder}
                )[:8],
                16,
            )
            % 100
            for builder in sorted(submissions)
        }
