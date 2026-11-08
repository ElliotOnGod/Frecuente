"""
servidor_mcp.py — servidor MCP (Model Context Protocol) de Frecuente.

¿Qué es MCP? Un protocolo abierto para que un asistente de IA (Claude,
ChatGPT, Copilot…) use "herramientas" de un sistema. GraphQL es la API
para NUESTRO front; MCP es la API para que un AGENTE consulte la tienda:
"¿qué café sirve para prensa francesa?", "¿cómo va el pedido 37?",
"¿qué productos tienen poco stock?".

Vive en el mismo backend, en  POST /mcp  (transporte Streamable HTTP).
Para probarlo:
    npx @modelcontextprotocol/inspector     → URL http://localhost:8000/mcp
o agregarlo como conector remoto en Claude con esa URL (publicada).

Herramientas públicas (catálogo):
    buscar_productos, ver_producto, listar_categorias, metodos_de_preparacion,
    cotizar_envio
Herramientas de administración (piden el token JWT de un admin en el
encabezado  Authorization: Bearer <token>, el mismo que usa el panel):
    estado_de_pedido, resumen_de_ventas, productos_con_poco_stock,
    pedidos_por_cobrar

Reutiliza las mismas funciones que GraphQL: las reglas de negocio están en
un solo lugar.

Equipo: Jehu Uribe Bermudez (23100139),
        Jose Fernando Leon Lopez (23100146),
        Elliot Garcia Lopez (22300923)
Materia: Programacion Web II - CETI Colomos
"""

from datetime import timedelta

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

import envios
import relacional
from auth import SesionInvalida, usuario_id_de_token
from database import METODOS_PREPARACION, db
from pagos import referencia_de

mcp = MCPServer(
    name="frecuente",
    title="Frecuente Café",
    version="1.0",
    instructions=(
        "Tienda en línea de Frecuente, cafetería de especialidad en Guadalajara. "
        "Usa buscar_productos para recomendar café, leches, matcha o accesorios según el "
        "método de preparación del cliente. Precios en pesos mexicanos (MXN). Las "
        "herramientas de administración requieren el token de un administrador."
    ),
)


def _producto(p: dict) -> dict:
    return {
        "id": p["_id"],
        "nombre": p["nombre"],
        "descripcion": p.get("descripcion", ""),
        "precio_mxn": float(p["precio"]),
        "disponibles": p["stock"],
        "categoria_id": p["categoria_id"],
        "variantes": p.get("variantes") or [],
        "metodos_de_preparacion": [METODOS_PREPARACION.get(m, m) for m in p.get("metodos") or []],
        "url": f"/categoria?id={p['categoria_id']}&producto={p['_id']}",
    }


def _admin(ctx: Context) -> dict:
    """El agente manda el JWT de un admin; se verifica la FIRMA (no se le cree al encabezado)."""
    encabezado = (ctx.headers or {}).get("authorization", "")
    tipo, _, token = encabezado.partition(" ")
    if tipo.lower() != "bearer" or not token.strip():
        raise ToolError("Esta herramienta es para administradores: manda Authorization: Bearer <token>")
    try:
        usuario = relacional.usuario(usuario_id_de_token(token.strip()))
    except SesionInvalida as e:
        raise ToolError(str(e))
    if usuario is None or not usuario["activo"] or usuario["rol"] != "admin":
        raise ToolError("Solo un administrador puede usar esta herramienta")
    return usuario


# ---------------- públicas ----------------

@mcp.tool(title="Buscar productos")
def buscar_productos(texto: str = "", metodo: str = "", categoria_id: int = 0, solo_disponibles: bool = True) -> list[dict]:
    """Busca en el catálogo de Frecuente.

    texto: palabras del nombre o la descripción (ej. "etiopía", "avena").
    metodo: espresso | filtro | prensa | goteo | frio | batido (vacío = todos).
    categoria_id: 1 café, 2 leches, 3 matcha, 4 accesorios (0 = todas)."""
    import re

    filtro: dict = {}
    if texto.strip():
        patron = {"$regex": re.escape(texto.strip()[:60]), "$options": "i"}
        filtro["$or"] = [{"nombre": patron}, {"descripcion": patron}, {"variantes": patron}]
    if metodo:
        if metodo not in METODOS_PREPARACION:
            raise ToolError(f"Método desconocido. Usa uno de: {', '.join(METODOS_PREPARACION)}")
        filtro["metodos"] = metodo
    if categoria_id:
        filtro["categoria_id"] = categoria_id
    if solo_disponibles:
        filtro["stock"] = {"$gt": 0}
    return [_producto(p) for p in db.productos.find(filtro).sort("_id", 1).limit(30)]


@mcp.tool(title="Ver un producto")
def ver_producto(producto_id: int) -> dict:
    """Detalle de un producto por su id."""
    p = db.productos.find_one({"_id": producto_id})
    if p is None:
        raise ToolError(f"No existe el producto {producto_id}")
    return _producto(p)


