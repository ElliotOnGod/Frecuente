"""Prefactura CFDI (RQF90 a RQF96; RQNF111 a RQNF120): datos fiscales, XML,
validación XSD y de catálogos, IVA por producto, cuadre con el total,
generación al pagar y descargas solo para el dueño o el administrador."""

from datetime import datetime
from decimal import Decimal

import pytest
from lxml import etree

from conftest import ErrorGraphQL

NS = {"cfdi": "http://www.sat.gob.mx/cfd/4"}

REGISTRAR = "mutation($i:PedidoInput!){ registrarPedido(input:$i){ id total costoEnvio } }"
CONFIRMAR = "mutation($i:ConfirmarPagoInput!){ confirmarPago(input:$i){ id estado pago{ estado } } }"
PREFACTURA = """query($p:Int!){ prefactura(pedidoId:$p){
  serie folio rfcReceptor nombreReceptor regimenFiscalReceptor cpFiscalReceptor usoCfdi
  subtotal iva total estado disponible errores } }"""
COTIZAR = "query($i:CotizarEnvioInput!){ cotizarEnvio(input:$i){ token costo } }"
DIRECCION = {"tipo": "domicilio", "nombre": "Ana Envío", "telefono": "3311122233", "calle": "Av. Chapultepec",
             "numero": "480", "colonia": "Americana", "ciudad": "Guadalajara", "estado": "JA", "cp": "44160"}
FISCALES = {"rfc": "GODE561231GR8", "nombre": "Empresa Demo", "regimenFiscal": "612",
            "cpFiscal": "44160", "usoCfdi": "G03"}


def pedir(gql, token, items, metodo="paypal", **extra):
    return gql(REGISTRAR, {"i": {"items": items, "metodoPago": metodo, **extra}}, token=token)["registrarPedido"]


def pagar(gql, token, pedido_id):
    return gql(CONFIRMAR, {"i": {"pedidoId": pedido_id, "simulacion": "aprobado"}}, token=token)["confirmarPago"]


def con_envio(gql, items):
    opcion = gql(COTIZAR, {"i": {"cp": "44160", "estado": "JA", "items": items}})["cotizarEnvio"][0]
    return {**DIRECCION, "opcionToken": opcion["token"]}


def xml_de(pedido_id):
    import relacional

    return relacional.prefactura(pedido_id)["xml"]


def leer(xml):
    return etree.fromstring(xml.encode("utf-8"))


def pedido_falso(items, envio=0.0, metodo="mercadopago"):
    """Pedido con la forma de relacional.pedido() para probar el generador sin la base."""
    subtotal = sum(Decimal(str(c)) * Decimal(str(p)) for _, c, p, _ in items)
    return {
        "_id": 900, "envio": envio, "total": float(subtotal + Decimal(str(envio))),
        "items": [{"producto_id": pid, "nombre": f"Producto {pid}", "variante": "", "cantidad": c, "precio_unit": p}
                  for pid, c, p, _ in items],
        "pago": {"metodo": metodo, "fecha_pago": datetime(2026, 11, 17, 10, 0)},
        "entrega": {"descripcion": "DHL Express"} if envio else {"tipo": "recoger"},
    }


def productos_falsos(items, clave_cafe="50201706", clave_accesorio="52141526"):
    return {
        pid: {"tasa_iva": tasa, "clave_prod_serv": clave_cafe if tasa == 0 else clave_accesorio, "clave_unidad": "H87"}
        for pid, _, _, tasa in items
    }


# ---------------- RQF90: datos fiscales ----------------

def test_rfc_valida_estructura(gql, nuevo_cliente):
    """RQNF111: 3 letras (moral) o 4 (física) + AAMMDD + 3 de homoclave; backend y GraphQL."""
    from cfdi.prefactura import rfc_valido

    for bueno in ("GODE561231GR8", "ABC991231AB1", "XAXX010101000", "ÑAÑO800101AA1"):
        assert rfc_valido(bueno), bueno
    for malo in ("GODE561331GR8",   # mes 13
                 "GODE560230GR8",   # 30 de febrero
                 "AB991231AB1",     # 2 letras
                 "ABCDE991231AB1",  # 5 letras
                 "ABC99123AB1",     # 5 dígitos de fecha
                 "ABC991231AB",     # homoclave de 2
                 "ABC991231-B1",    # homoclave no alfanumérica
                 "1BC991231AB1", ""):
        assert not rfc_valido(malo), malo

    token, _ = nuevo_cliente()
    with pytest.raises(ErrorGraphQL, match="RFC debe tener 3 letras"):
        pedir(gql, token, [{"productoId": 4, "cantidad": 1}], datosFiscales={**FISCALES, "rfc": "GODE561331GR8"})
    # minúsculas y espacios se normalizan
    p = pedir(gql, token, [{"productoId": 4, "cantidad": 1}], datosFiscales={**FISCALES, "rfc": " gode561231gr8 "})
    import relacional

    assert relacional.pedido(p["id"])["datos_fiscales"]["rfc"] == "GODE561231GR8"


