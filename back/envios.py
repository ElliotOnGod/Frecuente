"""
envios.py — envíos a domicilio con la API de Envia.com.

Qué hace:
  1. buscar_cp(cp)        → estado, ciudad y colonias de un código postal
                            (geocodes.envia.com, público: funciona siempre).
  2. cotizar(destino, …)  → precios reales de varias paqueterías
                            (POST /ship/rate/, una llamada por paquetería).
  3. generar_guia(pedido) → crea la guía (número de rastreo + etiqueta PDF)
                            cuando el admin marca el pedido como enviado
                            (POST /ship/generate/).
  4. rastrear(…)          → estado del envío (POST /ship/generaltrack/).

Modos, igual que los pagos:
  - simulado (sin ENVIA_TOKEN): precios calculados aquí con una tabla por
    peso y zona, y guías de prueba "SIM…". Sirve para la demo sin cuenta.
  - sandbox  (con ENVIA_TOKEN): entorno de PRUEBAS real de Envia
    (api-test.envia.com). Con ENVIA_API=https://api.envia.com sería real.

¿Cómo sabemos que el cliente no cambió el precio del envío en el navegador?
Cada opción cotizada viaja con una FIRMA (HMAC con la clave del servidor,
la misma idea que el código del día de las membresías). Al registrar el
pedido se verifica la firma, que no haya expirado, que sea para el mismo
código postal y para el mismo peso del carrito. Si algo no cuadra, se
rechaza: el precio del envío lo decide el servidor, no el navegador.

Equipo: Jehu Uribe Bermudez (23100139),
        Jose Fernando Leon Lopez (23100146),
        Elliot Garcia Lopez (22300923)
Materia: Programacion Web II - CETI Colomos
"""

import base64
import hashlib
import hmac
import json
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

from auth import JWT_SECRET

load_dotenv(Path(__file__).resolve().parent / ".env")

ENVIA_TOKEN = os.getenv("ENVIA_TOKEN", "").strip()
ENVIA_API = os.getenv("ENVIA_API", "https://api-test.envia.com").rstrip("/")
ENVIA_GEOCODES = "https://geocodes.envia.com"
# En el sandbox de Envia, Estafeta solo cotiza (al generar la guía responde
# SERVICE_QUOTE_ONLY); FedEx y DHL sí generan guía y etiqueta de prueba.
_PAQUETERIAS_DEFECTO = "fedex,dhl" if "api-test" in ENVIA_API else "estafeta,fedex,dhl"
PAQUETERIAS = [p.strip() for p in os.getenv("ENVIA_PAQUETERIAS", _PAQUETERIAS_DEFECTO).split(",") if p.strip()]

# Origen de todos los envíos: el local (mismos datos que el mapa)
ORIGEN = {
    "name": "Frecuente Café Bar",
    "company": "Frecuente",
    "email": os.getenv("CORREO_TIENDA", "hola@frecuente.mx"),
    "phone": os.getenv("TIENDA_TELEFONO", "3300000000"),
    "street": "C. Justo Sierra",
    "number": "2665",
    "district": "Arcos Vallarta",
    "city": "Guadalajara",
    "state": "JA",
    "country": "MX",
    "postalCode": "44650",
}

USER_AGENT = "FrecuenteTienda/1.0 (+https://github.com/ElliotOnGod/Frecuente)"
COTIZACION_MINUTOS = 30          # cuánto dura válida una cotización
PESO_EMPAQUE_KG = 0.2
PESO_DEFECTO_KG = 0.5

