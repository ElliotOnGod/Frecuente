"""
cfdi/prefactura.py — construye, valida y representa en PDF la prefactura de un pedido.

Prefactura: comprobante en XML con la estructura del CFDI, sin timbre
fiscal (sección 1.3 del SRS). Se genera cuando se aprueba el pago (RQF91).

Versión del esquema: el SRS dice «CFDI 4.1», pero el SAT solo publica el
esquema 4.0 (http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd, espacio
de nombres http://www.sat.gob.mx/cfd/4, Version="4.0"). El XML se genera y
valida con ese esquema; la diferencia se documenta aparte.

Qué revisa antes de ponerla a disposición:
  - RQNF113: nodos Comprobante, Emisor, Receptor, Conceptos e Impuestos.
  - RQNF114: el XML contra cfdv40.xsd (con copia local de tdCFDI.xsd y
    catCFDI.xsd en cfdi/xsd/; no se descarga nada al validar).
  - RQNF115: cada clave contra el extracto de catálogos (catalogos.py).
  - RQNF116: cada concepto con la tasa de IVA de su producto (0 % o 16 %).
  - RQNF117: suma de importes + IVA trasladado = total del pedido, al centavo.

Sello, NoCertificado y Certificado: el XSD los exige, pero solo existen
cuando un contribuyente sella el comprobante con su Certificado de Sello
Digital (CSD), y el timbrado con un PAC (RQF97) está fuera de esta versión.
Por eso llevan valores de relleno que cumplen el XSD: NoCertificado con 20
ceros y Sello y Certificado con el texto SIN-SELLO. Con esos valores
nadie puede confundir la prefactura con una factura válida.

Precios: los del catálogo ya incluyen IVA. Por cada renglón, la base es el
importe del renglón entre (1 + tasa) redondeado al centavo, y el IVA es la
diferencia; así base + IVA = importe del renglón exacto, y la suma de todos
los renglones (con el envío) da el total del pedido sin tocarlo.
"""

import os
import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from lxml import etree

from cfdi import catalogos as cat

NS = "http://www.sat.gob.mx/cfd/4"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = "http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd"
VERSION = "4.0"
SERIE = "FREC"
XSD_DIR = Path(__file__).resolve().parent / "xsd"

NO_CERTIFICADO_RELLENO = "0" * 20
SELLO_RELLENO = "SIN-SELLO"

# RQNF111: 3 letras (moral) o 4 letras (física) + fecha AAMMDD + 3 caracteres de homoclave
RFC_RE = re.compile(r"^([A-ZÑ]{3,4})(\d{2})(\d{2})(\d{2})([A-Z0-9]{3})$")
CP_RE = re.compile(r"^\d{5}$")

DOS = Decimal("0.01")


class DatosFiscalesInvalidos(ValueError):
    """Los datos fiscales que capturó el cliente no cumplen las reglas."""


def emisor() -> dict:
    """Datos del emisor (FRECUENTE). Por omisión, los del contribuyente de
    pruebas que publica el SAT para su Certificado de Sello Digital de prueba."""
    return {
        "rfc": os.getenv("EMISOR_RFC", "").strip().upper() or "EKU9003173C9",
        "nombre": os.getenv("EMISOR_NOMBRE", "").strip().upper() or "ESCUELA KEMPER URGATE",
        "regimen": os.getenv("EMISOR_REGIMEN", "").strip() or "601",
        "cp": os.getenv("EMISOR_CP", "").strip() or "44650",
    }


# =========================================================
# Datos fiscales del cliente (RQF90)
# =========================================================

def rfc_valido(rfc: str) -> bool:
    """RQNF111: estructura del RFC (con fecha AAMMDD real)."""
    m = RFC_RE.match(rfc or "")
    if not m:
        return False
    _, aa, mm, dd, _ = m.groups()
    try:
        date(2000 + int(aa), int(mm), int(dd))  # el siglo no cambia si la fecha existe
    except ValueError:
        return False
    return True


