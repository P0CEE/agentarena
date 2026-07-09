import httpx

from arena_cli import monitor
from arena_cli.theme import console

BASE = 18200


def _network(nodes: int = 3) -> dict:
    return {"nodes": [
        {"name": f"node-{i}", "port": BASE + i, "url": f"http://127.0.0.1:{BASE + i}"}
        for i in range(nodes)
    ]}


def _client(down_ports: set[int] = frozenset()) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        port = request.url.port
        if port in down_ports:
            raise httpx.ConnectError("down")
        return httpx.Response(200, json={
            "height": 10 + (port - BASE),
            "round": 1,
            "mempool": port - BASE,
            "proposer_next": port == BASE,
        })
    return httpx.Client(transport=httpx.MockTransport(handler))


def _render(frame) -> str:
    with console.capture() as capture:
        console.print(frame)
    return capture.get()


def test_poll_marque_down_sans_casser_les_autres() -> None:
    with _client(down_ports={BASE + 1}) as client:
        rows = monitor.poll_nodes(client, _network())
    assert [row["up"] for row in rows] == [True, False, True]
    assert rows[0] == {"name": "node-0", "port": BASE, "up": True,
                       "height": 10, "round": 1, "mempool": 0, "proposer": True}
    assert rows[1]["name"] == "node-1"  # present malgre le down


def test_frame_entete_nodes_et_proposer() -> None:
    with _client(down_ports={BASE + 1}) as client:
        rows = monitor.poll_nodes(client, _network())
    text = _render(monitor.build_frame(rows, "http://localhost:5173"))
    # entete : hauteur max des nodes up, compte des up, url du dashboard
    assert "RÉSEAU · h=12 · round 1 · 2/3 up" in text
    assert "http://localhost:5173" in text
    # un node par ligne, le down marque sans casser le reste
    assert "node-1" in text and "○" in text and "down" in text
    assert text.count("●") == 2
    assert "▸ proposer" in [line for line in text.splitlines() if "node-0" in line][0]


def test_frame_sans_dashboard_ni_node_up() -> None:
    rows = [{"name": "node-0", "port": BASE, "up": False,
             "height": 0, "round": 0, "mempool": 0, "proposer": False}]
    text = _render(monitor.build_frame(rows))
    assert "0/1 up" in text
    assert "dashboard" not in text