# Estados de México con su código de 2 letras (el que usa Envia)
ESTADOS_MX = {
    "AG": "Aguascalientes", "BC": "Baja California", "BS": "Baja California Sur", "CM": "Campeche",
    "CS": "Chiapas", "CH": "Chihuahua", "CX": "Ciudad de México", "CO": "Coahuila", "CL": "Colima",
    "DG": "Durango", "GT": "Guanajuato", "GR": "Guerrero", "HG": "Hidalgo", "JA": "Jalisco",
    "EM": "Estado de México", "MI": "Michoacán", "MO": "Morelos", "NA": "Nayarit", "NL": "Nuevo León",
    "OA": "Oaxaca", "PU": "Puebla", "QT": "Querétaro", "QR": "Quintana Roo", "SL": "San Luis Potosí",
    "SI": "Sinaloa", "SO": "Sonora", "TB": "Tabasco", "TM": "Tamaulipas", "TL": "Tlaxcala",
    "VE": "Veracruz", "YU": "Yucatán", "ZA": "Zacatecas",
}
VECINOS_JA = {"NA", "CL", "MI", "GT", "AG", "ZA"}

# Simulado: (paquetería, servicio, descripción, base, por kg extra, días local, días foráneo)
_TABLA_SIMULADA = [
    ("estafeta", "terrestre", "Estafeta Terrestre", 119.0, 22.0, "2-3 días", "3-5 días"),
    ("fedex", "express", "FedEx Express", 165.0, 30.0, "1-2 días", "1-3 días"),
    ("dhl", "express", "DHL Express", 189.0, 34.0, "1 día", "1-2 días"),
]


class ErrorEnvio(Exception):
    """Algo falló al cotizar o generar la guía; el mensaje se le muestra al usuario."""


def modo() -> str:
    return "sandbox" if ENVIA_TOKEN else "simulado"


def _sin_acentos(valor):
    """Envia.com truena ("Malformed UTF-8 characters") si los datos llevan
    acentos o ñ. Se mandan sin ellos: "Ladrón de Guevara" → "Ladron de Guevara"."""
    if isinstance(valor, str):
        return unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode()
    if isinstance(valor, dict):
        return {k: _sin_acentos(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_sin_acentos(v) for v in valor]
    return valor


def _http(metodo: str, url: str, cuerpo: dict | None = None, timeout: int = 20) -> tuple[int, dict | list]:
    import urllib.error
    import urllib.request

    datos = json.dumps(_sin_acentos(cuerpo)).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo)
    req.add_header("Accept", "application/json")
    # Cloudflare (delante de Envia) bloquea el User-Agent por defecto de Python
    req.add_header("User-Agent", USER_AGENT)
    if datos is not None:
        req.add_header("Content-Type", "application/json")
    if ENVIA_TOKEN and url.startswith(ENVIA_API):
        req.add_header("Authorization", f"Bearer {ENVIA_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise ErrorEnvio(f"No pudimos conectar con Envia.com ({e.__class__.__name__})")


# =========================================================
# 1. Código postal
# =========================================================

_cache_cp: dict[str, dict] = {}


def buscar_cp(cp: str) -> dict:
    """{cp, estado (código), estado_nombre, ciudad, colonias[]} de un CP de México."""
    cp = (cp or "").strip()
    if not re.fullmatch(r"\d{5}", cp):
        raise ErrorEnvio("El código postal debe tener 5 dígitos")
    if cp in _cache_cp:
        return _cache_cp[cp]
    status, data = _http("GET", f"{ENVIA_GEOCODES}/zipcode/MX/{cp}", timeout=10)
    registro = data[0] if isinstance(data, list) and data else (data.get("data") if isinstance(data, dict) else None)
    if status >= 300 or not registro:
        raise ErrorEnvio("No encontramos ese código postal")
    estado = registro.get("state") or {}
    codigo = (estado.get("code") or {}).get("2digit") if isinstance(estado, dict) else str(estado)
    info = {
        "cp": cp,
        "estado": codigo or "",
        "estado_nombre": (estado.get("name") if isinstance(estado, dict) else "") or ESTADOS_MX.get(codigo or "", ""),
        "ciudad": registro.get("locality") or registro.get("city") or "",
        "colonias": sorted(registro.get("suburbs") or []),
    }
    _cache_cp[cp] = info
    return info


# =========================================================
# 2. Cotizar
# =========================================================

def peso_de(lineas: list[dict], pesos: dict[int, float]) -> float:
    """Peso del paquete: lo de cada producto × cantidad + el empaque, redondeado a 0.1 kg."""
    kg = sum(pesos.get(l["producto_id"], PESO_DEFECTO_KG) * l["cantidad"] for l in lineas) + PESO_EMPAQUE_KG
    return round(max(kg, 0.5), 1)


def _paquete(kg: float, valor: float) -> dict:
    caja = (25, 20, 15) if kg <= 2 else (35, 30, 25) if kg <= 6 else (45, 40, 35)
    return {
        "type": "box",
        "content": "Café y accesorios",
        "amount": 1,
        "declaredValue": round(valor, 2),
        "lengthUnit": "CM",
        "weightUnit": "KG",
        "weight": kg,
        "dimensions": {"length": caja[0], "width": caja[1], "height": caja[2]},
    }


def _mensaje_envia(status: int, data) -> str:
    """El motivo que da Envia cuando rechaza una petición."""
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("description") or error)[:200]
        if error:
            return str(error)[:200]
        if data.get("description") or data.get("message"):
            return str(data.get("description") or data.get("message"))[:200]
        if not data.get("data"):
            return f"HTTP {status}, sin tarifas"
    return f"HTTP {status}"


