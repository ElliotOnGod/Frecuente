"""
main.py — servidor FastAPI que expone un único endpoint GraphQL.

    POST /graphql                 (GraphiQL habilitado en GET /graphql)
    WS   /graphql                 Subscriptions en tiempo real (graphql-transport-ws)
    POST /webhooks/mercadopago    avisos de pago de Mercado Pago (opcional)

Levantar:  uvicorn main:app --reload --port 8000

Equipo: Jehu Uribe Bermudez (23100139),
        Jose Fernando Leon Lopez (23100146),
        Elliot Garcia Lopez (22300923)
Materia: Programacion Web II - CETI Colomos
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

import pagos
from database import db, init_db
from schema import _aplicar_resultado_pago, _aplicar_resultado_pago_membresia, schema

# Crea las colecciones en MongoDB y carga datos_ejemplo.json si está vacía
init_db()

app = FastAPI(title="Frecuente API", version="0.4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # en el avance se deja abierto para el front en Astro
    allow_methods=["*"],
    allow_headers=["*"],
)

def _router():
    """GraphiQL cambió de nombre entre versiones de Strawberry:
    antes graphiql=True, ahora graphql_ide="graphiql". Soporta ambas.

    El mismo router atiende las Subscriptions por WebSocket en /graphql
    (protocolos graphql-transport-ws y graphql-ws, los dos vienen activos)."""
    try:
        return GraphQLRouter(schema, graphql_ide="graphiql")
    except TypeError:
        return GraphQLRouter(schema, graphiql=True)


app.include_router(_router(), prefix="/graphql")


@app.get("/")
def raiz():
    return {"api": "Frecuente", "graphql": "/graphql", "pagos": pagos.PAGOS_MODO}


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
            pedido = db.pedidos.find_one({"_id": int(ref)})
            if pedido and (pedido.get("pago") or {}).get("metodo") == "mercadopago":
                _aplicar_resultado_pago(pedido, pagos.mp_consultar(pedido, pago_id))
    except (pagos.ErrorPago, ValueError, TypeError):
        pass
    return {"ok": True}