@mcp.tool(title="Categorías")
def listar_categorias() -> list[dict]:
    """Categorías del catálogo con cuántos productos tiene cada una."""
    return [
        {"id": c["_id"], "nombre": c["nombre"], "descripcion": c.get("descripcion", ""),
         "productos": db.productos.count_documents({"categoria_id": c["_id"]})}
        for c in db.categorias.find().sort("_id", 1)
    ]


@mcp.tool(title="Métodos de preparación")
def metodos_de_preparacion() -> dict[str, str]:
    """Claves válidas para el filtro `metodo` de buscar_productos."""
    return dict(METODOS_PREPARACION)


@mcp.tool(title="Cotizar envío")
def cotizar_envio(codigo_postal: str, producto_id: int, cantidad: int = 1) -> list[dict]:
    """Cuánto cuesta enviar un producto a un código postal de México (Envia.com)."""
    p = db.productos.find_one({"_id": producto_id})
    if p is None:
        raise ToolError(f"No existe el producto {producto_id}")
    try:
        info = envios.buscar_cp(codigo_postal)
        kg = envios.peso_de([{"producto_id": producto_id, "cantidad": max(1, cantidad)}],
                            {producto_id: float(p.get("peso_kg") or envios.PESO_DEFECTO_KG)})
        opciones = envios.cotizar({"cp": info["cp"], "estado": info["estado"], "ciudad": info["ciudad"]},
                                  kg, float(p["precio"]) * max(1, cantidad))
    except envios.ErrorEnvio as e:
        raise ToolError(str(e))
    return [{k: o[k] for k in ("descripcion", "dias", "costo", "modo")} for o in opciones]


# ---------------- administración ----------------

@mcp.tool(title="Estado de un pedido (admin)")
def estado_de_pedido(ctx: Context, pedido_id: int) -> dict:
    """Estado, pago, envío y renglones de un pedido (FREC-000012 → 12)."""
    _admin(ctx)
    p = relacional.pedido(pedido_id)
    if p is None:
        raise ToolError(f"No existe el pedido {pedido_id}")
    entrega = p.get("entrega") or {}
    return {
        "referencia": referencia_de(p["_id"]),
        "cliente": relacional.nombre_de(p["usuario_id"]),
        "fecha": p["fecha"].isoformat(sep=" "),
        "estado": p["estado"],
        "total_mxn": p["total"],
        "pago": {"metodo": p["pago"]["metodo"], "estado": p["pago"]["estado"]},
        "entrega": {"tipo": entrega.get("tipo", "recoger"), "paqueteria": entrega.get("descripcion", ""),
                    "guia": entrega.get("guia", "")},
        "productos": [
            {"nombre": i["nombre"], "variante": i["variante"], "cantidad": i["cantidad"]} for i in p["items"]
        ],
    }


@mcp.tool(title="Resumen de ventas (admin)")
def resumen_de_ventas(ctx: Context, dias: int = 7) -> dict:
    """Ventas pagadas de los últimos `dias` días y los productos más vendidos."""
    from schema import _ahora

    _admin(ctx)
    dias = max(1, min(dias, 365))
    desde = _ahora().replace(hour=0, minute=0, second=0) - timedelta(days=dias - 1)
    r = relacional.resumen_ventas(desde, dias)
    return {
        "dias": dias,
        "ventas_mxn": r["ventas_total"],
        "pedidos_pagados": r["pedidos_pagados"],
        "periodo_anterior_mxn": r["ventas_periodo_anterior"],
        "por_cobrar_mxn": r["por_cobrar"],
        "pedidos_por_enviar": r["pedidos_por_enviar"],
        "recompras_activas": r["recompras_activas"],
        "mas_vendidos": [{"nombre": t["nombre"], "piezas": t["piezas"]} for t in r["top"]],
    }


@mcp.tool(title="Productos con poco stock (admin)")
def productos_con_poco_stock(ctx: Context, maximo: int = 10) -> list[dict]:
    """Productos con `maximo` piezas o menos, para resurtir."""
    _admin(ctx)
    return [
        {"id": p["_id"], "nombre": p["nombre"], "disponibles": p["stock"]}
        for p in db.productos.find({"stock": {"$lte": maximo}}).sort("stock", 1)
    ]


@mcp.tool(title="Pedidos por cobrar (admin)")
def pedidos_por_cobrar(ctx: Context) -> list[dict]:
    """Pedidos registrados que todavía no se pagan."""
    _admin(ctx)
    _, docs = relacional.pedidos_admin("por_cobrar", None, None, 50, 0)
    return [
        {"referencia": referencia_de(p["_id"]), "cliente": relacional.nombre_de(p["usuario_id"]),
         "total_mxn": p["total"], "metodo": p["pago"]["metodo"], "fecha": p["fecha"].isoformat(sep=" ")}
        for p in docs
    ]


def app_http():
    """App ASGI del transporte Streamable HTTP, montada en /mcp por main.py.
    stateless_http: cada petición es independiente (sirve con varios
    procesos y en Render). La protección contra DNS rebinding se desactiva
    porque el backend se publica con su propio dominio y CORS."""
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