def _destino(d: dict) -> dict:
    return {
        "name": d.get("nombre") or "Cliente Frecuente",
        "phone": d.get("telefono") or "3300000000",
        "street": d.get("calle", ""),
        "number": d.get("numero", ""),
        "district": d.get("colonia", ""),
        "city": d.get("ciudad", ""),
        "state": d.get("estado", ""),
        "country": "MX",
        "postalCode": d.get("cp", ""),
        "reference": d.get("referencias", ""),
    }


def _cotizar_simulado(destino: dict, kg: float) -> list[dict]:
    estado = destino.get("estado", "")
    local = estado == "JA"
    zona = 0.0 if local else (25.0 if estado in VECINOS_JA else 55.0)
    extra = max(0.0, kg - 1.0)
    return [
        {
            "paqueteria": p,
            "servicio": s,
            "descripcion": desc,
            "dias": d_local if local else d_foraneo,
            "costo": round(base + zona + extra * por_kg, 2),
        }
        for p, s, desc, base, por_kg, d_local, d_foraneo in _TABLA_SIMULADA
    ]


def _cotizar_envia(destino: dict, kg: float, valor: float) -> list[dict]:
    # Al cotizar todavía no hay calle ni número: Envia los pide, así que se
    # manda un domicilio genérico en ese CP (el precio depende del CP y el peso).
    destino_cotizar = {
        "nombre": "Cliente Frecuente",
        "telefono": ORIGEN["phone"],
        "calle": "Domicilio",
        "numero": "1",
        "colonia": destino.get("colonia") or "Centro",
        **{k: v for k, v in destino.items() if v},
    }
    errores: list[str] = []

    def una(paqueteria: str) -> list[dict]:
        cuerpo = {
            "origin": ORIGEN,
            "destination": _destino(destino_cotizar),
            "packages": [_paquete(kg, valor)],
            "shipment": {"type": 1, "carrier": paqueteria},
            "settings": {"currency": "MXN"},
        }
        try:
            status, data = _http("POST", f"{ENVIA_API}/ship/rate/", cuerpo)
        except ErrorEnvio as e:
            errores.append(f"{paqueteria}: {e}")
            return []
        if status >= 300 or not isinstance(data, dict) or not data.get("data"):
            errores.append(f"{paqueteria}: {_mensaje_envia(status, data)}")
            return []
        return [
            {
                "paqueteria": r.get("carrier", paqueteria),
                "servicio": r.get("service", ""),
                "descripcion": (r.get("serviceDescription") or f"{paqueteria} {r.get('service', '')}").strip(),
                "dias": str(r.get("deliveryEstimate") or ""),
                "costo": round(float(r.get("totalPrice") or 0), 2),
            }
            for r in data.get("data") or []
            if r.get("totalPrice") is not None and (r.get("currency") or "MXN") == "MXN"
            # Solo puerta a puerta: los servicios "ocurre" piden llevar el
            # paquete a una sucursal y un código de sucursal que no tenemos
            and not r.get("dropOff") and not r.get("branchType")
            and "ocurre" not in str(r.get("serviceDescription", "")).lower()
        ]

    # Una petición por paquetería, todas al mismo tiempo
    with ThreadPoolExecutor(max_workers=len(PAQUETERIAS) or 1) as ex:
        opciones = [o for lista in ex.map(una, PAQUETERIAS) for o in lista]
    if not opciones:
        detalle = "; ".join(errores)[:300]
        print(f"[frecuente] Envia no cotizó: {detalle}")
        raise ErrorEnvio(f"Ninguna paquetería pudo cotizar ese destino ({detalle})" if detalle
                         else "Ninguna paquetería pudo cotizar ese destino; revisa la dirección")
    return opciones


