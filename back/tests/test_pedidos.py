"""Checkout: precios del servidor, stock atómico con compensación, pagos idempotentes."""

import threading

import pytest

from conftest import ErrorGraphQL

REGISTRAR = """mutation($i:PedidoInput!){ registrarPedido(input:$i){
  id estado subtotal costoEnvio total suscripcionId
  items{ productoId nombre variante cantidad precioUnit }
  pago{ metodo estado } entrega{ tipo costo guia } } }"""
CONFIRMAR = "mutation($i:ConfirmarPagoInput!){ confirmarPago(input:$i){ id estado pago{ estado pagoId } } }"


def pedir(gql, token, items, metodo="mercadopago", **extra):
    return gql(REGISTRAR, {"i": {"items": items, "metodoPago": metodo, **extra}}, token=token)["registrarPedido"]


def test_el_total_lo_calcula_el_servidor_y_descuenta_stock(gql, nuevo_cliente, stock):
    token, _ = nuevo_cliente()
    antes = stock(4)
    p = pedir(gql, token, [{"productoId": 4, "cantidad": 2}, {"productoId": 4, "cantidad": 1}])
    assert p["estado"] == "registrado" and p["pago"]["estado"] == "pendiente"
    assert p["items"] == [{"productoId": 4, "nombre": "Leche entera 1 L", "variante": "", "cantidad": 3, "precioUnit": 34.0}]
    assert p["total"] == p["subtotal"] == 102.0 and p["entrega"]["tipo"] == "recoger"
    assert stock(4) == antes - 3


def test_variante_por_defecto_y_variante_invalida(gql, nuevo_cliente):
    token, _ = nuevo_cliente()
    p = pedir(gql, token, [{"productoId": 1, "cantidad": 1}, {"productoId": 1, "cantidad": 1, "variante": "Molido para espresso"}])
    assert sorted(i["variante"] for i in p["items"]) == ["Grano entero", "Molido para espresso"]
    with pytest.raises(ErrorGraphQL, match="no viene en"):
        pedir(gql, token, [{"productoId": 1, "cantidad": 1, "variante": "Molido para microondas"}])


def test_sin_stock_no_se_descuenta_nada_compensacion(gql, nuevo_cliente, stock):
    token, _ = nuevo_cliente()
    stock.fijar(7, 1)
    antes = stock(5)
    with pytest.raises(ErrorGraphQL, match="Stock insuficiente"):
        pedir(gql, token, [{"productoId": 5, "cantidad": 2}, {"productoId": 7, "cantidad": 5}])
    assert stock(5) == antes and stock(7) == 1
    stock.fijar(7, 12)


def test_dos_compras_al_mismo_tiempo_no_venden_la_misma_pieza(gql, nuevo_cliente, stock):
    tokens = [nuevo_cliente()[0] for _ in range(6)]
    stock.fijar(9, 1)
    resultados = []

    def comprar(t):
        try:
            pedir(gql, t, [{"productoId": 9, "cantidad": 1}])
            resultados.append("ok")
        except ErrorGraphQL:
            resultados.append("sin stock")

    hilos = [threading.Thread(target=comprar, args=(t,)) for t in tokens]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert resultados.count("ok") == 1 and stock(9) == 0
    stock.fijar(9, 9)


def test_pago_simulado_aprobado_es_idempotente_y_avisa_por_correo(gql, nuevo_cliente):
    import relacional

    token, usuario = nuevo_cliente()
    p = pedir(gql, token, [{"productoId": 6, "cantidad": 1}])
    url = gql("mutation($id:Int!){ iniciarPago(pedidoId:$id){ url } }", {"id": p["id"]}, token=token)["iniciarPago"]["url"]
    assert url == f"/pago/simulado?pedido={p['id']}"
    r1 = gql(CONFIRMAR, {"i": {"pedidoId": p["id"], "simulacion": "aprobado"}}, token=token)["confirmarPago"]
    r2 = gql(CONFIRMAR, {"i": {"pedidoId": p["id"], "simulacion": "rechazado"}}, token=token)["confirmarPago"]
    assert r1["estado"] == r2["estado"] == "pagado" and r2["pago"]["estado"] == "aprobado"
    plantillas = [c["plantilla"] for c in relacional.correos_recientes(50) if c["pedido_id"] == p["id"]]
    assert plantillas.count("pedido_confirmado") == 1 and "pedido_nuevo_tienda" in plantillas


def test_cancelar_regresa_el_stock_una_sola_vez(gql, nuevo_cliente, stock):
    token, _ = nuevo_cliente()
    antes = stock(8)
    p = pedir(gql, token, [{"productoId": 8, "cantidad": 2}])
    m = "mutation($id:Int!){ cancelarMiPedido(id:$id){ estado } }"
    assert gql(m, {"id": p["id"]}, token=token)["cancelarMiPedido"]["estado"] == "cancelado"
    with pytest.raises(ErrorGraphQL):
        gql(m, {"id": p["id"]}, token=token)
    assert stock(8) == antes


def test_un_cliente_no_ve_pedidos_ajenos(gql, nuevo_cliente):
    t1, _ = nuevo_cliente()
    t2, _ = nuevo_cliente()
    p = pedir(gql, t1, [{"productoId": 4, "cantidad": 1}])
    assert gql("query($id:Int!){ pedido(id:$id){ id } }", {"id": p["id"]}, token=t2)["pedido"] is None


def test_panel_resumen_sale_de_postgres(gql, token_admin):
    r = gql(
        "{ resumenAdmin(dias: 30){ ventasTotal pedidosPagados ventasPorDia{ fecha } porEstado{ estado pedidos }"
        " topProductos{ nombre piezas } recomprasActivas } }",
        token=token_admin,
    )["resumenAdmin"]
    assert len(r["ventasPorDia"]) == 30 and r["ventasTotal"] > 0 and r["topProductos"]
    pagina = gql('{ pedidosAdmin(estado:"por_cobrar", limite:5){ total pedidos{ id estado } } }', token=token_admin)["pedidosAdmin"]
    assert all(p["estado"] == "registrado" for p in pagina["pedidos"])