def limpiar_datos_fiscales(datos: dict | None) -> dict | None:
    """Revisa los datos fiscales capturados. Sin datos → None (público en general).
    Si captura alguno, deben venir los cinco y ser válidos."""
    if not datos:
        return None
    rfc = str(datos.get("rfc") or "").strip().upper()
    nombre = " ".join(str(datos.get("nombre") or "").split()).upper()
    regimen = str(datos.get("regimen_fiscal") or "").strip()
    cp = str(datos.get("cp_fiscal") or "").strip()
    uso = str(datos.get("uso_cfdi") or "").strip().upper()
    if not any([rfc, nombre, regimen, cp, uso]):
        return None
    if not rfc_valido(rfc):
        raise DatosFiscalesInvalidos(
            "El RFC debe tener 3 letras (persona moral) o 4 letras (persona física), "
            "6 dígitos de fecha AAMMDD y 3 caracteres de homoclave"
        )
    if not nombre:
        raise DatosFiscalesInvalidos("Escribe el nombre o razón social como aparece en tu constancia fiscal")
    if regimen not in cat.REGIMEN_FISCAL:
        raise DatosFiscalesInvalidos("Elige un régimen fiscal del catálogo del SAT")
    if not CP_RE.match(cp):
        raise DatosFiscalesInvalidos("El código postal fiscal debe tener 5 dígitos")
    if uso not in cat.USO_CFDI:
        raise DatosFiscalesInvalidos("Elige un uso del CFDI del catálogo del SAT")
    if regimen not in cat.USO_POR_REGIMEN[uso]:
        raise DatosFiscalesInvalidos("Ese uso del CFDI no aplica al régimen fiscal elegido")
    return {"rfc": rfc, "nombre": nombre, "regimen_fiscal": regimen, "cp_fiscal": cp, "uso_cfdi": uso}


def receptor_de(datos_fiscales: dict | None, cp_emisor: str) -> dict:
    """RQNF112: sin datos fiscales, el receptor es el público en general."""
    if datos_fiscales:
        return {
            "rfc": datos_fiscales["rfc"],
            "nombre": datos_fiscales["nombre"],
            "regimen": datos_fiscales["regimen_fiscal"],
            "cp": datos_fiscales["cp_fiscal"],
            "uso": datos_fiscales["uso_cfdi"],
        }
    return {
        "rfc": cat.RFC_PUBLICO_GENERAL,
        "nombre": cat.NOMBRE_PUBLICO_GENERAL,
        "regimen": cat.REGIMEN_PUBLICO_GENERAL,
        "cp": cp_emisor,  # para público en general el SAT pide el CP del lugar de expedición
        "uso": cat.USO_PUBLICO_GENERAL,
    }


# =========================================================
# Importes
# =========================================================

def _d(valor) -> Decimal:
    return Decimal(str(valor)).quantize(DOS, rounding=ROUND_HALF_UP)


def _tasa_txt(tasa: float) -> str:
    return f"{Decimal(str(tasa)):.6f}"


def conceptos_de(pedido: dict, productos: dict[int, dict]) -> list[dict]:
    """Un concepto por renglón del pedido y uno por el envío (si cuesta).
    `productos` = {producto_id: documento del catálogo} con tasa_iva y claves SAT."""
    conceptos = []
    for it in pedido["items"]:
        prod = productos.get(it["producto_id"]) or {}
        nombre = it["nombre"] + (f" ({it['variante']})" if it.get("variante") else "")
        conceptos.append({
            "no_identificacion": str(it["producto_id"]),
            "clave_prod_serv": str(prod.get("clave_prod_serv") or ""),
            "clave_unidad": str(prod.get("clave_unidad") or ""),
            "descripcion": nombre,
            "cantidad": int(it["cantidad"]),
            "importe_con_iva": _d(it["cantidad"] * it["precio_unit"]),
            "tasa": float(prod["tasa_iva"]) if prod.get("tasa_iva") is not None else None,
        })
    if _d(pedido.get("envio") or 0) > 0:
        entrega = pedido.get("entrega") or {}
        paqueteria = entrega.get("descripcion") or entrega.get("paqueteria") or "paquetería"
        conceptos.append({
            "no_identificacion": "ENVIO",
            "clave_prod_serv": cat.ENVIO_CLAVE_PROD_SERV,
            "clave_unidad": cat.ENVIO_CLAVE_UNIDAD,
            "descripcion": f"Envío a domicilio ({paqueteria})",
            "cantidad": 1,
            "importe_con_iva": _d(pedido["envio"]),
            "tasa": cat.ENVIO_TASA_IVA,
        })
    for c in conceptos:
        tasa = c["tasa"] if c["tasa"] is not None else 0.0
        base = (c["importe_con_iva"] / (Decimal(1) + Decimal(str(tasa)))).quantize(DOS, rounding=ROUND_HALF_UP)
        c["importe"] = base
        c["iva"] = c["importe_con_iva"] - base  # base + IVA = importe del renglón, exacto
        c["valor_unitario"] = (base / c["cantidad"]).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return conceptos


