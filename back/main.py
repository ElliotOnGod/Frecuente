"""
main.py — servidor FastAPI que expone un único endpoint GraphQL.

    POST /graphql                 (GraphiQL habilitado en GET /graphql)
    WS   /graphql                 Subscriptions en tiempo real (graphql-transport-ws)
    GET  /imagenes/<id>           fotos de productos subidas desde el panel
    POST /webhooks/mercadopago    avisos de pago de Mercado Pago (opcional)
    POST /mcp                     servidor MCP para agentes de IA (servidor_mcp.py)
    POST /tareas/recompras        genera los pedidos de recompra (para un cron)
    GET  /salud                   revisión de salud (Render la usa para saber si está vivo)

Levantar:  uvicorn main:app --reload --port 8000

Equipo: Jehu Uribe Bermudez (23100139),
        Jose Fernando Leon Lopez (23100146),
        Elliot Garcia Lopez (22300923)
Materia: Programacion Web II - CETI Colomos
"""

import asyncio
import hmac
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

import pagos
import relacional
import servidor_mcp
from database import db, init_db
from schema import _aplicar_resultado_pago, _aplicar_resultado_pago_membresia, procesar_recompras, schema

# Prepara MongoDB (catálogo) y PostgreSQL (usuarios, pedidos…) y carga los
# datos de ejemplo si están vacías
init_db()

# Orígenes que pueden llamar a la API desde el navegador. En producción:
#   CORS_ORIGENES=https://frecuente.netlify.app
# Sin la variable se permite cualquiera (cómodo para desarrollo).
CORS_ORIGENES = [o.strip().rstrip("/") for o in os.getenv("CORS_ORIGENES", "").split(",") if o.strip()]
CRON_SECRET = os.getenv("CRON_SECRET", "").strip()
RECOMPRAS_AUTOMATICAS = os.getenv("RECOMPRAS_AUTOMATICAS", "1") != "0"
RECOMPRAS_CADA_MINUTOS = int(os.getenv("RECOMPRAS_CADA_MINUTOS", "60"))

mcp_app = servidor_mcp.app_http()


async def _ciclo_recompras():
    """Cada hora revisa si a alguna suscripción ya le toca su pedido."""
    while True:
        try:
            await asyncio.to_thread(procesar_recompras)
        except Exception as e:  # que un error no apague el ciclo
            print(f"[frecuente] Recompras: {e}")
        await asyncio.sleep(RECOMPRAS_CADA_MINUTOS * 60)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    tarea = asyncio.create_task(_ciclo_recompras()) if RECOMPRAS_AUTOMATICAS else None
    # El servidor MCP necesita su administrador de sesiones corriendo
    async with servidor_mcp.mcp.session_manager.run():
        yield
    if tarea:
        tarea.cancel()
    relacional.pool.close()


app = FastAPI(title="Frecuente API", version="0.5", lifespan=ciclo_de_vida)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGENES or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)

def _router():
    """GraphiQL cambió de nombre entre versiones de Strawberry:
    antes graphiql=True, ahora graphql_ide="graphiql". Soporta ambas.

    El mismo router atiende las Subscriptions por WebSocket en /graphql
    (protocolos graphql-transport-ws y graphql-ws, los dos vienen activos).

    Los navegadores no aplican CORS al WebSocket, así que Strawberry (desde
    la 0.34x) revisa el encabezado Origin: se permiten los mismos orígenes
    que CORS. Nuestra sesión viaja en connection_init (no en cookies), así
    que en desarrollo, sin CORS_ORIGENES, se aceptan todos."""
    origenes = CORS_ORIGENES or ["*"]
    for opciones in (
        {"graphql_ide": "graphiql", "allowed_origins": origenes},
        {"graphql_ide": "graphiql"},
        {"graphiql": True},
    ):
        try:
            return GraphQLRouter(schema, **opciones)
        except TypeError:
            continue
    raise RuntimeError("Versión de Strawberry no soportada")


app.include_router(_router(), prefix="/graphql")


