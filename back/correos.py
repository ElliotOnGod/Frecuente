"""
correos.py — correos automáticos con la API de Brevo.

Cuándo se manda un correo:
  - bienvenida          → al crear una cuenta
  - pedido_nuevo_tienda → a la tienda (CORREO_TIENDA), con cada pedido nuevo
  - pedido_confirmado   → al cliente, cuando su pago se aprueba
  - pedido_enviado      → al cliente, con la paquetería y el número de guía
  - membresia_activada  → al cliente, con su plan y cómo usar el código del día
  - recompra_lista      → al cliente, cuando su suscripción genera el pedido del mes

Modos:
  - simulado (sin BREVO_API_KEY): no sale nada a internet; el correo se
    anota en la tabla `correos` y se imprime en la consola.
  - brevo: POST https://api.brevo.com/v3/smtp/email con la llave.
    El remitente (BREVO_REMITENTE) debe estar verificado en Brevo
    (Senders, Domains & Dedicated IPs → Senders). No hace falta dominio propio.

El envío se hace en un hilo aparte: el cliente no espera a que Brevo
responda para ver su pedido. Cada intento queda en la bitácora `correos`
de PostgreSQL (enviado / simulado / error), que el admin ve en el panel.

Equipo: Jehu Uribe Bermudez (23100139),
        Jose Fernando Leon Lopez (23100146),
        Elliot Garcia Lopez (22300923)
Materia: Programacion Web II - CETI Colomos
"""

import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html import escape
from pathlib import Path

from dotenv import load_dotenv

import relacional

load_dotenv(Path(__file__).resolve().parent / ".env")

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()
BREVO_API = "https://api.brevo.com/v3/smtp/email"
REMITENTE = os.getenv("BREVO_REMITENTE", "").strip()
REMITENTE_NOMBRE = os.getenv("BREVO_REMITENTE_NOMBRE", "Frecuente Café").strip()
CORREO_TIENDA = os.getenv("CORREO_TIENDA", "").strip()
FRONT_URL = os.getenv("FRONT_URL", "http://localhost:4321").rstrip("/")
SINCRONO = os.getenv("CORREOS_SINCRONO", "").lower() in ("1", "true", "si")

_hilos = ThreadPoolExecutor(max_workers=2, thread_name_prefix="correos")


def modo() -> str:
    return "brevo" if BREVO_API_KEY and REMITENTE else "simulado"


def enviar(destinatario: str, nombre: str, asunto: str, cuerpo_html: str, plantilla: str, pedido_id=None) -> None:
    """Encola el correo. Nunca truena: un fallo de Brevo no debe tumbar una compra."""
    if not destinatario:
        return
    trabajo = (destinatario, nombre, asunto, cuerpo_html, plantilla, pedido_id)
    if SINCRONO:
        _enviar_ahora(*trabajo)
    else:
        _hilos.submit(_enviar_ahora, *trabajo)


def _log(texto: str) -> None:
    """print que no truena si la consola no soporta algún carácter (Windows cp1252)."""
    try:
        print(texto)
    except UnicodeEncodeError:
        print(texto.encode("ascii", "replace").decode())


def _enviar_ahora(destinatario, nombre, asunto, cuerpo_html, plantilla, pedido_id) -> None:
    try:
        _enviar(destinatario, nombre, asunto, cuerpo_html, plantilla, pedido_id)
    except Exception as e:  # en un hilo, un error se perdería en silencio
        _log(f"[frecuente] Error al mandar el correo '{plantilla}' a {destinatario}: {e!r}")


def _enviar(destinatario, nombre, asunto, cuerpo_html, plantilla, pedido_id) -> None:
    html = _marco(asunto, cuerpo_html)
    estado, proveedor_id, detalle = "simulado", "", ""
    if modo() == "brevo":
        cuerpo = {
            "sender": {"name": REMITENTE_NOMBRE, "email": REMITENTE},
            "to": [{"email": destinatario, "name": nombre or destinatario}],
            "subject": asunto,
            "htmlContent": html,
            "tags": [plantilla],
        }
        req = urllib.request.Request(BREVO_API, data=json.dumps(cuerpo).encode(), method="POST")
        req.add_header("api-key", BREVO_API_KEY)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "FrecuenteTienda/1.0 (+https://github.com/ElliotOnGod/Frecuente)")
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                proveedor_id = str(json.loads(r.read() or b"{}").get("messageId", ""))
                estado = "enviado"
        except urllib.error.HTTPError as e:
            estado = "error"
            try:
                detalle = json.loads(e.read() or b"{}").get("message", "") or f"HTTP {e.code}"
            except ValueError:
                detalle = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError) as e:
            estado, detalle = "error", f"Sin conexión con Brevo ({e.__class__.__name__})"
    else:
        _log(f"[frecuente] Correo simulado para {destinatario}: {asunto}")
    try:
        relacional.registrar_correo(destinatario, asunto, plantilla, estado, proveedor_id, detalle, pedido_id)
    except Exception as e:  # la bitácora tampoco debe tumbar nada
        _log(f"[frecuente] No se pudo anotar el correo: {e}")


