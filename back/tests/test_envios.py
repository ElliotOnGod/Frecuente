"""Envia.com (modo simulado): cotización firmada, dirección, guía y rastreo."""

import pytest

from conftest import ErrorGraphQL

COTIZAR = "query($i:CotizarEnvioInput!){ cotizarEnvio(input:$i){ token paqueteria descripcion dias costo modo } }"
REGISTRAR = (
    "mutation($i:PedidoInput!){ registrarPedido(input:$i){ id subtotal costoEnvio total"
    " entrega{ tipo cp costo descripcion guia } } }"
)
DIRECCION = {"tipo": "domicilio", "nombre": "Ana Envío", "telefono": "3311122233", "calle": "Av. Chapultepec",
             "numero": "480", "colonia": "Americana", "ciudad": "Guadalajara", "estado": "JA", "cp": "44160"}
ITEMS = [{"productoId": 2, "cantidad": 2}]


def cotizar(gql, cp="44160", estado="JA", items=ITEMS):
    return gql(COTIZAR, {"i": {"cp": cp, "estado": estado, "items": items}})["cotizarEnvio"]


def registrar(gql, token, entrega, items=ITEMS, metodo="paypal"):
    return gql(REGISTRAR, {"i": {"items": items, "metodoPago": metodo, "entrega": entrega}}, token=token)["registrarPedido"]


def test_cotiza_varias_paqueterias_ordenadas_y_foraneo_cuesta_mas(gql):
    local = cotizar(gql)
    assert len(local) == 3 and [o["costo"] for o in local] == sorted(o["costo"] for o in local)
    assert all(o["modo"] == "simulado" and o["token"] for o in local)
    cdmx = cotizar(gql, "06100", "CX")
    assert cdmx[0]["costo"] > local[0]["costo"]


def test_pedido_a_domicilio_suma_el_envio_firmado(gql, nuevo_cliente):
    token, _ = nuevo_cliente()
    opcion = cotizar(gql)[0]
    p = registrar(gql, token, {**DIRECCION, "opcionToken": opcion["token"]})
    assert p["costoEnvio"] == opcion["costo"] and p["total"] == round(p["subtotal"] + opcion["costo"], 2)
    assert p["entrega"]["tipo"] == "domicilio" and p["entrega"]["descripcion"] == opcion["descripcion"]


def test_no_se_puede_alterar_ni_reusar_la_cotizacion(gql, nuevo_cliente):
    token, _ = nuevo_cliente()
    opcion = cotizar(gql)[0]
    datos, firma = opcion["token"].split(".")
    with pytest.raises(ErrorGraphQL, match="no es válida"):          # precio alterado
        registrar(gql, token, {**DIRECCION, "opcionToken": datos[:-2] + "AA." + firma})
    with pytest.raises(ErrorGraphQL, match="otro código postal"):
        registrar(gql, token, {**DIRECCION, "cp": "44100", "opcionToken": opcion["token"]})
    with pytest.raises(ErrorGraphQL, match="carrito cambió"):          # más peso que al cotizar
        registrar(gql, token, {**DIRECCION, "opcionToken": opcion["token"]}, items=[{"productoId": 2, "cantidad": 6}])


def test_efectivo_solo_al_recoger(gql, nuevo_cliente):
    token, _ = nuevo_cliente()
    opcion = cotizar(gql)[0]
    with pytest.raises(ErrorGraphQL, match="efectivo"):
        registrar(gql, token, {**DIRECCION, "opcionToken": opcion["token"]}, metodo="efectivo")


def test_al_enviar_se_genera_la_guia_y_se_avisa_al_cliente(gql, nuevo_cliente, token_admin):
    import relacional

    token, usuario = nuevo_cliente()
    opcion = cotizar(gql)[0]
    p = registrar(gql, token, {**DIRECCION, "opcionToken": opcion["token"]}, metodo="transferencia")
    cambiar = "mutation($id:Int!,$e:String!){ cambiarEstadoPedido(id:$id, estado:$e){ estado entrega{ guia } } }"
    gql(cambiar, {"id": p["id"], "e": "pagado"}, token=token_admin)
    enviado = gql(cambiar, {"id": p["id"], "e": "enviado"}, token=token_admin)["cambiarEstadoPedido"]
    assert enviado["estado"] == "enviado" and enviado["entrega"]["guia"].startswith("SIM")
    rastreo = gql("query($id:Int!){ rastrearPedido(id:$id){ guia estado eventos{ descripcion } } }", {"id": p["id"]}, token=token)
    assert rastreo["rastrearPedido"]["estado"] == "En tránsito"
    plantillas = {c["plantilla"] for c in relacional.correos_recientes(50) if c["destinatario"] == usuario["email"]}
    assert {"pedido_confirmado", "pedido_enviado"} <= plantillas


def test_codigo_postal_usa_geocodes_de_envia(gql, monkeypatch):
    import envios

    respuesta = [{"zip_code": "44650", "state": {"name": "Jalisco", "code": {"2digit": "JA"}},
                  "locality": "Guadalajara", "suburbs": ["Arcos Vallarta", "Ladrón de Guevara"]}]
    llamadas = []

    def falso(metodo, url, cuerpo=None, timeout=20):
        llamadas.append(url)
        return 200, respuesta

    monkeypatch.setattr(envios, "_http", falso)
    envios._cache_cp.clear()
    info = gql('{ buscarCodigoPostal(cp:"44650"){ estado ciudad colonias } }')["buscarCodigoPostal"]
    assert info == {"estado": "JA", "ciudad": "Guadalajara", "colonias": ["Arcos Vallarta", "Ladrón de Guevara"]}
    assert llamadas == ["https://geocodes.envia.com/zipcode/MX/44650"]
    with pytest.raises(ErrorGraphQL, match="5 dígitos"):
        gql('{ buscarCodigoPostal(cp:"44"){ estado } }')


def test_a_envia_se_le_mandan_los_datos_sin_acentos():
    """Envia truena con acentos ("Malformed UTF-8 characters")."""
    import envios

    limpio = envios._sin_acentos({"colonia": "Ladrón de Guevara", "items": [{"content": "Café y ñoquis"}], "kg": 1.5})
    assert limpio == {"colonia": "Ladron de Guevara", "items": [{"content": "Cafe y noquis"}], "kg": 1.5}