def cotizar(destino: dict, kg: float, valor: float) -> list[dict]:
    """Opciones de envío ordenadas por precio, cada una con su firma."""
    if not re.fullmatch(r"\d{5}", destino.get("cp", "")):
        raise ErrorEnvio("El código postal debe tener 5 dígitos")
    if destino.get("estado") not in ESTADOS_MX:
        raise ErrorEnvio("Elige el estado de la dirección")
    opciones = _cotizar_simulado(destino, kg) if modo() == "simulado" else _cotizar_envia(destino, kg, valor)
    opciones.sort(key=lambda o: o["costo"])
    opciones = opciones[:6]
    for o in opciones:
        o["token"] = firmar(o, destino["cp"], kg)
        o["modo"] = modo()
    return opciones


# ---- firma de la cotización ----

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _de_b64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _hmac(datos: bytes) -> str:
    return _b64(hmac.new(JWT_SECRET.encode(), b"envio:" + datos, hashlib.sha256).digest())


def firmar(opcion: dict, cp: str, kg: float) -> str:
    carga = {
        "p": opcion["paqueteria"], "s": opcion["servicio"], "d": opcion["descripcion"],
        "t": opcion["dias"], "c": opcion["costo"], "cp": cp, "kg": kg,
        "m": modo(), "exp": int(time.time()) + COTIZACION_MINUTOS * 60,
    }
    datos = json.dumps(carga, separators=(",", ":"), sort_keys=True).encode()
    return f"{_b64(datos)}.{_hmac(datos)}"


def verificar(token: str, cp: str, kg: float) -> dict:
    """Regresa la opción firmada si la firma es buena y coincide con el pedido."""
    try:
        parte, firma = (token or "").split(".")
        datos = _de_b64(parte)
    except (ValueError, TypeError):
        raise ErrorEnvio("Elige una opción de envío")
    if not hmac.compare_digest(firma, _hmac(datos)):
        raise ErrorEnvio("La cotización del envío no es válida; vuelve a cotizar")
    carga = json.loads(datos)
    if carga["exp"] < time.time():
        raise ErrorEnvio("La cotización del envío expiró; vuelve a cotizar")
    if carga["cp"] != cp:
        raise ErrorEnvio("La cotización es de otro código postal; vuelve a cotizar")
    if abs(float(carga["kg"]) - kg) > 0.05:
        raise ErrorEnvio("Tu carrito cambió desde que cotizaste; vuelve a cotizar el envío")
    return {
        "paqueteria": carga["p"], "servicio": carga["s"], "descripcion": carga["d"],
        "dias": carga["t"], "costo": float(carga["c"]), "modo": carga.get("m", "simulado"),
    }


# =========================================================
# 3. Guía  y  4. Rastreo
# =========================================================