# =========================================================
# Plantillas (colores del manual de marca)
# =========================================================

ESPRESSO, CREMA, TOSTADO, HOJA = "#3E2A20", "#F3E5D4", "#8B5E3C", "#4F7A52"


def _dinero(n) -> str:
    return f"${float(n):,.2f} MXN"


def _marco(titulo: str, cuerpo: str) -> str:
    return f"""<!doctype html><html lang="es"><body style="margin:0;background:{CREMA};font-family:Arial,Helvetica,sans-serif;color:{ESPRESSO}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border-radius:12px;overflow:hidden">
<tr><td style="background:{ESPRESSO};color:{CREMA};padding:20px 24px;font-size:20px;font-weight:bold;letter-spacing:.5px">Frecuente</td></tr>
<tr><td style="padding:24px"><h1 style="font-size:20px;margin:0 0 12px">{escape(titulo)}</h1>{cuerpo}</td></tr>
<tr><td style="padding:16px 24px;background:{CREMA};font-size:12px;color:{TOSTADO}">Frecuente Café Bar · C. Justo Sierra 2665, Arcos Vallarta, Guadalajara, Jal.<br>Recibes este correo por una compra o cuenta en Frecuente.</td></tr>
</table></td></tr></table></body></html>"""


def _boton(texto: str, url: str) -> str:
    return (
        f'<p style="margin:20px 0"><a href="{escape(url)}" style="background:{TOSTADO};color:#fff;'
        f'text-decoration:none;padding:12px 18px;border-radius:8px;display:inline-block">{escape(texto)}</a></p>'
    )


def _tabla_items(pedido: dict) -> str:
    filas = "".join(
        f"<tr><td style='padding:6px 0'>{escape(i['nombre'])}"
        f"{' · ' + escape(i['variante']) if i.get('variante') else ''} × {i['cantidad']}</td>"
        f"<td align='right'>{_dinero(i['cantidad'] * i['precio_unit'])}</td></tr>"
        for i in pedido["items"]
    )
    envio = (
        f"<tr><td style='padding:6px 0'>Envío</td><td align='right'>{_dinero(pedido.get('envio', 0))}</td></tr>"
        if pedido.get("envio")
        else ""
    )
    return (
        f"<table width='100%' style='border-collapse:collapse;font-size:14px'>{filas}{envio}"
        f"<tr><td style='padding:8px 0;border-top:1px solid {CREMA};font-weight:bold'>Total</td>"
        f"<td align='right' style='border-top:1px solid {CREMA};font-weight:bold'>{_dinero(pedido['total'])}</td></tr></table>"
    )


def _entrega_txt(pedido: dict) -> str:
    e = pedido.get("entrega") or {}
    if e.get("tipo") == "domicilio":
        return (
            f"<p style='font-size:14px'><b>Envío a:</b> {escape(e.get('calle', ''))} {escape(e.get('numero', ''))}, "
            f"{escape(e.get('colonia', ''))}, {escape(e.get('ciudad', ''))}, CP {escape(e.get('cp', ''))}<br>"
            f"<b>Paquetería:</b> {escape(e.get('descripcion', ''))} ({escape(e.get('dias', ''))})</p>"
        )
    return "<p style='font-size:14px'><b>Entrega:</b> recoges en el local (C. Justo Sierra 2665).</p>"


def _ref(pedido_id: int) -> str:
    return f"FREC-{pedido_id:06d}"


def bienvenida(usuario: dict) -> None:
    enviar(
        usuario["email"], usuario["nombre"], "Bienvenido a Frecuente",
        f"<p>Hola {escape(usuario['nombre'])}, tu cuenta ya está lista.</p>"
        "<p>Ahora puedes pedir tu café en línea, recibirlo en casa y programar tu recompra.</p>"
        + _boton("Ver la tienda", f"{FRONT_URL}/tienda"),
        "bienvenida",
    )