# =========================================================
# XML
# =========================================================

def _q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _fecha(valor) -> str:
    if isinstance(valor, datetime):
        return valor.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")
    return datetime.now().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")


def construir(pedido: dict, productos: dict[int, dict], datos_fiscales: dict | None) -> dict:
    """Arma el XML de la prefactura. Regresa {xml, receptor, subtotal, iva, total}."""
    em = emisor()
    rec = receptor_de(datos_fiscales, em["cp"])
    conceptos = conceptos_de(pedido, productos)
    subtotal = sum((c["importe"] for c in conceptos), Decimal("0.00"))
    iva = sum((c["iva"] for c in conceptos), Decimal("0.00"))
    total = subtotal + iva
    fecha = (pedido.get("pago") or {}).get("fecha_pago") or datetime.now()

    raiz = etree.Element(_q("Comprobante"), nsmap={"cfdi": NS, "xsi": NS_XSI})
    raiz.set(f"{{{NS_XSI}}}schemaLocation", SCHEMA_LOCATION)
    for clave, valor in [
        ("Version", VERSION),
        ("Serie", SERIE),
        ("Folio", str(pedido["_id"])),
        ("Fecha", _fecha(fecha)),
        ("Sello", SELLO_RELLENO),
        ("FormaPago", cat.FORMA_PAGO_POR_METODO.get((pedido.get("pago") or {}).get("metodo"), "99")),
        ("NoCertificado", NO_CERTIFICADO_RELLENO),
        ("Certificado", SELLO_RELLENO),
        ("SubTotal", f"{subtotal:.2f}"),
        ("Moneda", "MXN"),
        ("Total", f"{total:.2f}"),
        ("TipoDeComprobante", "I"),
        ("Exportacion", "01"),
        ("MetodoPago", "PUE"),
        ("LugarExpedicion", em["cp"]),
    ]:
        raiz.set(clave, valor)

    if rec["rfc"] == cat.RFC_PUBLICO_GENERAL:
        # Venta a público en general: el SAT pide el nodo InformacionGlobal
        etree.SubElement(raiz, _q("InformacionGlobal"), Periodicidad="01",
                         Meses=f"{fecha.month:02d}" if isinstance(fecha, datetime) else f"{date.today().month:02d}",
                         Año=str(fecha.year if isinstance(fecha, datetime) else date.today().year))
    etree.SubElement(raiz, _q("Emisor"), Rfc=em["rfc"], Nombre=em["nombre"], RegimenFiscal=em["regimen"])
    etree.SubElement(raiz, _q("Receptor"), Rfc=rec["rfc"], Nombre=rec["nombre"],
                     DomicilioFiscalReceptor=rec["cp"], RegimenFiscalReceptor=rec["regimen"], UsoCFDI=rec["uso"])

    nodo_conceptos = etree.SubElement(raiz, _q("Conceptos"))
    for c in conceptos:
        concepto = etree.SubElement(
            nodo_conceptos, _q("Concepto"),
            ClaveProdServ=c["clave_prod_serv"], NoIdentificacion=c["no_identificacion"],
            Cantidad=str(c["cantidad"]), ClaveUnidad=c["clave_unidad"], Descripcion=c["descripcion"],
            ValorUnitario=f"{c['valor_unitario']:.6f}", Importe=f"{c['importe']:.2f}", ObjetoImp="02",
        )
        traslados = etree.SubElement(etree.SubElement(concepto, _q("Impuestos")), _q("Traslados"))
        etree.SubElement(traslados, _q("Traslado"), Base=f"{c['importe']:.2f}", Impuesto="002",
                         TipoFactor="Tasa", TasaOCuota=_tasa_txt(c["tasa"] if c["tasa"] is not None else -1),
                         Importe=f"{c['iva']:.2f}")

    # Resumen de impuestos: un traslado por tasa
    por_tasa: dict[str, list[Decimal]] = {}
    for c in conceptos:
        acumulado = por_tasa.setdefault(_tasa_txt(c["tasa"] if c["tasa"] is not None else -1), [Decimal("0.00"), Decimal("0.00")])
        acumulado[0] += c["importe"]
        acumulado[1] += c["iva"]
    impuestos = etree.SubElement(raiz, _q("Impuestos"), TotalImpuestosTrasladados=f"{iva:.2f}")
    traslados = etree.SubElement(impuestos, _q("Traslados"))
    for tasa, (base, importe) in sorted(por_tasa.items()):
        etree.SubElement(traslados, _q("Traslado"), Base=f"{base:.2f}", Impuesto="002",
                         TipoFactor="Tasa", TasaOCuota=tasa, Importe=f"{importe:.2f}")

    xml = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", pretty_print=True).decode("utf-8")
    return {"xml": xml, "receptor": rec, "subtotal": subtotal, "iva": iva, "total": total}


