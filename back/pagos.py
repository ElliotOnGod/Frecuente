"""
pagos.py — métodos de cobro del e-commerce Frecuente.

Métodos disponibles:

    mercadopago    Tarjeta de crédito/débito, OXXO o saldo (Checkout Pro)
    paypal         Cuenta PayPal o tarjeta dentro de PayPal (Orders API v2)
    transferencia  Transferencia SPEI — la tienda confirma el depósito
    efectivo       Pago en efectivo al recoger en la tienda

Cada método en línea funciona en uno de dos modos:

    simulado  (por defecto) No se conecta a nadie. El front muestra una
              "pasarela de prueba" donde se elige aprobar o rechazar el pago.
              Sirve para la demo en clase sin crear cuentas ni llaves.
    sandbox   Se conecta al entorno de PRUEBAS real de Mercado Pago / PayPal
              con las credenciales de .env (no se mueve dinero real).

El modo se elige con PAGOS_MODO en .env. Si pides "sandbox" pero faltan las
llaves de un proveedor, ese método se queda en "simulado" para no romper.

Regla de oro: el backend NUNCA confía en lo que el navegador dice del pago.
Cuando el cliente regresa de la pasarela, aquí se le pregunta directo al
proveedor (con nuestra llave secreta) si el pago existe, de qué pedido es,
de cuánto fue y en qué estado está.

Solo se usa la librería estándar (urllib), sin dependencias nuevas.

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
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

PAGOS_MODO = os.getenv("PAGOS_MODO", "simulado").strip().lower()
FRONT_URL = os.getenv("FRONT_URL", "http://localhost:4321").rstrip("/")
# URL pública del backend (por ejemplo con ngrok). Solo hace falta para
# que Mercado Pago mande avisos (webhooks); sin ella todo sigue funcionando.
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "").rstrip("/")

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "").strip()
# Correo del COMPRADOR DE PRUEBA de Mercado Pago (Tus integraciones →
# Cuentas de prueba → Comprador). En pruebas, Mercado Pago exige que el
# pagador sea una cuenta de prueba; si mandamos el correo real del cliente,
# el pago con tarjetas de prueba falla.
MP_COMPRADOR_PRUEBA = os.getenv("MP_COMPRADOR_PRUEBA", "").strip()
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
MP_API = "https://api.mercadopago.com"

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET", "")
PAYPAL_API = os.getenv("PAYPAL_API", "https://api-m.sandbox.paypal.com").rstrip("/")

TRANSFERENCIA = {
    "banco": os.getenv("TRANSFERENCIA_BANCO", "BBVA México"),
    "clabe": os.getenv("TRANSFERENCIA_CLABE", "012 320 00123456789 0"),
    "titular": os.getenv("TRANSFERENCIA_TITULAR", "Café Frecuente (cuenta de prueba)"),
}
TIENDA_DIRECCION = os.getenv(
    "TIENDA_DIRECCION", "Café Frecuente, Guadalajara, Jalisco (horario del local)"
)

MONEDA = "MXN"

# ---------------------------------------------------------
# Catálogo de métodos
# ---------------------------------------------------------
METODOS = {
    "mercadopago": {
        "nombre": "Mercado Pago",
        "descripcion": "Tarjeta de crédito o débito, OXXO o saldo de Mercado Pago.",
        "en_linea": True,
    },
    "paypal": {
        "nombre": "PayPal",
        "descripcion": "Paga con tu cuenta PayPal o con tarjeta dentro de PayPal.",
        "en_linea": True,
    },
    "transferencia": {
        "nombre": "Transferencia SPEI",
        "descripcion": "Te damos la CLABE y confirmamos tu pedido al ver el depósito.",
        "en_linea": False,
    },
    "efectivo": {
        "nombre": "Efectivo al recoger",
        "descripcion": "Apartamos tu pedido y pagas en el local al recogerlo.",
        "en_linea": False,
    },
}

# Estados del subdocumento pedido.pago
ESTADOS_PAGO = ["pendiente", "aprobado", "rechazado", "por_reembolsar", "reembolsado"]


class ErrorPago(Exception):
    """Falla al hablar con el proveedor; el mensaje se muestra al cliente."""


def modo_de(metodo: str) -> str:
    """'sandbox' si se pidió y hay llaves de ese proveedor; si no, 'simulado'.
    Los métodos fuera de línea no usan pasarela: regresan 'manual'."""
    if not METODOS.get(metodo, {}).get("en_linea"):
        return "manual"
    if PAGOS_MODO != "sandbox":
        return "simulado"
    if metodo == "mercadopago" and MP_ACCESS_TOKEN:
        return "sandbox"
    if metodo == "paypal" and PAYPAL_CLIENT_ID and PAYPAL_SECRET:
        return "sandbox"
    return "simulado"


def referencia_de(pedido_id: int) -> str:
    """Referencia legible para transferencias y para el local: FREC-000012."""
    return f"FREC-{pedido_id:06d}"


def referencia_membresia(membresia_id: int) -> str:
    """Referencia de una membresía: MEMB-000003."""
    return f"MEMB-{membresia_id:06d}"


# ---------------------------------------------------------
# "Cargo": lo que se cobra. Puede ser un pedido o una membresía.
# Las funciones de Mercado Pago y PayPal reciben el documento tal cual
# (con _id, total y pago) y, si es membresía, tres llaves extra:
#   _ref    referencia externa para el proveedor ("M3" en vez de "37")
#   _param  nombre del parámetro de regreso (?membresia=3 en vez de ?pedido=37)
#   _titulo texto que ve el cliente en la pasarela
# Un pedido no necesita nada extra: se usan los valores por defecto.
# ---------------------------------------------------------
def cargo_membresia(membresia: dict, plan_nombre: str) -> dict:
    return {
        **membresia,
        "_ref": f"M{membresia['_id']}",
        "_param": "membresia",
        "_titulo": f"Membresía {plan_nombre} ({referencia_membresia(membresia['_id'])}) - Frecuente",
    }


def _ref(cargo: dict) -> str:
    return cargo.get("_ref") or str(cargo["_id"])


def _param(cargo: dict) -> str:
    return cargo.get("_param", "pedido")


def _titulo(cargo: dict) -> str:
    return cargo.get("_titulo") or f"Pedido {referencia_de(cargo['_id'])} - Frecuente"


def instrucciones(metodo: str, referencia: int | str, total: float) -> list[tuple[str, str]]:
    """Datos que el cliente necesita para pagar fuera de línea.
    `referencia` es el id del pedido (int) o una referencia ya armada (str)."""
    if isinstance(referencia, int):
        referencia = referencia_de(referencia)
    monto = f"${total:,.2f} {MONEDA}"
    if metodo == "transferencia":
        return [
            ("Banco", TRANSFERENCIA["banco"]),
            ("CLABE", TRANSFERENCIA["clabe"]),
            ("Titular", TRANSFERENCIA["titular"]),
            ("Concepto / referencia", referencia),
            ("Monto exacto", monto),
        ]
    if metodo == "efectivo":
        return [
            ("Dónde", TIENDA_DIRECCION),
            ("Menciona la referencia", referencia),
            ("Monto a pagar", monto),
        ]
    return []


# ---------------------------------------------------------
# HTTP mínimo con urllib
# ---------------------------------------------------------
def _http(metodo: str, url: str, *, headers=None, json_body=None, form=None, timeout=20):
    headers = dict(headers or {})
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = urllib.request.Request(url, data=data, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            cuerpo = res.read().decode() or "{}"
            return res.status, json.loads(cuerpo)
    except urllib.error.HTTPError as e:
        try:
            cuerpo = json.loads(e.read().decode() or "{}")
        except ValueError:
            cuerpo = {}
        return e.code, cuerpo
    except (urllib.error.URLError, TimeoutError) as e:
        raise ErrorPago(f"No pudimos conectar con la pasarela de pago ({e}). Intenta de nuevo.")


def _monto_coincide(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) < 0.01


# ---------------------------------------------------------
# Mercado Pago (Checkout Pro)
# Docs: https://www.mercadopago.com.mx/developers/es/docs/checkout-pro
# ---------------------------------------------------------
def _mp_headers(idempotencia: str | None = None):
    h = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}
    if idempotencia:
        h["X-Idempotency-Key"] = idempotencia
    return h


def mp_crear_preferencia(pedido: dict, lineas: list[dict], email: str, intento: int = 1) -> dict:
    """Crea la 'preferencia' de pago y regresa {proveedor_id, url}."""
    regreso = f"{FRONT_URL}/pago/resultado?{_param(pedido)}={pedido['_id']}&metodo=mercadopago"
    cuerpo = {
        "items": [
            {
                "id": str(l["producto_id"]),
                "title": l["nombre"],
                "quantity": l["cantidad"],
                "unit_price": round(float(l["precio_unit"]), 2),
                "currency_id": MONEDA,
            }
            for l in lineas
        ],
        "external_reference": _ref(pedido),
        "statement_descriptor": "FRECUENTE",
        "back_urls": {"success": regreso, "pending": regreso, "failure": regreso},
    }
    # Pagador: este proyecto solo usa el entorno de PRUEBAS de Mercado Pago,
    # y ahí el pagador debe ser una cuenta de prueba. Por eso NO se manda el
    # correo real del cliente (`email`): se manda el del comprador de prueba
    # si lo configuraste, o ninguno (y en el checkout entras con esa cuenta).
    if MP_COMPRADOR_PRUEBA:
        cuerpo["payer"] = {"email": MP_COMPRADOR_PRUEBA}
    # Mercado Pago solo acepta auto_return con URLs públicas (https)
    if FRONT_URL.startswith("https://"):
        cuerpo["auto_return"] = "approved"
    if BACKEND_PUBLIC_URL:
        cuerpo["notification_url"] = f"{BACKEND_PUBLIC_URL}/webhooks/mercadopago"

    status, data = _http(
        "POST",
        f"{MP_API}/checkout/preferences",
        headers=_mp_headers(f"frec-pref-{_ref(pedido)}-{intento}"),
        json_body=cuerpo,
    )
    if status >= 300 or "id" not in data:
        raise ErrorPago(f"Mercado Pago rechazó la solicitud: {data.get('message', status)}")
    # Con credenciales de prueba (TEST-…) el checkout de pruebas es
    # sandbox_init_point; con las de un usuario de prueba (APP_USR-…) es init_point.
    if mp_es_prueba():
        url = data.get("sandbox_init_point") or data.get("init_point")
    else:
        url = data.get("init_point") or data.get("sandbox_init_point")
    return {"proveedor_id": data["id"], "url": url}


def mp_es_prueba() -> bool:
    """True si el Access Token es de pruebas (TEST-…)."""
    return MP_ACCESS_TOKEN.startswith("TEST-")


def _mp_traducir(status: str) -> str:
    return {
        "approved": "aprobado",
        "authorized": "pendiente",
        "pending": "pendiente",
        "in_process": "pendiente",
        "in_mediation": "pendiente",
        "rejected": "rechazado",
        "cancelled": "rechazado",
        "refunded": "reembolsado",
        "charged_back": "reembolsado",
    }.get(status, "pendiente")


def mp_consultar(pedido: dict, payment_id: str | None) -> dict:
    """Pregunta a Mercado Pago por el pago de este pedido.
    Regresa {estado, detalle, pago_id}."""
    if payment_id:
        status, data = _http("GET", f"{MP_API}/v1/payments/{payment_id}", headers=_mp_headers())
        if status >= 300:
            raise ErrorPago("Mercado Pago no encontró ese pago.")
        pagos = [data]
    else:
        # El cliente regresó sin payment_id: se busca por nuestro número de pedido
        q = urllib.parse.urlencode(
            {"external_reference": _ref(pedido), "sort": "date_created", "criteria": "desc"}
        )
        status, data = _http("GET", f"{MP_API}/v1/payments/search?{q}", headers=_mp_headers())
        if status >= 300:
            raise ErrorPago("No pudimos consultar el pago en Mercado Pago.")
        pagos = data.get("results", [])
        if not pagos:
            return {"estado": "pendiente", "detalle": "Sin pago registrado todavía", "pago_id": ""}

    # Si hay varios intentos, gana el aprobado; si no, el más reciente
    pago = next((p for p in pagos if p.get("status") == "approved"), pagos[0])

    if str(pago.get("external_reference")) != _ref(pedido):
        raise ErrorPago("Ese pago no corresponde a este pedido.")
    if pago.get("currency_id") != MONEDA or not _monto_coincide(
        pago.get("transaction_amount", 0), pedido["total"]
    ):
        raise ErrorPago("El monto del pago no coincide con el pedido.")

    return {
        "estado": _mp_traducir(pago.get("status", "")),
        "detalle": f"{pago.get('status')} / {pago.get('status_detail', '')}".strip(" /"),
        "pago_id": str(pago.get("id", "")),
    }


def mp_firma_valida(x_signature: str, x_request_id: str, data_id: str) -> bool:
    """Valida la firma del webhook (header x-signature: 'ts=...,v1=...').
    Si no configuraste MP_WEBHOOK_SECRET no se valida (igual se consulta
    el pago directo a Mercado Pago antes de cambiar nada)."""
    if not MP_WEBHOOK_SECRET:
        return True
    partes = dict(p.strip().split("=", 1) for p in x_signature.split(",") if "=" in p)
    ts, v1 = partes.get("ts", ""), partes.get("v1", "")
    manifiesto = f"id:{data_id.lower()};request-id:{x_request_id};ts:{ts};"
    esperado = hmac.new(MP_WEBHOOK_SECRET.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)


# ---------------------------------------------------------
# PayPal (Orders API v2)
# Docs: https://developer.paypal.com/docs/api/orders/v2/
# ---------------------------------------------------------
def _paypal_token() -> str:
    basico = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_SECRET}".encode()).decode()
    status, data = _http(
        "POST",
        f"{PAYPAL_API}/v1/oauth2/token",
        headers={"Authorization": f"Basic {basico}"},
        form={"grant_type": "client_credentials"},
    )
    if status >= 300 or "access_token" not in data:
        raise ErrorPago("PayPal rechazó nuestras credenciales. Revisa PAYPAL_CLIENT_ID y PAYPAL_SECRET.")
    return data["access_token"]


def paypal_crear_orden(pedido: dict, intento: int = 1) -> dict:
    """Crea la orden en PayPal y regresa {proveedor_id, url} (link de aprobación)."""
    token = _paypal_token()
    regreso = f"{FRONT_URL}/pago/resultado?{_param(pedido)}={pedido['_id']}&metodo=paypal"
    cuerpo = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": _ref(pedido),
                "custom_id": _ref(pedido),
                "description": _titulo(pedido),
                "amount": {"currency_code": MONEDA, "value": f"{pedido['total']:.2f}"},
            }
        ],
        "application_context": {
            "brand_name": "Frecuente",
            "locale": "es-MX",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "PAY_NOW",
            "return_url": regreso,
            "cancel_url": regreso + "&cancelado=1",
        },
    }
    status, data = _http(
        "POST",
        f"{PAYPAL_API}/v2/checkout/orders",
        headers={
            "Authorization": f"Bearer {token}",
            "PayPal-Request-Id": f"frec-orden-{_ref(pedido)}-{intento}",
        },
        json_body=cuerpo,
    )
    if status >= 300 or "id" not in data:
        raise ErrorPago(f"PayPal rechazó la solicitud: {data.get('message', status)}")
    url = next(
        (l["href"] for l in data.get("links", []) if l.get("rel") in ("approve", "payer-action")),
        None,
    )
    if not url:
        raise ErrorPago("PayPal no regresó el enlace de pago.")
    return {"proveedor_id": data["id"], "url": url}


def paypal_capturar(pedido: dict, orden_id: str) -> dict:
    """Cobra (captura) la orden que el cliente aprobó. Regresa {estado, detalle, pago_id}."""
    if orden_id != pedido.get("pago", {}).get("proveedor_id"):
        raise ErrorPago("Esa orden de PayPal no corresponde a este pedido.")

    token = _paypal_token()
    headers = {"Authorization": f"Bearer {token}", "PayPal-Request-Id": f"cap-{orden_id}"}
    status, data = _http(
        "POST", f"{PAYPAL_API}/v2/checkout/orders/{orden_id}/capture", headers=headers, json_body={}
    )
    if status == 422:
        # Ya se había capturado (recargaron la página) o aún no la aprueban
        status, data = _http("GET", f"{PAYPAL_API}/v2/checkout/orders/{orden_id}", headers=headers)
    if status >= 300:
        raise ErrorPago(f"PayPal no pudo completar el cobro: {data.get('message', status)}")

    estado_orden = data.get("status", "")
    unidad = (data.get("purchase_units") or [{}])[0]
    captura = ((unidad.get("payments") or {}).get("captures") or [{}])[0]

    if estado_orden == "COMPLETED" and captura.get("status") == "COMPLETED":
        monto = captura.get("amount", {})
        if monto.get("currency_code") != MONEDA or not _monto_coincide(
            monto.get("value", 0), pedido["total"]
        ):
            raise ErrorPago("El monto cobrado por PayPal no coincide con el pedido.")
        return {"estado": "aprobado", "detalle": "COMPLETED", "pago_id": captura.get("id", "")}
    if estado_orden in ("APPROVED", "CREATED", "SAVED", "PAYER_ACTION_REQUIRED") or captura.get(
        "status"
    ) == "PENDING":
        return {"estado": "pendiente", "detalle": estado_orden, "pago_id": captura.get("id", "")}
    return {"estado": "rechazado", "detalle": estado_orden or "DECLINED", "pago_id": ""}