def pedido_nuevo_tienda(pedido: dict, cliente: dict) -> None:
    if not CORREO_TIENDA:
        return
    enviar(
        CORREO_TIENDA, "Frecuente", f"Pedido nuevo {_ref(pedido['_id'])} · {_dinero(pedido['total'])}",
        f"<p><b>{escape(cliente['nombre'])}</b> ({escape(cliente['email'])}) hizo un pedido "
        f"con {escape(pedido['pago']['metodo'])}.</p>{_tabla_items(pedido)}{_entrega_txt(pedido)}"
        + _boton("Abrir en el panel", f"{FRONT_URL}/admin/pedidos"),
        "pedido_nuevo_tienda", pedido["_id"],
    )


def pedido_confirmado(pedido: dict, cliente: dict) -> None:
    enviar(
        cliente["email"], cliente["nombre"], f"Recibimos tu pago · {_ref(pedido['_id'])}",
        f"<p>Hola {escape(cliente['nombre'])}, tu pago fue aprobado. Ya estamos preparando tu pedido.</p>"
        f"{_tabla_items(pedido)}{_entrega_txt(pedido)}" + _boton("Ver mi pedido", f"{FRONT_URL}/pedido?id={pedido['_id']}"),
        "pedido_confirmado", pedido["_id"],
    )


def pedido_enviado(pedido: dict, cliente: dict) -> None:
    e = pedido.get("entrega") or {}
    rastreo = (
        _boton("Rastrear mi paquete", e["rastreo_url"]) if e.get("rastreo_url")
        else _boton("Ver mi pedido", f"{FRONT_URL}/pedido?id={pedido['_id']}")
    )
    enviar(
        cliente["email"], cliente["nombre"], f"Tu pedido va en camino · {_ref(pedido['_id'])}",
        f"<p>Hola {escape(cliente['nombre'])}, entregamos tu pedido a la paquetería.</p>"
        f"<p style='font-size:14px'><b>Paquetería:</b> {escape(e.get('descripcion', ''))}<br>"
        f"<b>Número de guía:</b> {escape(e.get('guia', ''))}<br><b>Tiempo estimado:</b> {escape(e.get('dias', ''))}</p>"
        + rastreo,
        "pedido_enviado", pedido["_id"],
    )


def membresia_activada(cliente: dict, plan: dict, membresia: dict) -> None:
    fin = membresia.get("fin")
    enviar(
        cliente["email"], cliente["nombre"], f"Tu membresía {plan.get('nombre', '')} está activa",
        f"<p>Hola {escape(cliente['nombre'])}, tu membresía <b>{escape(plan.get('nombre', ''))}</b> ya está activa"
        f"{' hasta el ' + fin.strftime('%d/%m/%Y') if fin else ''}.</p>"
        "<p>Cada día puedes canjear un beneficio en el local: abre <b>Mi membresía</b> y enseña tu código del día en caja.</p>"
        + _boton("Ver mi código", f"{FRONT_URL}/mi-membresia"),
        "membresia_activada",
    )


def recompra_lista(pedido: dict, cliente: dict, cada_dias: int) -> None:
    enviar(
        cliente["email"], cliente["nombre"], f"Tu recompra está lista para pagar · {_ref(pedido['_id'])}",
        f"<p>Hola {escape(cliente['nombre'])}, como cada {cada_dias} días, preparamos tu pedido de siempre. "
        "Solo falta el pago para enviarlo.</p>"
        f"{_tabla_items(pedido)}{_entrega_txt(pedido)}" + _boton("Pagar mi pedido", f"{FRONT_URL}/pedido?id={pedido['_id']}")
        + "<p style='font-size:12px'>¿No lo quieres este mes? Puedes pausar o cancelar tu recompra en Mi cuenta.</p>",
        "recompra_lista", pedido["_id"],
    )


def recompra_sin_stock(cliente: dict, mensaje: str) -> None:
    enviar(
        cliente["email"], cliente["nombre"], "No pudimos preparar tu recompra",
        f"<p>Hola {escape(cliente['nombre'])}, este mes no pudimos generar tu pedido automático: {escape(mensaje)}.</p>"
        "<p>Lo intentaremos de nuevo mañana. También puedes pedir otros productos desde la tienda.</p>"
        + _boton("Ir a la tienda", f"{FRONT_URL}/tienda"),
        "recompra_sin_stock",
    )