# =========================================================
# Validación
# =========================================================

class _ResolverSAT(etree.Resolver):
    """Los import de cfdv40.xsd apuntan a sat.gob.mx; se resuelven con la copia local."""

    def resolve(self, url, pubid, context):
        nombre = url.rsplit("/", 1)[-1]
        local = XSD_DIR / nombre
        if local.exists():
            return self.resolve_filename(str(local), context)
        return None


_esquema = None


def _xsd() -> etree.XMLSchema:
    global _esquema
    if _esquema is None:
        parser = etree.XMLParser(no_network=True, huge_tree=True)
        parser.resolvers.add(_ResolverSAT())
        _esquema = etree.XMLSchema(etree.parse(str(XSD_DIR / "cfdv40.xsd"), parser))
    return _esquema


def _leer(xml: str):
    return etree.fromstring(xml.encode("utf-8"), etree.XMLParser(no_network=True, resolve_entities=False))


def validar_xsd(xml: str) -> list[str]:
    """RQNF114: errores del XML contra el esquema XSD del SAT ([] si es válido)."""
    try:
        doc = _leer(xml)
    except etree.XMLSyntaxError as e:
        return [f"XML mal formado: {e}"]
    esquema = _xsd()
    if esquema.validate(doc):
        return []
    return [f"XSD línea {e.line}: {e.message}" for e in esquema.error_log]


def validar_nodos(xml: str) -> list[str]:
    """RQNF113: la prefactura contiene Comprobante, Emisor, Receptor, Conceptos e Impuestos."""
    doc = _leer(xml)
    faltan = []
    if doc.tag != _q("Comprobante"):
        faltan.append("Comprobante")
    for nodo in ("Emisor", "Receptor", "Conceptos", "Impuestos"):
        if doc.find(_q(nodo)) is None:
            faltan.append(nodo)
    return [f"Falta el nodo {n}" for n in faltan]