def test_prefactura_publico_en_general(gql, nuevo_cliente):
    """RQNF112: sin datos fiscales, el receptor es XAXX010101000. CV-66: con RFC de 13, sus datos en Receptor."""
    token, _ = nuevo_cliente()
    sin_datos = pedir(gql, token, [{"productoId": 4, "cantidad": 2}])
    pagar(gql, token, sin_datos["id"])
    pf = gql(PREFACTURA, {"p": sin_datos["id"]}, token=token)["prefactura"]
    assert pf["rfcReceptor"] == "XAXX010101000" and pf["nombreReceptor"] == "PUBLICO EN GENERAL"
    receptor = leer(xml_de(sin_datos["id"])).find("cfdi:Receptor", NS)
    assert receptor.get("Rfc") == "XAXX010101000" and receptor.get("UsoCFDI") == "S01"
    assert receptor.get("RegimenFiscalReceptor") == "616"

    con_datos = pedir(gql, token, [{"productoId": 4, "cantidad": 2}], datosFiscales=FISCALES)
    pagar(gql, token, con_datos["id"])
    receptor = leer(xml_de(con_datos["id"])).find("cfdi:Receptor", NS)
    assert receptor.get("Rfc") == "GODE561231GR8" and len(receptor.get("Rfc")) == 13
    assert receptor.get("Nombre") == "EMPRESA DEMO" and receptor.get("RegimenFiscalReceptor") == "612"
    assert receptor.get("DomicilioFiscalReceptor") == "44160" and receptor.get("UsoCFDI") == "G03"


# ---------------- RQF91: generación y validación ----------------

def test_prefactura_nodos(gql, nuevo_cliente):
    """RQNF113: Comprobante, Emisor, Receptor, Conceptos e Impuestos."""
    token, _ = nuevo_cliente()
    p = pedir(gql, token, [{"productoId": 1, "cantidad": 1}, {"productoId": 9, "cantidad": 1}])
    pagar(gql, token, p["id"])
    raiz = leer(xml_de(p["id"]))
    assert raiz.tag == "{http://www.sat.gob.mx/cfd/4}Comprobante" and raiz.get("Version") == "4.0"
    for nodo in ("Emisor", "Receptor", "Conceptos", "Impuestos"):
        assert raiz.find(f"cfdi:{nodo}", NS) is not None, nodo
    assert len(raiz.findall("cfdi:Conceptos/cfdi:Concepto", NS)) == 2


def test_prefactura_valida_xsd():
    """RQNF114: el XML generado pasa el XSD del SAT y uno alterado no."""
    from cfdi import prefactura as pf

    items = [(1, 2, 185.0, 0.0), (9, 1, 420.0, 0.16)]
    xml = pf.construir(pedido_falso(items, envio=149.0), productos_falsos(items), None)["xml"]
    assert pf.validar_xsd(xml) == []
    alterado = xml.replace('Moneda="MXN"', 'Moneda="PESOS"')
    assert pf.validar_xsd(alterado)
    sin_emisor = etree.tostring(leer(xml)).decode().replace("cfdi:Emisor", "cfdi:Otro")
    assert pf.validar_xsd(sin_emisor)


def test_prefactura_catalogos_sat():
    """RQNF115: cada clave contra su catálogo del SAT."""
    from cfdi import prefactura as pf

    items = [(1, 1, 185.0, 0.0), (9, 1, 420.0, 0.16)]
    xml = pf.construir(pedido_falso(items, envio=120.0), productos_falsos(items), None)["xml"]
    assert pf.validar_catalogos(xml) == []
    cambios = {
        'Moneda="MXN"': "Moneda", 'FormaPago="31"': "Forma de pago", 'MetodoPago="PUE"': "Método de pago",
        'ClaveProdServ="50201706"': "Clave de producto", 'ClaveUnidad="H87"': "Clave de unidad",
        'ObjetoImp="02"': "Objeto de impuesto", 'Impuesto="002"': "Impuesto", 'TipoFactor="Tasa"': "Tipo de factor",
        'TasaOCuota="0.160000"': "Tasa o cuota", 'RegimenFiscal="601"': "Régimen fiscal del emisor",
        'RegimenFiscalReceptor="616"': "Régimen fiscal del receptor", 'UsoCFDI="S01"': "Uso del CFDI",
    }
    for original, nombre in cambios.items():
        clave = original.split("=")[0]
        malo = xml.replace(original, f'{clave}="ZZZ"', 1)
        assert any(e.startswith(nombre) for e in pf.validar_catalogos(malo)), nombre


