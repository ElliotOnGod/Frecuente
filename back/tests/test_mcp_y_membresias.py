"""Servidor MCP (herramientas para agentes de IA), código del día y salud."""

import pytest

from conftest import ErrorGraphQL

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def rpc(cliente, metodo, params=None, token=None):
    headers = dict(HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = cliente.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": metodo, "params": params or {}}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def llamar(cliente, herramienta, argumentos=None, token=None):
    return rpc(cliente, "tools/call", {"name": herramienta, "arguments": argumentos or {}}, token)["result"]


def datos(resultado):
    """Lo que regresó la herramienta (estructurado o como texto JSON)."""
    import json

    if "structuredContent" in resultado:
        contenido = resultado["structuredContent"]
        return contenido.get("result", contenido)
    return json.loads(resultado["content"][0]["text"])


def test_mcp_lista_herramientas(cliente):
    nombres = {t["name"] for t in rpc(cliente, "tools/list")["result"]["tools"]}
    assert {"buscar_productos", "cotizar_envio", "estado_de_pedido", "resumen_de_ventas"} <= nombres


def test_mcp_busca_productos_por_metodo(cliente):
    r = llamar(cliente, "buscar_productos", {"metodo": "batido"})
    assert not r.get("isError")
    nombres = {p["nombre"] for p in datos(r)}
    assert nombres == {"Matcha ceremonial 50 g", "Premezcla matcha latte 200 g"}


def test_mcp_herramientas_de_admin_piden_token(cliente, token_admin, token_cliente):
    assert llamar(cliente, "resumen_de_ventas")["isError"] is True
    assert llamar(cliente, "resumen_de_ventas", token=token_cliente)["isError"] is True
    r = llamar(cliente, "resumen_de_ventas", {"dias": 30}, token=token_admin)
    assert not r.get("isError") and datos(r)["ventas_mxn"] > 0


def test_codigo_del_dia_cambia_cada_dia_y_no_se_adivina():
    from schema import CODIGO_RE, codigo_canje

    hoy = codigo_canje(12, "2026-11-08")
    assert CODIGO_RE.match(hoy) and hoy.startswith("FM12-")
    assert codigo_canje(12, "2026-11-09") != hoy
    assert codigo_canje(13, "2026-11-08") != hoy
    assert codigo_canje(12, "2026-11-08") == hoy


def test_salud_revisa_las_dos_bases(cliente):
    assert cliente.get("/salud").json() == {"ok": True, "mongo": "ok", "postgres": "ok"}


@pytest.mark.parametrize("consulta", ["{ integraciones { clave modo } }", "{ correosAdmin { id } }", "{ suscripcionesAdmin { id } }"])
def test_consultas_de_admin_cerradas_para_clientes(gql, token_cliente, consulta):
    with pytest.raises(ErrorGraphQL, match="administrador"):
        gql(consulta, token=token_cliente)


def test_integraciones_son_al_menos_cinco(gql, token_admin):
    integraciones = gql("{ integraciones { clave modo } }", token=token_admin)["integraciones"]
    assert len(integraciones) >= 5
    assert {"mercadopago", "paypal", "envia", "brevo", "openfreemap"} <= {i["clave"] for i in integraciones}


def test_websocket_de_tiempo_real_acepta_otro_origen(cliente, token_admin):
    """El front (Netlify) y el backend (Render) son orígenes distintos:
    el WebSocket de las Subscriptions debe aceptar la conexión."""
    with cliente.websocket_connect(
        "/graphql", subprotocols=["graphql-transport-ws"], headers={"origin": "https://frecuente.netlify.app"}
    ) as ws:
        ws.send_json({"type": "connection_init", "payload": {"Authorization": f"Bearer {token_admin}"}})
        assert ws.receive_json()["type"] == "connection_ack"
        ws.send_json({"id": "1", "type": "subscribe", "payload": {"query": "subscription { eventosAdmin { tipo mensaje } }"}})
        mensaje = ws.receive_json()
        assert mensaje["type"] == "next" and mensaje["payload"]["data"]["eventosAdmin"]["tipo"] == "conectado"
