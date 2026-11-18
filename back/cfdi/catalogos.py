"""
cfdi/catalogos.py — extracto de los catálogos del SAT que usa la prefactura.

Fuente: catálogos del CFDI 4.0 publicados por el SAT en el Anexo 20 de la
Resolución Miscelánea Fiscal (catCFDI.xls) y en el esquema
http://www.sat.gob.mx/sitio_internet/cfd/catalogos/catCFDI.xsd, del que hay
copia local en cfdi/xsd/catCFDI.xsd. Aquí solo están las claves que usa la
tienda; cada una existe en el catálogo oficial (la validación XSD de
prefactura.py lo vuelve a comprobar contra catCFDI.xsd).

Las claves de producto o servicio (c_ClaveProdServ) siguen la clasificación
UNSPSC que adoptó el SAT.

RQNF115: prefactura.validar_catalogos() revisa cada clave de la prefactura
contra estos catálogos.
"""

# c_Moneda
MONEDA = {"MXN": "Peso Mexicano"}

# c_FormaPago
FORMA_PAGO = {
    "01": "Efectivo",
    "03": "Transferencia electrónica de fondos",
    "04": "Tarjeta de crédito",
    "28": "Tarjeta de débito",
    "31": "Intermediario pagos",
    "99": "Por definir",
}

# c_MetodoPago
METODO_PAGO = {"PUE": "Pago en una sola exhibición"}

# c_TipoDeComprobante
TIPO_COMPROBANTE = {"I": "Ingreso"}

# c_Exportacion
EXPORTACION = {"01": "No aplica"}

# c_ObjetoImp
OBJETO_IMPUESTO = {"02": "Sí objeto de impuesto"}

# c_Impuesto
IMPUESTO = {"002": "IVA"}

# c_TipoFactor
TIPO_FACTOR = {"Tasa": "Tasa"}

# c_TasaOCuota (IVA trasladado, tasa fija)
TASA_O_CUOTA = {"0.000000": "IVA tasa 0 %", "0.160000": "IVA tasa 16 %"}

# c_Periodicidad y c_Meses (nodo InformacionGlobal, solo para público en general)
PERIODICIDAD = {"01": "Diario"}
MESES = {f"{m:02d}": nombre for m, nombre in enumerate(
    ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
     "Septiembre", "Octubre", "Noviembre", "Diciembre"], start=1)}

# c_RegimenFiscal
REGIMEN_FISCAL = {
    "601": "General de Ley Personas Morales",
    "603": "Personas Morales con Fines no Lucrativos",
    "605": "Sueldos y Salarios e Ingresos Asimilados a Salarios",
    "606": "Arrendamiento",
    "607": "Régimen de Enajenación o Adquisición de Bienes",
    "608": "Demás ingresos",
    "610": "Residentes en el Extranjero sin Establecimiento Permanente en México",
    "611": "Ingresos por Dividendos (socios y accionistas)",
    "612": "Personas Físicas con Actividades Empresariales y Profesionales",
    "614": "Ingresos por intereses",
    "615": "Régimen de los ingresos por obtención de premios",
    "616": "Sin obligaciones fiscales",
    "620": "Sociedades Cooperativas de Producción que optan por diferir sus ingresos",
    "621": "Incorporación Fiscal",
    "622": "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras",
    "623": "Opcional para Grupos de Sociedades",
    "624": "Coordinados",
    "625": "Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas",
    "626": "Régimen Simplificado de Confianza",
}

# c_UsoCFDI (los que aplican a una compra en la tienda)
USO_CFDI = {
    "G01": "Adquisición de mercancías",
    "G03": "Gastos en general",
    "S01": "Sin efectos fiscales",
}

# Columna «Régimen Fiscal Receptor» de c_UsoCFDI: con qué regímenes se permite cada uso
_REGIMENES_EMPRESARIALES = {"601", "603", "606", "612", "620", "621", "622", "623", "624", "625", "626"}
USO_POR_REGIMEN = {
    "G01": _REGIMENES_EMPRESARIALES,
    "G03": _REGIMENES_EMPRESARIALES,
    "S01": set(REGIMEN_FISCAL),
}

# c_ClaveProdServ (las que usa el catálogo de la tienda y el envío)
CLAVE_PROD_SERV = {
    "50201706": "Café",
    "50201710": "Té",
    "50201711": "Té instantáneo",
    "50131702": "Productos de mantequilla o leche en conserva",
    "50202308": "Cocteles libres de alcohol o mezclas de bebidas",
    "52141526": "Cafeteras domésticas",
    "52141529": "Molinillos de café domésticos",
    "78102203": "Servicios de envío, entrega o recogida de correo",
}

# c_ClaveUnidad
CLAVE_UNIDAD = {
    "H87": "Pieza",
    "E48": "Unidad de servicio",
}

# Tasas de IVA que puede tener un producto (RQNF116)
TASAS_IVA = (0.0, 0.16)

# Envío: concepto aparte, siempre con 16 % (servicio de paquetería)
ENVIO_CLAVE_PROD_SERV = "78102203"
ENVIO_CLAVE_UNIDAD = "E48"
ENVIO_TASA_IVA = 0.16

# Valores por categoría para productos que aún no los tienen (bases de una
# entrega anterior). Café, leches y matcha son alimentos (tasa 0 %);
# los accesorios llevan 16 %.
POR_CATEGORIA = {
    1: {"tasa_iva": 0.0, "clave_prod_serv": "50201706", "clave_unidad": "H87"},   # Café en grano y molido
    2: {"tasa_iva": 0.0, "clave_prod_serv": "50131702", "clave_unidad": "H87"},   # Leches y alternativas
    3: {"tasa_iva": 0.0, "clave_prod_serv": "50201710", "clave_unidad": "H87"},   # Matcha
    4: {"tasa_iva": 0.16, "clave_prod_serv": "52141526", "clave_unidad": "H87"},  # Accesorios
}
POR_DEFECTO = {"tasa_iva": 0.16, "clave_prod_serv": "52141526", "clave_unidad": "H87"}

# Receptor genérico cuando el cliente no captura datos fiscales (RQNF112)
RFC_PUBLICO_GENERAL = "XAXX010101000"
NOMBRE_PUBLICO_GENERAL = "PUBLICO EN GENERAL"
REGIMEN_PUBLICO_GENERAL = "616"
USO_PUBLICO_GENERAL = "S01"

# Forma de pago según el método de la tienda
FORMA_PAGO_POR_METODO = {
    "mercadopago": "31",   # Mercado Pago cobra como intermediario (tarjeta, OXXO o saldo)
    "paypal": "31",
    "transferencia": "03",
    "efectivo": "01",
}


def lista(catalogo: dict) -> list[dict]:
    """[{clave, descripcion}] para los formularios del front."""
    return [{"clave": k, "descripcion": v} for k, v in catalogo.items()]
