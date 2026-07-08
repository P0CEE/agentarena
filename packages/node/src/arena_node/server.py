"""Serveur FastAPI d'un node : P2P entre nodes + API de lecture + SSE dashboard."""

import asyncio
import contextlib
import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from arena_chain.errors import ChainError

from arena_node.engine import Engine


def create_app(engine: Engine, run_engine: bool = False) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(engine.run()) if run_engine else None
        yield
        if task is not None:
            task.cancel()

    app = FastAPI(title="agentarena-node", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    # --- ecriture ---

    @app.post("/tx")
    async def post_tx(request: Request) -> dict:
        try:
            tid = await engine.handle_tx(await request.json())
        except ChainError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"txid": tid}

    # --- P2P (fire-and-forget entre nodes) ---

    @app.post("/consensus/proposal")
    async def post_proposal(request: Request) -> dict:
        await engine.handle_proposal(await request.json())
        return {"ok": True}

    @app.post("/consensus/vote")
    async def post_vote(request: Request) -> dict:
        await engine.handle_vote(await request.json())
        return {"ok": True}

    @app.post("/consensus/timeout")
    async def post_timeout(request: Request) -> dict:
        await engine.handle_timeout(await request.json())
        return {"ok": True}

    # --- lecture (dashboard, CLI, catch-up) ---

    @app.get("/status")
    async def status() -> dict:
        agents = engine.state.data["agents"]
        me = agents.get(engine.wallet.address, {})
        return {
            "address": engine.wallet.address,
            "height": engine.height,
            "round": engine.round,
            "mempool": len(engine.mempool),
            "peers": len(engine.peers),
            "validators": len(engine.validators()),
            "jailed_until": me.get("jailed_until", 0),
            "proposer_next": engine.is_proposer(),
        }

    @app.get("/blocks")
    async def blocks(request: Request) -> dict:
        start = int(request.query_params.get("from", 0))
        return {"blocks": engine.blocks[start:]}

    @app.get("/chain")
    async def chain(request: Request) -> dict:
        limit = int(request.query_params.get("limit", 50))
        headers = [entry["block"]["header"] for entry in engine.blocks[-limit:]]
        return {"headers": headers}

    @app.get("/tasks")
    async def tasks() -> dict:
        return {"tasks": engine.state.data["tasks"]}

    @app.get("/tasks/{task_id}")
    async def task_detail(task_id: str) -> dict:
        task = engine.state.data["tasks"].get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task inconnue")
        prefix = f"{task_id}|"
        return {
            "task": task,
            "submissions": {
                key.removeprefix(prefix): value
                for key, value in engine.state.data["submissions"].items()
                if key.startswith(prefix)
            },
            "scores": {
                key.removeprefix(prefix): value
                for key, value in engine.state.data["scores"].items()
                if key.startswith(prefix)
            },
        }

    @app.get("/agents")
    async def agents() -> dict:
        data = engine.state.data
        return {
            "agents": {
                addr: agent | data["stakes"].get(addr, {"free": 0, "locked": 0})
                for addr, agent in data["agents"].items()
            }
        }

    @app.get("/events")
    async def events() -> EventSourceResponse:
        queue = engine.subscribe()

        async def stream():
            try:
                while True:
                    event = await queue.get()
                    yield {"event": event["type"], "data": json.dumps(event)}
            finally:
                engine.unsubscribe(queue)

        return EventSourceResponse(stream())

    return app