def validar_catalogos(xml: str) -> list[str]:
    """RQNF115: cada clave usada existe en su catálogo del SAT."""
    doc = _leer(xml)
    errores = []

    def revisar(valor, catalogo, nombre):
        if valor not in catalogo:
            errores.append(f"{nombre} «{valor}» no está en el catálogo del SAT")

    revisar(doc.get("Moneda"), cat.MONEDA, "Moneda")
    revisar(doc.get("FormaPago"), cat.FORMA_PAGO, "Forma de pago")
    revisar(doc.get("MetodoPago"), cat.METODO_PAGO, "Método de pago")
    revisar(doc.get("TipoDeComprobante"), cat.TIPO_COMPROBANTE, "Tipo de comprobante")
    revisar(doc.get("Exportacion"), cat.EXPORTACION, "Exportación")
    emisor_n, receptor_n = doc.find(_q("Emisor")), doc.find(_q("Receptor"))
    if emisor_n is not None:
        revisar(emisor_n.get("RegimenFiscal"), cat.REGIMEN_FISCAL, "Régimen fiscal del emisor")
    if receptor_n is not None:
        revisar(receptor_n.get("RegimenFiscalReceptor"), cat.REGIMEN_FISCAL, "Régimen fiscal del receptor")
        revisar(receptor_n.get("UsoCFDI"), cat.USO_CFDI, "Uso del CFDI")
    global_n = doc.find(_q("InformacionGlobal"))
    if global_n is not None:
        revisar(global_n.get("Periodicidad"), cat.PERIODICIDAD, "Periodicidad")
        revisar(global_n.get("Meses"), cat.MESES, "Mes")
    for concepto in doc.iter(_q("Concepto")):
        revisar(concepto.get("ClaveProdServ"), cat.CLAVE_PROD_SERV, "Clave de producto o servicio")
        revisar(concepto.get("ClaveUnidad"), cat.CLAVE_UNIDAD, "Clave de unidad")
        revisar(concepto.get("ObjetoImp"), cat.OBJETO_IMPUESTO, "Objeto de impuesto")
    for traslado in doc.iter(_q("Traslado")):
        revisar(traslado.get("Impuesto"), cat.IMPUESTO, "Impuesto")
        revisar(traslado.get("TipoFactor"), cat.TIPO_FACTOR, "Tipo de factor")
        revisar(traslado.get("TasaOCuota"), cat.TASA_O_CUOTA, "Tasa o cuota")
    return errores


def validar_importes(xml: str, total_pedido: float) -> list[str]:
    """RQNF117: suma de importes de los conceptos + IVA trasladado = total del pedido."""
    doc = _leer(xml)
    importes = sum((Decimal(c.get("Importe")) for c in doc.iter(_q("Concepto"))), Decimal("0.00"))
    impuestos = doc.find(_q("Impuestos"))
    iva = Decimal(impuestos.get("TotalImpuestosTrasladados")) if impuestos is not None else Decimal("0.00")
    errores = []
    if importes + iva != _d(total_pedido):
        errores.append(f"Conceptos ({importes}) + IVA ({iva}) no es igual al total del pedido ({_d(total_pedido)})")
    if Decimal(doc.get("Total")) != _d(total_pedido):
        errores.append(f"El Total del comprobante ({doc.get('Total')}) no es igual al total del pedido")
    return errores


def validar(xml: str, total_pedido: float) -> list[str]:
    """Todas las validaciones; [] si la prefactura se puede poner a disposición."""
    errores = validar_nodos(xml) if xml else ["El XML está vacío"]
    if errores:
        return errores
    return validar_xsd(xml) + validar_catalogos(xml) + validar_importes(xml, total_pedido)


# =========================================================
# Representación impresa (PDF) — RQF93, RQF96, RQNF120
# =========================================================

def datos_de_xml(xml: str) -> dict:
    """Lee del XML guardado todo lo que muestra el PDF (no se usa el pedido)."""
    doc = _leer(xml)
    em, rec = doc.find(_q("Emisor")), doc.find(_q("Receptor"))
    impuestos = doc.find(_q("Impuestos"))
    return {
        "serie": doc.get("Serie"), "folio": doc.get("Folio"), "fecha": doc.get("Fecha"),
        "version": doc.get("Version"), "moneda": doc.get("Moneda"),
        "forma_pago": doc.get("FormaPago"), "metodo_pago": doc.get("MetodoPago"),
        "lugar": doc.get("LugarExpedicion"), "subtotal": doc.get("SubTotal"), "total": doc.get("Total"),
        "emisor": dict(em.attrib), "receptor": dict(rec.attrib),
        "conceptos": [
            {**dict(c.attrib),
             "traslados": [dict(t.attrib) for t in c.iter(_q("Traslado"))]}
            for c in doc.iter(_q("Concepto"))
        ],
        "total_iva": impuestos.get("TotalImpuestosTrasladados") if impuestos is not None else "0.00",
        "traslados": [dict(t.attrib) for t in impuestos.find(_q("Traslados"))] if impuestos is not None else [],
    }


def _latin1(texto) -> str:
    """Las fuentes base del PDF solo cubren Latin-1 (acentos y ñ sí)."""
    return str(texto).replace("—", "-").replace("–", "-").replace("«", '"').replace("»", '"') \
        .encode("latin-1", "replace").decode("latin-1")


