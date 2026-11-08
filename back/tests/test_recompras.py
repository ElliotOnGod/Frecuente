"""Suscripción de recompra: el pedido se repite solo cada N días."""

from datetime import date, timedelta

import pytest

from conftest import ErrorGraphQL

REGISTRAR = "mutation($i:PedidoInput!){ registrarPedido(input:$i){ id suscripcionId } }"
MIS = "{ misSuscripciones { id estado cadaDias proxima items{ productoId variante cantidad } pedidos{ id } totalEstimado } }"


def test_recompra_genera_el_pedido_cuando_le_toca(gql, nuevo_cliente):
    import relacional
    from schema import procesar_recompras

    token, usuario = nuevo_cliente()
    items = [{"productoId": 1, "cantidad": 1, "variante": "Molido para espresso"}]
    p = gql(REGISTRAR, {"i": {"items": items, "metodoPago": "mercadopago", "recompraCadaDias": 30}}, token=token)["registrarPedido"]
    s = gql(MIS, token=token)["misSuscripciones"][0]
    assert p["suscripcionId"] == s["id"] and s["cadaDias"] == 30
    assert s["proxima"] == (date.today() + timedelta(days=30)).isoformat()
    assert s["items"] == [{"productoId": 1, "variante": "Molido para espresso", "cantidad": 1}]

    procesar_recompras(date.today())                       # todavía no le toca
    assert len(gql(MIS, token=token)["misSuscripciones"][0]["pedidos"]) == 1

    procesar_recompras(date.today() + timedelta(days=30))
    s = gql(MIS, token=token)["misSuscripciones"][0]
    assert len(s["pedidos"]) == 2
    assert s["proxima"] == (date.today() + timedelta(days=60)).isoformat()
    # Volver a correr el mismo día no duplica
    procesar_recompras(date.today() + timedelta(days=30))
    assert len(gql(MIS, token=token)["misSuscripciones"][0]["pedidos"]) == 2
    assert any(c["plantilla"] == "recompra_lista" and c["destinatario"] == usuario["email"]
               for c in relacional.correos_recientes(50))


def test_pausada_no_genera_y_cancelada_no_revive(gql, nuevo_cliente):
    from schema import procesar_recompras

    token, _ = nuevo_cliente()
    gql(REGISTRAR, {"i": {"items": [{"productoId": 5, "cantidad": 1}], "metodoPago": "paypal", "recompraCadaDias": 15}}, token=token)
    sid = gql(MIS, token=token)["misSuscripciones"][0]["id"]
    cambiar = "mutation($id:Int!,$e:String){ cambiarMiSuscripcion(id:$id, estado:$e){ estado } }"
    gql(cambiar, {"id": sid, "e": "pausada"}, token=token)
    procesar_recompras(date.today() + timedelta(days=15))
    assert len(gql(MIS, token=token)["misSuscripciones"][0]["pedidos"]) == 1
    gql(cambiar, {"id": sid, "e": "cancelada"}, token=token)
    with pytest.raises(ErrorGraphQL, match="cancelada"):
        gql(cambiar, {"id": sid, "e": "activa"}, token=token)


def test_recompra_valida_frecuencia_y_metodo(gql, nuevo_cliente):
    token, _ = nuevo_cliente()
    item = [{"productoId": 5, "cantidad": 1}]
    with pytest.raises(ErrorGraphQL, match="15, 30 o 60"):
        gql(REGISTRAR, {"i": {"items": item, "recompraCadaDias": 7}}, token=token)
    with pytest.raises(ErrorGraphQL, match="efectivo"):
        gql(REGISTRAR, {"i": {"items": item, "metodoPago": "efectivo", "recompraCadaDias": 30}}, token=token)


def test_endpoint_de_cron_pide_la_clave(cliente):
    assert cliente.post("/tareas/recompras").status_code == 401
    r = cliente.post("/tareas/recompras", headers={"X-Cron-Secret": "cron-de-pruebas"})
    assert r.status_code == 200 and r.json()["ok"] is True
