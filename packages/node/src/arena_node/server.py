"""Serveur FastAPI d'un node : P2P entre nodes + API de lecture + SSE dashboard."""

import asyncio
import contextlib
import json
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from arena_chain.block import block_hash
from arena_chain.errors import ChainError
from arena_chain.tx import make_tx
from arena_chain.wallet import Wallet

from arena_node.engine import Engine


def create_app(
    engine: Engine,
    run_engine: bool = False,
    agent_runner=None,
    sponsor_wallet: Wallet | None = None,
) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        tasks = []
        if run_engine:
            tasks.append(asyncio.create_task(engine.run()))
            if agent_runner is not None:
                tasks.append(asyncio.create_task(agent_runner.run()))
        yield
        for task in tasks:
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

    # --- sponsor (node de reference uniquement : il detient le wallet sponsor) ---

    if sponsor_wallet is not None:

        @app.post("/sponsor/tasks")
        async def sponsor_create_task(request: Request) -> dict:
            body = await request.json()
            task_id = f"task-{secrets.token_hex(3)}"
            account = engine.state.data["accounts"].get(sponsor_wallet.address, {"nonce": 0})
            pending = sum(
                1 for tx in engine.mempool.values() if tx["sender"] == sponsor_wallet.address
            )
            tx = make_tx(
                sponsor_wallet,
                account["nonce"] + pending,
                {
                    "type": "create_task",
                    "task": task_id,
                    "prize": body.get("prize", 0),
                    "brief": str(body.get("brief", "")).strip(),
                },
            )
            # Validation immediate sur un clone : une tx invalide (prix trop bas,
            # pool insuffisant) est refusee en 400 au lieu d'etre silencieusement
            # abandonnee au seal.
            probe = engine.state.clone()
            probe.begin_block(engine.next_height, block_hash(engine.last_header))
            try:
                probe.apply_tx(tx)
                await engine.handle_tx(tx)
            except ChainError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {"task": task_id}

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
            "peers": list(engine.peers),
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

    @app.get("/accounts/{addr}")
    async def account(addr: str) -> dict:
        return dict(engine.state.data["accounts"].get(addr, {"balance": 0, "nonce": 0}))

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