def pdf(xml: str) -> bytes:
    """PDF de la prefactura generado SOLO a partir del XML guardado (RQNF120)."""
    from fpdf import FPDF

    d = datos_de_xml(xml)
    doc = FPDF(format="Letter")
    doc.set_auto_page_break(auto=True, margin=15)
    doc.add_page()
    doc.set_title(f"Prefactura {d['serie']}-{d['folio']}")

    def texto(t, tam=9, negrita=False, alto=5, ancho=0, alin="L", salto=True):
        doc.set_font("Helvetica", "B" if negrita else "", tam)
        doc.cell(ancho, alto, _latin1(t), align=alin, new_x="LMARGIN" if salto else "RIGHT",
                 new_y="NEXT" if salto else "TOP")

    texto("PREFACTURA (sin timbre fiscal)", 15, True, 8)
    texto(f"Serie {d['serie']}  Folio {d['folio']}  ·  Fecha {d['fecha']}  ·  Estructura CFDI {d['version']}", 9)
    texto("Este documento no es un comprobante fiscal: no tiene sello digital ni timbre del SAT.", 8)
    doc.ln(3)

    em, rec = d["emisor"], d["receptor"]
    texto("Emisor", 10, True)
    texto(f"{em.get('Nombre')}  ·  RFC {em.get('Rfc')}  ·  Régimen fiscal {em.get('RegimenFiscal')} "
          f"{cat.REGIMEN_FISCAL.get(em.get('RegimenFiscal'), '')}")
    texto(f"Lugar de expedición (CP): {d['lugar']}")
    doc.ln(2)
    texto("Receptor", 10, True)
    texto(f"{rec.get('Nombre')}  ·  RFC {rec.get('Rfc')}")
    texto(f"Régimen fiscal {rec.get('RegimenFiscalReceptor')} {cat.REGIMEN_FISCAL.get(rec.get('RegimenFiscalReceptor'), '')}"
          f"  ·  CP fiscal {rec.get('DomicilioFiscalReceptor')}")
    texto(f"Uso del CFDI {rec.get('UsoCFDI')} {cat.USO_CFDI.get(rec.get('UsoCFDI'), '')}")
    doc.ln(3)

    columnas = [("Clave", 20), ("Unidad", 14), ("Cant.", 12), ("Descripción", 72), ("Valor unit.", 26),
                ("Importe", 24), ("IVA", 28)]
    doc.set_fill_color(243, 229, 212)
    for titulo, ancho in columnas:
        texto(titulo, 8, True, 6, ancho, "C", salto=False)
    doc.ln(6)
    for c in d["conceptos"]:
        t = (c["traslados"] or [{}])[0]
        tasa = Decimal(t.get("TasaOCuota", "0")) * 100
        fila = [c.get("ClaveProdServ"), c.get("ClaveUnidad"), c.get("Cantidad"), c.get("Descripcion")[:48],
                c.get("ValorUnitario"), c.get("Importe"), f"{t.get('Importe', '0.00')} ({tasa:.0f}%)"]
        for (_, ancho), valor in zip(columnas, fila, strict=True):
            texto(valor, 8, False, 6, ancho, "L" if ancho == 72 else "R", salto=False)
        doc.ln(6)
    doc.ln(3)

    texto(f"Subtotal: ${d['subtotal']}", 10, alin="R")
    for t in d["traslados"]:
        tasa = Decimal(t.get("TasaOCuota")) * 100
        texto(f"IVA trasladado {tasa:.0f}% (base ${t.get('Base')}): ${t.get('Importe')}", 9, alin="R")
    texto(f"Total de impuestos trasladados: ${d['total_iva']}", 9, alin="R")
    texto(f"Total: ${d['total']} {d['moneda']}", 12, True, 7, alin="R")
    doc.ln(2)
    texto(f"Forma de pago {d['forma_pago']} {cat.FORMA_PAGO.get(d['forma_pago'], '')}  ·  "
          f"Método de pago {d['metodo_pago']} {cat.METODO_PAGO.get(d['metodo_pago'], '')}", 8)
    return bytes(doc.output())