def generar_guia(pedido: dict, kg: float) -> dict:
    """{guia, rastreo_url, etiqueta_url} del envío de un pedido."""
    entrega = pedido.get("entrega") or {}
    if entrega.get("tipo") != "domicilio":
        raise ErrorEnvio("Este pedido se recoge en el local; no lleva guía")
    if entrega.get("guia"):
        return {k: entrega.get(k, "") for k in ("guia", "rastreo_url", "etiqueta_url")}
    if modo() == "simulado" or entrega.get("modo") == "simulado":
        guia = f"SIM{pedido['_id']:06d}{int(time.time()) % 10000:04d}"
        return {"guia": guia, "rastreo_url": "", "etiqueta_url": ""}

    cuerpo = {
        "origin": ORIGEN,
        "destination": _destino(entrega),
        "packages": [_paquete(kg, pedido.get("subtotal", pedido["total"]))],
        "shipment": {"type": 1, "carrier": entrega["paqueteria"], "service": entrega["servicio"]},
        "settings": {"currency": "MXN", "printFormat": "PDF", "printSize": "STOCK_4X6"},
    }
    status, data = _http("POST", f"{ENVIA_API}/ship/generate/", cuerpo, timeout=40)
    filas = data.get("data") if isinstance(data, dict) else None
    if status >= 300 or not filas or (isinstance(data, dict) and data.get("meta") == "error"):
        motivo = _mensaje_envia(status, data)
        if "QUOTE_ONLY" in motivo:
            motivo = f"{entrega.get('descripcion') or entrega['paqueteria']} solo cotiza en este entorno; usa FedEx o DHL"
        raise ErrorEnvio(f"Envia.com no generó la guía: {motivo}")
    g = filas[0]
    return {
        "guia": str(g.get("trackingNumber") or ""),
        "rastreo_url": g.get("trackUrl") or "",
        "etiqueta_url": g.get("label") or "",
    }


_PASOS_SIMULADOS = {
    "pagado": ["Pedido pagado; lo estamos preparando"],
    "enviado": ["Pedido pagado; lo estamos preparando", "Guía generada", "Recolectado por la paquetería", "En tránsito"],
    "entregado": [
        "Pedido pagado; lo estamos preparando", "Guía generada", "Recolectado por la paquetería",
        "En tránsito", "En ruta de entrega", "Entregado",
    ],
}


# Estados de Envia en español (los demás se muestran tal cual)
_ESTADOS_ENVIA = {
    "created": "Guía creada",
    "pending": "Pendiente de recolección",
    "picked up": "Recolectado por la paquetería",
    "shipped": "En tránsito",
    "in transit": "En tránsito",
    "out for delivery": "En ruta de entrega",
    "delivered": "Entregado",
    "canceled": "Cancelado",
    "cancelled": "Cancelado",
    "returned": "Devuelto",
}


def rastrear(pedido: dict) -> dict:
    """{estado, eventos: [{fecha, descripcion, lugar}]}."""
    entrega = pedido.get("entrega") or {}
    guia = entrega.get("guia", "")
    if not guia or entrega.get("modo") == "simulado" or modo() == "simulado":
        pasos = _PASOS_SIMULADOS.get(pedido["estado"], ["Esperando pago"])
        return {
            "estado": pasos[-1],
            "eventos": [{"fecha": "", "descripcion": p, "lugar": ""} for p in reversed(pasos)],
        }
    status, data = _http("POST", f"{ENVIA_API}/ship/generaltrack/", {"trackingNumbers": [guia]})
    filas = data.get("data") if isinstance(data, dict) else None
    if status >= 300 or not filas:
        raise ErrorEnvio("La paquetería todavía no tiene información de esta guía")
    r = filas[0]
    eventos = r.get("eventHistory") or r.get("events") or []
    return {
        "estado": _ESTADOS_ENVIA.get(str(r.get("status") or "").lower(), str(r.get("status") or r.get("statusName") or "En proceso")),
        "eventos": [
            {
                "fecha": str(e.get("date") or e.get("datetime") or ""),
                "descripcion": str(e.get("event") or e.get("description") or ""),
                "lugar": str(e.get("location") or ""),
            }
            for e in eventos
        ],
    }