@app.get("/")
def raiz():
    return {"api": "Frecuente", "graphql": "/graphql", "mcp": "/mcp", "pagos": pagos.PAGOS_MODO}


@app.get("/salud")
def salud():
    """Revisa que las DOS bases respondan."""
    db.command("ping")
    with relacional.transaccion() as con:
        con.execute("SELECT 1")
    return {"ok": True, "mongo": "ok", "postgres": "ok"}


@app.post("/tareas/recompras")
def tarea_recompras(request: Request):
    """Para un cron externo (por ejemplo el workflow programado de GitHub
    Actions): genera los pedidos de recompra del día. Pide la clave
    CRON_SECRET en el encabezado X-Cron-Secret."""
    clave = request.headers.get("x-cron-secret", "")
    if not CRON_SECRET or not hmac.compare_digest(clave, CRON_SECRET):
        raise HTTPException(status_code=401, detail="Clave de cron inválida")
    return {"ok": True, "pedidos": procesar_recompras()}


@app.get("/imagenes/{imagen_id}")
def imagen(imagen_id: str):
    """Fotos de productos que sube el admin (las guarda subirImagen en MongoDB).

    Cada foto tiene un id al azar y nunca cambia, así que el navegador la
    puede guardar en caché un año entero. `nosniff` evita que el navegador
    trate el archivo como otra cosa que no sea la imagen que declaramos."""
    if not re.fullmatch(r"[0-9a-f]{32}", imagen_id):
        raise HTTPException(status_code=404)
    doc = db.imagenes.find_one({"_id": imagen_id})
    if doc is None:
        raise HTTPException(status_code=404)
    return Response(
        content=bytes(doc["datos"]),
        media_type=doc["tipo"],
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.post("/webhooks/mercadopago")
async def webhook_mercadopago(request: Request):
    """Mercado Pago avisa aquí cuando cambia un pago (solo si configuraste
    BACKEND_PUBLIC_URL con una URL pública, por ejemplo con ngrok).

    No se confía en el contenido del aviso: solo se toma el id del pago y
    se le pregunta a Mercado Pago con nuestra llave. Siempre se responde
    200 para que no lo reintente sin fin."""
    params = request.query_params
    try:
        cuerpo = await request.json()
    except Exception:
        cuerpo = {}

    tipo = params.get("type") or params.get("topic") or cuerpo.get("type")
    pago_id = params.get("data.id") or str((cuerpo.get("data") or {}).get("id", ""))
    if tipo != "payment" or not pago_id or pagos.modo_de("mercadopago") != "sandbox":
        return {"ok": True, "ignorado": True}

    if not pagos.mp_firma_valida(
        request.headers.get("x-signature", ""), request.headers.get("x-request-id", ""), pago_id
    ):
        return {"ok": False, "motivo": "firma inválida"}

    try:
        # Primero se averigua de qué es el pago (external_reference):
        #   "37" → pedido 37      "M5" → membresía 5
        status, data = pagos._http(
            "GET", f"{pagos.MP_API}/v1/payments/{pago_id}", headers=pagos._mp_headers()
        )
        ref = str(data.get("external_reference", ""))
        if status < 300 and ref.startswith("M"):
            membresia = db.membresias.find_one({"_id": int(ref[1:])})
            if membresia and (membresia.get("pago") or {}).get("metodo") == "mercadopago":
                plan = db.planes.find_one({"_id": membresia["plan_id"]}) or {"nombre": ""}
                cargo = pagos.cargo_membresia({**membresia, "total": membresia["precio"]}, plan["nombre"])
                _aplicar_resultado_pago_membresia(membresia, pagos.mp_consultar(cargo, pago_id))
        elif status < 300 and ref.isdigit():
            pedido = relacional.pedido(int(ref))
            if pedido and (pedido.get("pago") or {}).get("metodo") == "mercadopago":
                _aplicar_resultado_pago(pedido, pagos.mp_consultar(pedido, pago_id))
    except (pagos.ErrorPago, ValueError, TypeError):
        pass
    return {"ok": True}


# El servidor MCP va al final: atiende /mcp y nada de lo de arriba
app.mount("/", mcp_app)