def test_prefactura_iva_por_producto(gql, nuevo_cliente):
    """RQNF116: cada concepto usa la tasa de su producto (café 0 %, accesorio 16 %)."""
    from database import db

    assert db.productos.find_one({"_id": 1})["tasa_iva"] == 0.0
    assert db.productos.find_one({"_id": 9})["tasa_iva"] == 0.16
    token, _ = nuevo_cliente()
    p = pedir(gql, token, [{"productoId": 1, "cantidad": 2}, {"productoId": 9, "cantidad": 1}])
    pagar(gql, token, p["id"])
    tasas = {
        c.get("NoIdentificacion"): c.find("cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado", NS).get("TasaOCuota")
        for c in leer(xml_de(p["id"])).findall("cfdi:Conceptos/cfdi:Concepto", NS)
    }
    assert tasas == {"1": "0.000000", "9": "0.160000"}


def test_prefactura_cuadra_con_total(gql, nuevo_cliente):
    """RQNF117: importes de los conceptos (con el envío) + IVA = total del pedido, al centavo."""
    from cfdi import prefactura as pf

    casos = [
        [(1, 1, 185.0, 0.0)],
        [(9, 1, 420.0, 0.16)],
        [(9, 3, 99.99, 0.16), (1, 7, 33.33, 0.0)],
        [(9, 1, 0.01, 0.16), (2, 1, 0.01, 0.0)],
        [(9, 13, 17.17, 0.16), (2, 11, 260.0, 0.0), (5, 3, 68.0, 0.0)],
    ]
    for envio in (0.0, 149.0, 87.33, 0.01):
        for items in casos:
            pedido = pedido_falso(items, envio=envio)
            armado = pf.construir(pedido, productos_falsos(items), None)
            assert armado["total"] == Decimal(str(pedido["total"])).quantize(Decimal("0.01"))
            assert pf.validar(armado["xml"], pedido["total"]) == [], (items, envio)

    # De punta a punta: pedido real con productos de 0 % y 16 % y envío a domicilio
    token, _ = nuevo_cliente()
    items = [{"productoId": 1, "cantidad": 2}, {"productoId": 9, "cantidad": 1}, {"productoId": 5, "cantidad": 3}]
    p = pedir(gql, token, items, entrega=con_envio(gql, items))
    assert p["costoEnvio"] > 0
    pagar(gql, token, p["id"])
    raiz = leer(xml_de(p["id"]))
    importes = sum(Decimal(c.get("Importe")) for c in raiz.findall("cfdi:Conceptos/cfdi:Concepto", NS))
    iva = Decimal(raiz.find("cfdi:Impuestos", NS).get("TotalImpuestosTrasladados"))
    assert importes + iva == Decimal(str(p["total"])).quantize(Decimal("0.01"))
    assert raiz.find("cfdi:Conceptos/cfdi:Concepto[@NoIdentificacion='ENVIO']", NS) is not None


def test_prefactura_invalida_no_se_publica(gql, nuevo_cliente, token_admin, cliente):
    """RQNF118 y RQNF185: si la validación falla, queda en «error», el cliente no la ve ni
    la descarga y el administrador ve los errores."""
    from database import db

    token, _ = nuevo_cliente()
    p = pedir(gql, token, [{"productoId": 3, "cantidad": 1}])
    # Un producto con una clave que el catálogo no acepta (dato dañado a mano,
    # saltando el validador de MongoDB que normalmente lo impediría)
    original = db.productos.find_one({"_id": 3})
    db.command("collMod", "productos", validationLevel="off")
    try:
        db.productos.update_one({"_id": 3}, {"$set": {"clave_prod_serv": "99999999"}})
        pagar(gql, token, p["id"])
    finally:
        db.productos.update_one({"_id": 3}, {"$set": {"clave_prod_serv": original["clave_prod_serv"]}})
        db.command("collMod", "productos", validationLevel="strict")

    import relacional

    assert relacional.prefactura(p["id"])["estado"] == "error"
    assert gql(PREFACTURA, {"p": p["id"]}, token=token)["prefactura"] is None
    r = cliente.get(f"/prefacturas/{p['id']}.xml", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404
    admin = gql(PREFACTURA, {"p": p["id"]}, token=token_admin)["prefactura"]
    assert admin["estado"] == "error" and admin["disponible"] is False
    assert any("99999999" in e for e in admin["errores"])


def test_prefactura_se_genera_al_pagar(gql, nuevo_cliente, token_admin):
    """RQF91: se genera al aprobarse el pago, por la pasarela o confirmado por el administrador."""
    import relacional

    token, _ = nuevo_cliente()
    p = pedir(gql, token, [{"productoId": 4, "cantidad": 1}])
    assert relacional.prefactura(p["id"]) is None            # sin pagar no hay prefactura
    pagar(gql, token, p["id"])
    pf = gql(PREFACTURA, {"p": p["id"]}, token=token)["prefactura"]
    assert pf["estado"] == "validada" and pf["disponible"] and pf["folio"] == p["id"] and pf["total"] == p["total"]
    pagar(gql, token, p["id"])                               # aviso repetido: sigue habiendo una sola
    assert relacional.prefactura(p["id"])["estado"] == "validada"

    # Transferencia SPEI confirmada a mano por el administrador
    spei = pedir(gql, token, [{"productoId": 4, "cantidad": 1}], metodo="transferencia")
    gql('mutation($id:Int!){ cambiarEstadoPedido(id:$id, estado:"pagado"){ id } }', {"id": spei["id"]}, token=token_admin)
    assert leer(xml_de(spei["id"])).get("FormaPago") == "03"
    # Efectivo al recoger: registrado → entregado también aprueba el pago
    efectivo = pedir(gql, token, [{"productoId": 4, "cantidad": 1}], metodo="efectivo")
    gql('mutation($id:Int!){ cambiarEstadoPedido(id:$id, estado:"entregado"){ id } }', {"id": efectivo["id"]}, token=token_admin)
    assert leer(xml_de(efectivo["id"])).get("FormaPago") == "01"


def test_prefactura_solo_dueno(gql, nuevo_cliente, token_admin, cliente):
    """RQNF119: solo el dueño y los administradores descargan; los demás reciben 403.
    RQNF120: el PDF sale del XML guardado, con los mismos datos e importes."""
    from cfdi import prefactura as pf

    token, _ = nuevo_cliente()
    p = pedir(gql, token, [{"productoId": 1, "cantidad": 1}, {"productoId": 9, "cantidad": 1}], datosFiscales=FISCALES)
    pagar(gql, token, p["id"])
    url_xml, url_pdf = f"/prefacturas/{p['id']}.xml", f"/prefacturas/{p['id']}.pdf"

    def descargar(url, tk=None):
        return cliente.get(url, headers={"Authorization": f"Bearer {tk}"} if tk else {})

    dueno = descargar(url_xml, token)                                  # CV-67
    assert dueno.status_code == 200 and dueno.headers["content-type"].startswith("application/xml")
    assert dueno.text == xml_de(p["id"])
    pdf = descargar(url_pdf, token)                                    # CV-68
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert descargar(url_xml, token_admin).status_code == 200          # CV-69
    assert descargar(url_pdf, token_admin).status_code == 200          # CV-71
    otro, _ = nuevo_cliente("Otro Cliente")
    assert descargar(url_xml, otro).status_code == 403
    assert descargar(url_pdf, otro).status_code == 403
    assert descargar(url_xml).status_code == 401
    with pytest.raises(ErrorGraphQL):
        gql(PREFACTURA, {"p": p["id"]}, token=otro)
    # CV-70: el administrador consulta la prefactura de un pedido de otro cliente
    assert gql(PREFACTURA, {"p": p["id"]}, token=token_admin)["prefactura"]["rfcReceptor"] == "GODE561231GR8"

    # El PDF muestra los mismos datos e importes del XML
    datos = pf.datos_de_xml(dueno.text)
    assert datos["receptor"]["Rfc"] == "GODE561231GR8" and datos["total"] == f"{p['total']:.2f}"
    assert [c["Importe"] for c in datos["conceptos"]] == [
        c.get("Importe") for c in leer(dueno.text).findall("cfdi:Conceptos/cfdi:Concepto", NS)
    ]
