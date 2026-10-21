"""
schema.py — esquema GraphQL (Strawberry) del e-commerce Frecuente.

Tipos: Categoria, Producto, Usuario, Pedido, PedidoItem, Pago, MetodoPago,
       InicioPago, ResumenAdmin (+ sus series), PaginaPedidos,
       Plan, Membresia, Canje, ResumenMembresias, ClienteAdmin, EventoTiempoReal
Query: categorias, categoria, productos, producto, metodosPago, planes,
       yo, misPedidos, pedido, miMembresia, misMembresias, membresia,
       resumenAdmin, pedidosAdmin, resumenMembresias, membresiasAdmin,
       membresiaPorCodigo, canjesHoy, clientesAdmin                (admin)
Mutation: registrarUsuario, iniciarSesion,
          registrarPedido, iniciarPago, confirmarPago, cancelarMiPedido,
          crearProducto, actualizarProducto, eliminarProducto,      (admin)
          cambiarEstadoPedido, marcarReembolsado,                   (admin)
          contratarMembresia, iniciarPagoMembresia, confirmarPagoMembresia,
          cancelarMiMembresia,
          confirmarPagoMembresiaManual, cancelarMembresia, canjearMembresia,
          crearPlan, actualizarPlan                                 (admin)
Subscription (tiempo real, WebSocket): eventosAdmin (admin),
          seguirPedido, seguirMembresia (dueño o admin)

Sesión: el front manda  Authorization: Bearer <token>  (ver auth.py).
  - Catálogo (categorías, productos) y metodosPago: público.
  - yo, misPedidos, pedido, registrarPedido, iniciarPago, confirmarPago,
    cancelarMiPedido: requieren sesión (cada cliente solo toca lo suyo).
  - Todo lo marcado (admin): requiere sesión con rol "admin".

Equipo: Jehu Uribe Bermudez (23100139),
        Jose Fernando Leon Lopez (23100146),
        Elliot Garcia Lopez (22300923)
Materia: Programacion Web II - CETI Colomos
"""

import base64
import hashlib
import hmac
import re
from datetime import datetime, timedelta
from typing import AsyncGenerator, List, Optional

import strawberry
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError, WriteError
from strawberry.types import Info

import eventos
from auth import (
    JWT_SECRET,
    SesionInvalida,
    crear_token,
    hashear_password,
    token_de_request,
    usuario_id_de_token,
    verificar_password,
)
from database import DIAS_MEMBRESIA, ESTADOS_PEDIDO, a_dict, db, siguiente_id
import pagos
from pagos import METODOS, ErrorPago, modo_de, referencia_de, referencia_membresia


# =========================================================
# Tipos
# =========================================================

@strawberry.type
class PedidoItem:
    id: int
    pedido_id: int
    producto_id: int
    cantidad: int
    precio_unit: float

    @strawberry.field
    def producto(self) -> Optional["Producto"]:
        return _producto(db.productos.find_one({"_id": self.producto_id}))

    @strawberry.field
    def subtotal(self) -> float:
        return round(self.cantidad * self.precio_unit, 2)


@strawberry.type
class Producto:
    id: int
    nombre: str
    descripcion: str
    precio: float
    stock: int
    imagen_url: str
    categoria_id: int

    @strawberry.field
    def categoria(self) -> Optional["Categoria"]:
        return _categoria(db.categorias.find_one({"_id": self.categoria_id}))


@strawberry.type
class Categoria:
    id: int
    nombre: str
    descripcion: str
    imagen_url: str

    @strawberry.field
    def productos(self) -> List[Producto]:
        cursor = db.productos.find({"categoria_id": self.id}).sort("_id", ASCENDING)
        return [_producto(d) for d in cursor]


@strawberry.type
class Usuario:
    id: int
    nombre: str
    email: str
    telefono: str
    rol: str


@strawberry.type
class AuthPayload:
    """Lo que regresa registrarse o iniciar sesión."""
    token: str
    usuario: Usuario


@strawberry.type
class DatoPago:
    """Un renglón de instrucciones: 'CLABE' → '012 320 …'."""
    etiqueta: str
    valor: str


@strawberry.type
class Pago:
    metodo: str           # mercadopago | paypal | transferencia | efectivo
    metodo_nombre: str
    estado: str           # pendiente | aprobado | rechazado | por_reembolsar | reembolsado
    modo: str             # simulado | sandbox | manual
    en_linea: bool
    referencia: str       # FREC-000012
    pago_id: str          # id del cobro en Mercado Pago / PayPal
    detalle: str
    fecha_pago: Optional[str]
    pedido_total: strawberry.Private[float]

    @strawberry.field
    def instrucciones(self) -> List[DatoPago]:
        """Datos para pagar fuera de línea (CLABE, dónde recoger…)."""
        return [
            DatoPago(etiqueta=e, valor=v)
            for e, v in pagos.instrucciones(self.metodo, self.referencia, self.pedido_total)
        ]


@strawberry.type
class MetodoPago:
    clave: str
    nombre: str
    descripcion: str
    en_linea: bool
    modo: str


@strawberry.type
class Pedido:
    id: int
    usuario_id: int
    fecha: str
    estado: str
    total: float
    # Los items vienen embebidos en el documento del pedido; se guardan
    # aquí sin exponerlos tal cual y el campo `items` los convierte.
    items_doc: strawberry.Private[list]
    pago_doc: strawberry.Private[Optional[dict]]

    @strawberry.field
    def usuario(self) -> Optional[Usuario]:
        return _usuario(db.usuarios.find_one({"_id": self.usuario_id}))

    @strawberry.field
    def referencia(self) -> str:
        return referencia_de(self.id)

    @strawberry.field
    def piezas(self) -> int:
        return sum(it["cantidad"] for it in self.items_doc)

    @strawberry.field
    def pago(self) -> Optional[Pago]:
        """null en pedidos de la entrega anterior (antes de los pagos)."""
        return _pago(self.pago_doc, self.total, referencia_de(self.id))

    @strawberry.field
    def items(self) -> List[PedidoItem]:
        return [
            PedidoItem(
                id=i + 1,
                pedido_id=self.id,
                producto_id=it["producto_id"],
                cantidad=it["cantidad"],
                precio_unit=it["precio_unit"],
            )
            for i, it in enumerate(self.items_doc)
        ]


def _fecha_txt(v) -> Optional[str]:
    return v.isoformat(sep=" ", timespec="seconds") if isinstance(v, datetime) else None


def _pago(p: dict | None, total: float, referencia: str) -> Optional[Pago]:
    """Subdocumento pago → tipo Pago (lo usan pedidos y membresías)."""
    if not p:
        return None
    return Pago(
        metodo=p["metodo"],
        metodo_nombre=METODOS.get(p["metodo"], {}).get("nombre", p["metodo"]),
        estado=p["estado"],
        modo=p.get("modo", "manual"),
        en_linea=METODOS.get(p["metodo"], {}).get("en_linea", False),
        referencia=p.get("referencia") or referencia,
        pago_id=p.get("pago_id", ""),
        detalle=p.get("detalle", ""),
        fecha_pago=_fecha_txt(p.get("fecha_pago")),
        pedido_total=total,
    )


# ---- mapeadores documento -> tipo ----
# Se toman solo los campos que declara cada tipo y se rellenan los
# opcionales, porque un documento de Mongo puede no traerlos todos.

def _producto(doc: dict | None) -> Producto | None:
    d = a_dict(doc)
    if d is None:
        return None
    return Producto(
        id=d["id"],
        nombre=d["nombre"],
        descripcion=d.get("descripcion", ""),
        precio=float(d["precio"]),
        stock=d["stock"],
        imagen_url=d.get("imagen_url", ""),
        categoria_id=d["categoria_id"],
    )


def _categoria(doc: dict | None) -> Categoria | None:
    d = a_dict(doc)
    if d is None:
        return None
    return Categoria(
        id=d["id"],
        nombre=d["nombre"],
        descripcion=d.get("descripcion", ""),
        imagen_url=d.get("imagen_url", ""),
    )


def _usuario(doc: dict | None) -> Usuario | None:
    d = a_dict(doc)
    if d is None:
        return None
    return Usuario(
        id=d["id"],
        nombre=d["nombre"],
        email=d["email"],
        telefono=d.get("telefono", ""),
        rol=d.get("rol", "cliente"),
    )


def _pedido(doc: dict | None) -> Pedido | None:
    d = a_dict(doc)
    if d is None:
        return None
    return Pedido(
        id=d["id"],
        usuario_id=d["usuario_id"],
        fecha=d["fecha"],
        estado=d["estado"],
        total=float(d["total"]),
        items_doc=d.get("items", []),
        pago_doc=d.get("pago"),
    )


@strawberry.type
class InicioPago:
    """Respuesta de iniciarPago: a dónde mandar al cliente.
    url = null en transferencia/efectivo (se muestran las instrucciones)."""
    pedido: Pedido
    url: Optional[str]


# ---- tipos del panel de administración ----

@strawberry.type
class PuntoVenta:
    fecha: str        # "2026-10-08"
    total: float
    pedidos: int


@strawberry.type
class VentaMetodo:
    metodo: str
    nombre: str
    total: float
    pedidos: int


@strawberry.type
class ConteoEstado:
    estado: str
    pedidos: int


@strawberry.type
class ProductoVendido:
    producto_id: int
    nombre: str
    piezas: int
    total: float


@strawberry.type
class ResumenAdmin:
    dias: int
    ventas_total: float
    ventas_periodo_anterior: float
    pedidos_pagados: int
    ticket_promedio: float
    por_cobrar: float
    pedidos_por_cobrar: int
    pedidos_por_enviar: int
    pedidos_por_reembolsar: int
    clientes_total: int
    clientes_con_compra: int
    ventas_por_dia: List[PuntoVenta]
    por_metodo: List[VentaMetodo]
    por_estado: List[ConteoEstado]
    top_productos: List[ProductoVendido]
    stock_bajo: List[Producto]


@strawberry.type
class PaginaPedidos:
    total: int
    pedidos: List[Pedido]


# ---- membresías ----

@strawberry.type
class Plan:
    id: int
    nombre: str
    descripcion: str
    precio: float
    incluye: List[str]
    opciones: List[str]   # lo que el barista puede elegir al canjear
    activo: bool
    orden: int

    @strawberry.field
    def miembros_activos(self) -> int:
        ahora = datetime.now()
        return db.membresias.count_documents(
            {"plan_id": self.id, "estado": "activa", "inicio": {"$lte": ahora}, "fin": {"$gte": ahora}}
        )


@strawberry.type
class Canje:
    dia: str              # "2026-10-15"
    fecha: str            # "2026-10-15 08:31:00"
    opcion: str
    nota: str


@strawberry.type
class Membresia:
    id: int
    usuario_id: int
    plan_id: int
    estado: str           # pendiente | activa | programada | vencida | cancelada
    precio: float
    creada: str
    inicio: Optional[str]
    fin: Optional[str]
    canjes_doc: strawberry.Private[list]
    pago_doc: strawberry.Private[Optional[dict]]
    fin_dt: strawberry.Private[Optional[datetime]]

    @strawberry.field
    def referencia(self) -> str:
        return referencia_membresia(self.id)

    @strawberry.field
    def plan(self) -> Optional[Plan]:
        return _plan(db.planes.find_one({"_id": self.plan_id}))

    @strawberry.field
    def usuario(self) -> Optional[Usuario]:
        return _usuario(db.usuarios.find_one({"_id": self.usuario_id}))

    @strawberry.field
    def pago(self) -> Optional[Pago]:
        return _pago(self.pago_doc, self.precio, referencia_membresia(self.id))

    @strawberry.field
    def dias_restantes(self) -> int:
        if self.estado not in ("activa", "programada") or self.fin_dt is None:
            return 0
        return max(0, (self.fin_dt.date() - datetime.now().date()).days)

    @strawberry.field
    def canjes(self, limite: int = 31) -> List[Canje]:
        """Canjes más recientes primero."""
        orden = sorted(self.canjes_doc, key=lambda c: c["fecha"], reverse=True)
        return [_canje(c) for c in orden[: max(0, limite)]]

    @strawberry.field
    def canjes_total(self) -> int:
        return len(self.canjes_doc)

    @strawberry.field
    def canje_hoy(self) -> Optional[Canje]:
        hoy = _hoy_txt()
        c = next((c for c in self.canjes_doc if c["dia"] == hoy), None)
        return _canje(c) if c else None

    @strawberry.field
    def codigo_hoy(self, info: Info) -> Optional[str]:
        """Código que el cliente enseña en el local. Solo lo ve el dueño,
        y solo si la membresía está activa."""
        usuario = usuario_actual(info, requerido=False)
        if usuario is None or usuario["_id"] != self.usuario_id or self.estado != "activa":
            return None
        return codigo_canje(self.id, _hoy_txt())


@strawberry.type
class InicioPagoMembresia:
    membresia: Membresia
    url: Optional[str]


@strawberry.type
class PlanActivo:
    plan_id: int
    nombre: str
    activas: int
    ingreso_mensual: float


@strawberry.type
class ResumenMembresias:
    activas: int
    pendientes: int
    vencen_7_dias: int
    ingreso_mensual: float     # suma del precio de las membresías activas
    canjes_hoy: int
    canjes_7_dias: int
    por_plan: List[PlanActivo]


@strawberry.type
class CanjeAdmin:
    membresia_id: int
    cliente: str
    plan: str
    opcion: str
    nota: str
    fecha: str


@strawberry.type
class PaginaMembresias:
    total: int
    membresias: List[Membresia]


@strawberry.type
class ClienteAdmin:
    id: int
    nombre: str
    email: str
    telefono: str
    creado: Optional[str]
    pedidos: int
    total_gastado: float
    ultima_compra: Optional[str]
    membresia_id: strawberry.Private[Optional[int]]

    @strawberry.field
    def membresia(self) -> Optional[Membresia]:
        if self.membresia_id is None:
            return None
        return _membresia(db.membresias.find_one({"_id": self.membresia_id}))


@strawberry.type
class PaginaClientes:
    total: int
    clientes: List[ClienteAdmin]


@strawberry.type
class EventoTiempoReal:
    """Aviso que llega por la Subscription eventosAdmin."""
    id: int
    tipo: str             # pedido_nuevo | pago_actualizado | pedido_estado | stock_bajo |
                          # membresia_nueva | membresia_actualizada | canje | conectado
    mensaje: str
    fecha: str
    pedido_id: Optional[int]
    membresia_id: Optional[int]
    monto: Optional[float]


def _evento(e: dict) -> EventoTiempoReal:
    return EventoTiempoReal(
        id=e["id"],
        tipo=e["tipo"],
        mensaje=e["mensaje"],
        fecha=_fecha_txt(e["fecha"]) or "",
        pedido_id=e.get("pedido_id"),
        membresia_id=e.get("membresia_id"),
        monto=e.get("monto"),
    )


def _plan(doc: dict | None) -> Optional[Plan]:
    if doc is None:
        return None
    return Plan(
        id=doc["_id"],
        nombre=doc["nombre"],
        descripcion=doc.get("descripcion", ""),
        precio=float(doc["precio"]),
        incluye=list(doc.get("incluye", [])),
        opciones=list(doc.get("opciones", [])),
        activo=bool(doc.get("activo", True)),
        orden=int(doc.get("orden", doc["_id"])),
    )


def _canje(c: dict) -> Canje:
    return Canje(dia=c["dia"], fecha=_fecha_txt(c["fecha"]) or "", opcion=c["opcion"], nota=c.get("nota", ""))


def _estado_membresia(doc: dict) -> str:
    """'vencida' y 'programada' no se guardan, se calculan:
    vencida    = activa cuya fecha fin ya pasó
    programada = activa (renovación ya pagada) que todavía no empieza"""
    ahora = datetime.now()
    if doc["estado"] == "activa" and doc.get("fin") and doc["fin"] < ahora:
        return "vencida"
    if doc["estado"] == "activa" and doc.get("inicio") and doc["inicio"] > ahora:
        return "programada"
    return doc["estado"]


def _membresia(doc: dict | None) -> Optional[Membresia]:
    if doc is None:
        return None
    return Membresia(
        id=doc["_id"],
        usuario_id=doc["usuario_id"],
        plan_id=doc["plan_id"],
        estado=_estado_membresia(doc),
        precio=float(doc["precio"]),
        creada=_fecha_txt(doc["creada"]) or "",
        inicio=_fecha_txt(doc.get("inicio")),
        fin=_fecha_txt(doc.get("fin")),
        canjes_doc=doc.get("canjes", []),
        pago_doc=doc.get("pago"),
        fin_dt=doc.get("fin"),
    )


# =========================================================
# Inputs
# =========================================================

@strawberry.input
class ProductoInput:
    nombre: str
    descripcion: str = ""
    precio: float = 0.0
    stock: int = 0
    imagen_url: str = ""
    categoria_id: int = 1


@strawberry.input
class ProductoUpdateInput:
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    precio: Optional[float] = None
    stock: Optional[int] = None
    imagen_url: Optional[str] = None
    categoria_id: Optional[int] = None


@strawberry.input
class ItemInput:
    producto_id: int
    cantidad: int


@strawberry.input
class PedidoInput:
    # Ya no se manda usuario_id: el pedido es del usuario de la sesión
    items: List[ItemInput]
    metodo_pago: str = "mercadopago"


@strawberry.input
class ConfirmarPagoInput:
    """Lo que trae la URL al regresar de la pasarela.
    - Mercado Pago agrega ?payment_id=…
    - PayPal agrega ?token=<id de la orden>
    - La pasarela simulada manda simulacion = aprobado | rechazado | pendiente"""
    pedido_id: int
    payment_id: Optional[str] = None
    paypal_token: Optional[str] = None
    simulacion: Optional[str] = None


@strawberry.input
class ConfirmarPagoMembresiaInput:
    """Igual que ConfirmarPagoInput, pero para una membresía."""
    membresia_id: int
    payment_id: Optional[str] = None
    paypal_token: Optional[str] = None
    simulacion: Optional[str] = None


@strawberry.input
class PlanInput:
    nombre: str
    precio: float
    descripcion: str = ""
    incluye: List[str] = strawberry.field(default_factory=list)
    opciones: List[str] = strawberry.field(default_factory=list)
    activo: bool = True


@strawberry.input
class PlanUpdateInput:
    nombre: Optional[str] = None
    precio: Optional[float] = None
    descripcion: Optional[str] = None
    incluye: Optional[List[str]] = None
    opciones: Optional[List[str]] = None
    activo: Optional[bool] = None


@strawberry.input
class RegistroInput:
    nombre: str
    email: str
    password: str
    telefono: str = ""


# =========================================================
# Sesión
# =========================================================

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN = 8


def _token_de_info(info: Info) -> str | None:
    """Token de la petición. En HTTP viene en el encabezado Authorization.
    En WebSocket (Subscriptions) el navegador no puede poner encabezados,
    así que el front lo manda en el mensaje connection_init:
        { "type": "connection_init", "payload": { "Authorization": "Bearer <token>" } }
    y Strawberry lo deja en context["connection_params"]."""
    token = token_de_request(info.context.get("request"))
    if token:
        return token
    params = info.context.get("connection_params") or {}
    if isinstance(params, dict):
        valor = str(params.get("Authorization") or params.get("authorization") or "")
        tipo, _, resto = valor.partition(" ")
        if tipo.lower() == "bearer" and resto.strip():
            return resto.strip()
    return None


def usuario_actual(info: Info, requerido: bool = True) -> dict | None:
    """Usuario dueño del token de la petición. Si `requerido` y no hay
    sesión válida, lanza un error que el front muestra tal cual."""
    token = _token_de_info(info)
    if token is None:
        if requerido:
            raise ValueError("Necesitas iniciar sesión")
        return None

    usuario = db.usuarios.find_one({"_id": usuario_id_de_token(token)})
    if usuario is None:
        raise SesionInvalida("Tu sesión expiró, inicia sesión de nuevo")
    return usuario


def requiere_admin(info: Info) -> dict:
    usuario = usuario_actual(info)
    if usuario.get("rol") != "admin":
        raise ValueError("Solo un administrador puede hacer esto")
    return usuario


# =========================================================
# Pagos y ciclo de vida del pedido
# =========================================================

# A qué estados puede pasar un pedido desde cada estado (lo usa el admin)
TRANSICIONES = {
    "registrado": {"pagado", "entregado", "cancelado"},
    "pagado": {"enviado", "entregado", "cancelado"},
    "enviado": {"entregado"},
    "entregado": set(),
    "cancelado": set(),
}

# Estados de pago que ya no deben "regresar" a pendiente o rechazado
PAGO_CERRADO = ["aprobado", "por_reembolsar", "reembolsado"]


def _ahora() -> datetime:
    return datetime.now().replace(microsecond=0)


def _pedido_propio(usuario: dict, pedido_id: int) -> dict:
    """El pedido si es del usuario (o si es admin); si no, error."""
    filtro = {"_id": pedido_id}
    if usuario.get("rol") != "admin":
        filtro["usuario_id"] = usuario["_id"]
    pedido = db.pedidos.find_one(filtro)
    if pedido is None:
        raise ValueError(f"No encontramos el pedido {pedido_id}")
    return pedido


def _aplicar_resultado_pago(pedido: dict, resultado: dict) -> dict:
    """Guarda lo que dijo la pasarela y, si se aprobó, pasa el pedido a 'pagado'.

    Es idempotente: si el mismo aviso llega dos veces (regreso del cliente
    + webhook) el segundo no cambia nada. Un pago ya aprobado nunca vuelve
    a 'pendiente' o 'rechazado'."""
    estado_pago = resultado["estado"]
    cambios = {
        "pago.estado": estado_pago,
        "pago.detalle": resultado.get("detalle", "")[:200],
        "pago.actualizado": _ahora(),
    }
    if resultado.get("pago_id"):
        cambios["pago.pago_id"] = str(resultado["pago_id"])

    filtro = {"_id": pedido["_id"]}
    if estado_pago in ("pendiente", "rechazado"):
        filtro["pago.estado"] = {"$nin": PAGO_CERRADO}
    elif estado_pago == "aprobado":
        filtro["pago.estado"] = {"$nin": PAGO_CERRADO}
        cambios["pago.fecha_pago"] = _ahora()
        if pedido["estado"] == "cancelado":
            # Pagaron un pedido que ya se había cancelado: hay que regresar el dinero
            cambios["pago.estado"] = "por_reembolsar"
        elif pedido["estado"] == "registrado":
            cambios["estado"] = "pagado"

    resultado_db = db.pedidos.update_one(filtro, {"$set": cambios})
    if resultado_db.modified_count:
        textos = {
            "aprobado": "aprobado",
            "rechazado": "rechazado",
            "pendiente": "pendiente",
            "reembolsado": "reembolsado",
        }
        eventos.publicar(
            eventos.PAGO_ACTUALIZADO,
            f"Pago del pedido #{pedido['_id']} {textos.get(cambios['pago.estado'], cambios['pago.estado'])}"
            f" ({_dinero(pedido['total'])})",
            pedido_id=pedido["_id"],
            usuario_id=pedido["usuario_id"],
            monto=float(pedido["total"]),
        )
    return db.pedidos.find_one({"_id": pedido["_id"]})


def _dinero(n: float) -> str:
    return f"${float(n):,.2f}"


def _avisar_stock_bajo(producto_ids) -> None:
    """Publica un aviso por cada producto que quedó con poco stock."""
    for prod in db.productos.find({"_id": {"$in": list(producto_ids)}, "stock": {"$lte": STOCK_BAJO}}):
        eventos.publicar(
            eventos.STOCK_BAJO,
            f"{prod['nombre']}: quedan {prod['stock']} piezas",
        )


def _cancelar(pedido: dict) -> dict:
    """Cancela y regresa el stock. La condición en el filtro hace que, si
    dos personas cancelan al mismo tiempo, el stock se regrese una sola vez."""
    cambios = {"estado": "cancelado"}
    if pedido.get("pago"):  # los pedidos de la entrega anterior no traen pago
        cambios["pago.actualizado"] = _ahora()
        if pedido["pago"].get("estado") == "aprobado":
            cambios["pago.estado"] = "por_reembolsar"

    doc = db.pedidos.find_one_and_update(
        {"_id": pedido["_id"], "estado": {"$in": ["registrado", "pagado"]}},
        {"$set": cambios},
        return_document=ReturnDocument.AFTER,
    )
    if doc is None:
        raise ValueError("Este pedido ya no se puede cancelar")
    for it in doc["items"]:
        db.productos.update_one({"_id": it["producto_id"]}, {"$inc": {"stock": it["cantidad"]}})
    eventos.publicar(
        eventos.PEDIDO_ESTADO,
        f"Pedido #{doc['_id']} cancelado; el stock regresó al inventario",
        pedido_id=doc["_id"],
        usuario_id=doc["usuario_id"],
    )
    return doc


def _lineas_con_nombre(pedido: dict) -> list[dict]:
    nombres = {
        p["_id"]: p["nombre"]
        for p in db.productos.find({"_id": {"$in": [i["producto_id"] for i in pedido["items"]]}})
    }
    return [{**i, "nombre": nombres.get(i["producto_id"], "Producto")} for i in pedido["items"]]


# =========================================================
# Membresías
# =========================================================

CODIGO_RE = re.compile(r"^FM(\d+)-([A-Z2-7]{6})$")


def _hoy_txt() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def codigo_canje(membresia_id: int, dia: str) -> str:
    """Código del día para canjear en el local: FM12-K7QX2P.

    Es un HMAC (firma) del id de la membresía + la fecha con la clave
    secreta del servidor: cambia cada día, no se puede adivinar ni
    reutilizar el de ayer, y no hace falta guardarlo en la base."""
    firma = hmac.new(JWT_SECRET.encode(), f"{membresia_id}:{dia}".encode(), hashlib.sha256).digest()
    return f"FM{membresia_id}-{base64.b32encode(firma).decode()[:6]}"


def _membresia_por_codigo(codigo: str) -> dict:
    texto = re.sub(r"\s+", "", (codigo or "").upper())
    m = CODIGO_RE.match(texto)
    if not m:
        raise ValueError("Ese código no tiene el formato correcto (ej. FM12-K7QX2P)")
    membresia_id = int(m.group(1))
    if not hmac.compare_digest(texto, codigo_canje(membresia_id, _hoy_txt())):
        raise ValueError("Código inválido o de otro día. Pide al cliente que actualice su código")
    doc = db.membresias.find_one({"_id": membresia_id})
    if doc is None:
        raise ValueError("No existe esa membresía")
    return doc


def _membresia_propia(usuario: dict, membresia_id: int) -> dict:
    filtro = {"_id": membresia_id}
    if usuario.get("rol") != "admin":
        filtro["usuario_id"] = usuario["_id"]
    doc = db.membresias.find_one(filtro)
    if doc is None:
        raise ValueError(f"No encontramos la membresía {membresia_id}")
    return doc


def _membresia_vigente(usuario_id: int) -> dict | None:
    """La membresía que está corriendo HOY (ya empezó y no ha vencido)."""
    ahora = _ahora()
    return db.membresias.find_one(
        {"usuario_id": usuario_id, "estado": "activa", "inicio": {"$lte": ahora}, "fin": {"$gte": ahora}},
        sort=[("fin", DESCENDING)],
    )


def _ultima_activa(usuario_id: int) -> dict | None:
    """La activa que termina más tarde (puede ser una renovación programada)."""
    return db.membresias.find_one(
        {"usuario_id": usuario_id, "estado": "activa", "fin": {"$gte": _ahora()}},
        sort=[("fin", DESCENDING)],
    )


def _activar_membresia(doc: dict, cambios_pago: dict, detalle: str) -> dict | None:
    """Pasa una membresía de 'pendiente' a 'activa' por 30 días.
    Si el cliente ya tenía una vigente, la nueva empieza cuando termina
    la anterior (renovación sin perder días)."""
    ahora = _ahora()
    ultima = _ultima_activa(doc["usuario_id"])
    inicio = max(ahora, ultima["fin"]) if ultima and ultima["_id"] != doc["_id"] else ahora
    fin = inicio + timedelta(days=DIAS_MEMBRESIA)
    nuevo = db.membresias.find_one_and_update(
        {"_id": doc["_id"], "estado": "pendiente"},  # solo una vez, aunque llegue doble aviso
        {
            "$set": {
                **cambios_pago,
                "estado": "activa",
                "inicio": inicio,
                "fin": fin,
                "pago.estado": "aprobado",
                "pago.fecha_pago": ahora,
                "pago.detalle": detalle[:200],
                "pago.actualizado": ahora,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if nuevo:
        plan = db.planes.find_one({"_id": nuevo["plan_id"]}) or {}
        usuario = db.usuarios.find_one({"_id": nuevo["usuario_id"]}) or {}
        eventos.publicar(
            eventos.MEMBRESIA_ACTUALIZADA,
            f"Membresía {plan.get('nombre', '')} activada para {usuario.get('nombre', 'un cliente')}"
            f" ({_dinero(nuevo['precio'])})",
            membresia_id=nuevo["_id"],
            usuario_id=nuevo["usuario_id"],
            monto=float(nuevo["precio"]),
        )
    return nuevo


def _aplicar_resultado_pago_membresia(doc: dict, resultado: dict) -> dict:
    """Lo mismo que _aplicar_resultado_pago, pero para membresías."""
    estado_pago = resultado["estado"]
    extra = {"pago.pago_id": str(resultado["pago_id"])} if resultado.get("pago_id") else {}

    if estado_pago == "aprobado":
        if doc["estado"] == "pendiente":
            _activar_membresia(doc, extra, resultado.get("detalle", "Pago aprobado"))
        elif doc["estado"] == "cancelada" and (doc.get("pago") or {}).get("estado") not in PAGO_CERRADO:
            db.membresias.update_one(
                {"_id": doc["_id"]},
                {"$set": {**extra, "pago.estado": "por_reembolsar", "pago.actualizado": _ahora()}},
            )
    else:
        r = db.membresias.update_one(
            {"_id": doc["_id"], "pago.estado": {"$nin": PAGO_CERRADO}},
            {
                "$set": {
                    **extra,
                    "pago.estado": estado_pago,
                    "pago.detalle": resultado.get("detalle", "")[:200],
                    "pago.actualizado": _ahora(),
                }
            },
        )
        if r.modified_count:
            eventos.publicar(
                eventos.MEMBRESIA_ACTUALIZADA,
                f"Pago de la membresía {referencia_membresia(doc['_id'])} {estado_pago}",
                membresia_id=doc["_id"],
                usuario_id=doc["usuario_id"],
            )
    return db.membresias.find_one({"_id": doc["_id"]})


def _filtro_membresias(estado, plan_id, buscar) -> dict:
    filtro: dict = {}
    ahora = _ahora()
    if estado == "activa":
        filtro.update({"estado": "activa", "inicio": {"$lte": ahora}, "fin": {"$gte": ahora}})
    elif estado == "programada":
        filtro.update({"estado": "activa", "inicio": {"$gt": ahora}})
    elif estado == "vencida":
        filtro.update({"estado": "activa", "fin": {"$lt": ahora}})
    elif estado in ("pendiente", "cancelada"):
        filtro["estado"] = estado
    if plan_id:
        filtro["plan_id"] = plan_id
    if buscar and buscar.strip():
        texto = buscar.strip()
        numero = re.sub(r"(?i)^(memb-|fm)?#?0*", "", texto).split("-")[0]
        if numero.isdigit():
            filtro["_id"] = int(numero)
        else:
            patron = {"$regex": re.escape(texto), "$options": "i"}
            ids = [u["_id"] for u in db.usuarios.find({"$or": [{"nombre": patron}, {"email": patron}]}, {"_id": 1})]
            filtro["usuario_id"] = {"$in": ids}
    return filtro


def _resumen_membresias() -> ResumenMembresias:
    ahora = _ahora()
    hoy = _hoy_txt()
    hace_7 = (ahora - timedelta(days=6)).strftime("%Y-%m-%d")
    activas = list(db.membresias.find({"estado": "activa", "inicio": {"$lte": ahora}, "fin": {"$gte": ahora}}))
    planes = {p["_id"]: p for p in db.planes.find()}

    # Agregación: canjes de los últimos 7 días (desenrolla el arreglo de canjes)
    canjes_7 = {
        r["_id"]: r["n"]
        for r in db.membresias.aggregate(
            [
                {"$unwind": "$canjes"},
                {"$match": {"canjes.dia": {"$gte": hace_7}}},
                {"$group": {"_id": "$canjes.dia", "n": {"$sum": 1}}},
            ]
        )
    }

    por_plan: dict[int, list] = {pid: [0, 0.0] for pid in planes}
    for m in activas:
        por_plan.setdefault(m["plan_id"], [0, 0.0])
        por_plan[m["plan_id"]][0] += 1
        por_plan[m["plan_id"]][1] += float(m["precio"])

    return ResumenMembresias(
        activas=len(activas),
        pendientes=db.membresias.count_documents({"estado": "pendiente"}),
        vencen_7_dias=sum(1 for m in activas if m["fin"] <= ahora + timedelta(days=7)),
        ingreso_mensual=round(sum(float(m["precio"]) for m in activas), 2),
        canjes_hoy=canjes_7.get(hoy, 0),
        canjes_7_dias=sum(canjes_7.values()),
        por_plan=[
            PlanActivo(
                plan_id=pid,
                nombre=planes.get(pid, {}).get("nombre", f"Plan {pid}"),
                activas=v[0],
                ingreso_mensual=round(v[1], 2),
            )
            for pid, v in sorted(por_plan.items(), key=lambda kv: planes.get(kv[0], {}).get("orden", kv[0]))
        ],
    )


def _canjes_del_dia(dia: str) -> List[CanjeAdmin]:
    planes = {p["_id"]: p["nombre"] for p in db.planes.find()}
    filas = []
    for m in db.membresias.find({"canjes.dia": dia}):
        usuario = db.usuarios.find_one({"_id": m["usuario_id"]}) or {}
        for c in m["canjes"]:
            if c["dia"] == dia:
                filas.append(
                    CanjeAdmin(
                        membresia_id=m["_id"],
                        cliente=usuario.get("nombre", "Cliente"),
                        plan=planes.get(m["plan_id"], ""),
                        opcion=c["opcion"],
                        nota=c.get("nota", ""),
                        fecha=_fecha_txt(c["fecha"]) or "",
                    )
                )
    return sorted(filas, key=lambda f: f.fecha, reverse=True)


def _clientes_admin(buscar, limite, salto) -> PaginaClientes:
    filtro: dict = {"rol": "cliente"}
    if buscar and buscar.strip():
        patron = {"$regex": re.escape(buscar.strip()), "$options": "i"}
        filtro["$or"] = [{"nombre": patron}, {"email": patron}, {"telefono": patron}]
    usuarios = list(db.usuarios.find(filtro))
    ids = [u["_id"] for u in usuarios]

    # Agregación: pedidos y gasto por cliente (solo ventas pagadas)
    stats = {
        r["_id"]: r
        for r in db.pedidos.aggregate(
            [
                {"$match": {"usuario_id": {"$in": ids}}},
                {
                    "$group": {
                        "_id": "$usuario_id",
                        "pedidos": {"$sum": 1},
                        "ultima": {"$max": "$fecha"},
                    }
                },
            ]
        )
    }
    gastado: dict[int, float] = {}
    for p in db.pedidos.find(
        {"usuario_id": {"$in": ids}, "pago.estado": "aprobado", "estado": {"$ne": "cancelado"}},
        {"usuario_id": 1, "total": 1},
    ):
        gastado[p["usuario_id"]] = gastado.get(p["usuario_id"], 0.0) + float(p["total"])

    filas = []
    for u in usuarios:
        vigente = _membresia_vigente(u["_id"])
        st = stats.get(u["_id"], {})
        filas.append(
            ClienteAdmin(
                id=u["_id"],
                nombre=u["nombre"],
                email=u["email"],
                telefono=u.get("telefono", ""),
                creado=_fecha_txt(u.get("creado")),
                pedidos=st.get("pedidos", 0),
                total_gastado=round(gastado.get(u["_id"], 0.0), 2),
                ultima_compra=_fecha_txt(st.get("ultima")),
                membresia_id=vigente["_id"] if vigente else None,
            )
        )
    filas.sort(key=lambda c: (-c.total_gastado, c.nombre))
    limite = max(1, min(limite, 100))
    return PaginaClientes(total=len(filas), clientes=filas[max(0, salto): max(0, salto) + limite])


# =========================================================
# Panel de administración: resumen
# =========================================================

STOCK_BAJO = 10


def _es_venta(p: dict) -> bool:
    """Cuenta como venta: pago aprobado y pedido no cancelado."""
    return (p.get("pago") or {}).get("estado") == "aprobado" and p["estado"] != "cancelado"


def _resumen_admin(dias: int) -> ResumenAdmin:
    dias = max(1, min(dias, 365))
    hoy = _ahora().replace(hour=0, minute=0, second=0)
    desde = hoy - timedelta(days=dias - 1)
    desde_anterior = desde - timedelta(days=dias)

    # Pocos pedidos (es una cafetería): se traen los dos periodos y se
    # suman aquí. Las agrupaciones más pesadas van con aggregate() abajo.
    pedidos = list(db.pedidos.find({"fecha": {"$gte": desde_anterior}}))
    actuales = [p for p in pedidos if p["fecha"] >= desde]
    anteriores = [p for p in pedidos if p["fecha"] < desde]

    ventas = [p for p in actuales if _es_venta(p)]
    ventas_total = round(sum(p["total"] for p in ventas), 2)

    # Serie diaria con todos los días, aunque no haya ventas (para la gráfica)
    por_dia = {(desde + timedelta(days=i)).strftime("%Y-%m-%d"): [0.0, 0] for i in range(dias)}
    for p in ventas:
        clave = p["fecha"].strftime("%Y-%m-%d")
        if clave in por_dia:
            por_dia[clave][0] += p["total"]
            por_dia[clave][1] += 1

    por_metodo = {m: [0.0, 0] for m in METODOS}
    for p in ventas:
        m = p["pago"]["metodo"]
        por_metodo[m][0] += p["total"]
        por_metodo[m][1] += 1

    # Pendientes: se ven sin importar la fecha (algo que cobrar es algo que cobrar)
    por_cobrar = list(db.pedidos.find({"estado": "registrado"}, {"total": 1}))

    # Agregación en MongoDB: pedidos por estado en el periodo
    por_estado = {
        r["_id"]: r["n"]
        for r in db.pedidos.aggregate(
            [
                {"$match": {"fecha": {"$gte": desde}}},
                {"$group": {"_id": "$estado", "n": {"$sum": 1}}},
            ]
        )
    }

    # Agregación en MongoDB: productos más vendidos (desenrolla los items)
    top = list(
        db.pedidos.aggregate(
            [
                {
                    "$match": {
                        "fecha": {"$gte": desde},
                        "estado": {"$ne": "cancelado"},
                        "pago.estado": "aprobado",
                    }
                },
                {"$unwind": "$items"},
                {
                    "$group": {
                        "_id": "$items.producto_id",
                        "piezas": {"$sum": "$items.cantidad"},
                        "total": {
                            "$sum": {"$multiply": ["$items.cantidad", "$items.precio_unit"]}
                        },
                    }
                },
                {"$sort": {"piezas": -1, "total": -1}},
                {"$limit": 5},
            ]
        )
    )
    nombres = {
        p["_id"]: p["nombre"] for p in db.productos.find({"_id": {"$in": [t["_id"] for t in top]}})
    }

    clientes_total = db.usuarios.count_documents({"rol": "cliente"})

    return ResumenAdmin(
        dias=dias,
        ventas_total=ventas_total,
        ventas_periodo_anterior=round(sum(p["total"] for p in anteriores if _es_venta(p)), 2),
        pedidos_pagados=len(ventas),
        ticket_promedio=round(ventas_total / len(ventas), 2) if ventas else 0.0,
        por_cobrar=round(sum(p["total"] for p in por_cobrar), 2),
        pedidos_por_cobrar=len(por_cobrar),
        pedidos_por_enviar=db.pedidos.count_documents({"estado": "pagado"}),
        pedidos_por_reembolsar=db.pedidos.count_documents({"pago.estado": "por_reembolsar"}),
        clientes_total=clientes_total,
        clientes_con_compra=len({p["usuario_id"] for p in ventas}),
        ventas_por_dia=[
            PuntoVenta(fecha=f, total=round(v[0], 2), pedidos=v[1]) for f, v in por_dia.items()
        ],
        por_metodo=[
            VentaMetodo(metodo=m, nombre=METODOS[m]["nombre"], total=round(v[0], 2), pedidos=v[1])
            for m, v in sorted(por_metodo.items(), key=lambda kv: -kv[1][0])
        ],
        por_estado=[ConteoEstado(estado=e, pedidos=por_estado.get(e, 0)) for e in ESTADOS_PEDIDO],
        top_productos=[
            ProductoVendido(
                producto_id=t["_id"],
                nombre=nombres.get(t["_id"], f"Producto {t['_id']}"),
                piezas=t["piezas"],
                total=round(t["total"], 2),
            )
            for t in top
        ],
        stock_bajo=[
            _producto(d)
            for d in db.productos.find({"stock": {"$lte": STOCK_BAJO}}).sort("stock", ASCENDING)
        ],
    )


def _filtro_pedidos_admin(estado, metodo, buscar) -> dict:
    filtro: dict = {}
    if estado:
        if estado == "por_cobrar":
            filtro["estado"] = "registrado"
        elif estado == "por_reembolsar":
            filtro["pago.estado"] = "por_reembolsar"
        else:
            filtro["estado"] = estado
    if metodo:
        filtro["pago.metodo"] = metodo
    if buscar and buscar.strip():
        texto = buscar.strip()
        numero = re.sub(r"(?i)^(frec-)?#?0*", "", texto)
        if numero.isdigit():
            filtro["_id"] = int(numero)
        else:
            patron = {"$regex": re.escape(texto), "$options": "i"}
            ids = [
                u["_id"]
                for u in db.usuarios.find({"$or": [{"nombre": patron}, {"email": patron}]}, {"_id": 1})
            ]
            filtro["usuario_id"] = {"$in": ids}
    return filtro


# =========================================================
# Query
# =========================================================

@strawberry.type
class Query:
    @strawberry.field
    def categorias(self) -> List[Categoria]:
        return [_categoria(d) for d in db.categorias.find().sort("_id", ASCENDING)]

    @strawberry.field
    def categoria(self, id: int) -> Optional[Categoria]:
        return _categoria(db.categorias.find_one({"_id": id}))

    @strawberry.field
    def productos(self, categoria_id: Optional[int] = None) -> List[Producto]:
        filtro = {} if categoria_id is None else {"categoria_id": categoria_id}
        return [_producto(d) for d in db.productos.find(filtro).sort("_id", ASCENDING)]

    @strawberry.field
    def producto(self, id: int) -> Optional[Producto]:
        return _producto(db.productos.find_one({"_id": id}))

    @strawberry.field
    def yo(self, info: Info) -> Optional[Usuario]:
        """Usuario de la sesión actual (null si no hay sesión)."""
        return _usuario(usuario_actual(info, requerido=False))

    @strawberry.field
    def mis_pedidos(self, info: Info) -> List[Pedido]:
        usuario = usuario_actual(info)
        cursor = db.pedidos.find({"usuario_id": usuario["_id"]}).sort("_id", DESCENDING)
        return [_pedido(d) for d in cursor]

    @strawberry.field
    def pedido(self, info: Info, id: int) -> Optional[Pedido]:
        """Un cliente solo ve sus pedidos; un admin ve cualquiera."""
        usuario = usuario_actual(info)
        filtro = {"_id": id}
        if usuario.get("rol") != "admin":
            filtro["usuario_id"] = usuario["_id"]
        return _pedido(db.pedidos.find_one(filtro))

    @strawberry.field
    def metodos_pago(self) -> List[MetodoPago]:
        """Métodos de cobro disponibles y en qué modo está cada uno."""
        return [
            MetodoPago(
                clave=clave,
                nombre=m["nombre"],
                descripcion=m["descripcion"],
                en_linea=m["en_linea"],
                modo=modo_de(clave),
            )
            for clave, m in METODOS.items()
        ]

    # ---------------- panel de administración ----------------

    @strawberry.field
    def resumen_admin(self, info: Info, dias: int = 30) -> ResumenAdmin:
        requiere_admin(info)
        return _resumen_admin(dias)

    @strawberry.field
    def pedidos_admin(
        self,
        info: Info,
        estado: Optional[str] = None,
        metodo: Optional[str] = None,
        buscar: Optional[str] = None,
        limite: int = 20,
        salto: int = 0,
    ) -> PaginaPedidos:
        """Todos los pedidos con filtros y paginación (más recientes primero).
        estado acepta además 'por_cobrar' y 'por_reembolsar'."""
        requiere_admin(info)
        filtro = _filtro_pedidos_admin(estado, metodo, buscar)
        limite = max(1, min(limite, 100))
        cursor = db.pedidos.find(filtro).sort("_id", DESCENDING).skip(max(0, salto)).limit(limite)
        return PaginaPedidos(
            total=db.pedidos.count_documents(filtro),
            pedidos=[_pedido(d) for d in cursor],
        )

    # ---------------- membresías ----------------

    @strawberry.field
    def planes(self, info: Info, incluir_inactivos: bool = False) -> List[Plan]:
        """Planes a la venta. Con incluirInactivos=true (solo admin) salen todos."""
        filtro = {} if incluir_inactivos else {"activo": True}
        if incluir_inactivos:
            requiere_admin(info)
        return [_plan(d) for d in db.planes.find(filtro).sort([("orden", ASCENDING), ("_id", ASCENDING)])]

    @strawberry.field
    def mi_membresia(self, info: Info) -> Optional[Membresia]:
        """La que importa ahora: la vigente; si no hay, la pendiente de pago
        más reciente; si no, la última que tuvo."""
        usuario = usuario_actual(info)
        doc = (
            _membresia_vigente(usuario["_id"])
            or db.membresias.find_one(
                {"usuario_id": usuario["_id"], "estado": "pendiente"}, sort=[("_id", DESCENDING)]
            )
            or db.membresias.find_one({"usuario_id": usuario["_id"]}, sort=[("_id", DESCENDING)])
        )
        return _membresia(doc)

    @strawberry.field
    def mis_membresias(self, info: Info) -> List[Membresia]:
        usuario = usuario_actual(info)
        cursor = db.membresias.find({"usuario_id": usuario["_id"]}).sort("_id", DESCENDING)
        return [_membresia(d) for d in cursor]

    @strawberry.field
    def membresia(self, info: Info, id: int) -> Optional[Membresia]:
        return _membresia(_membresia_propia(usuario_actual(info), id))

    @strawberry.field
    def resumen_membresias(self, info: Info) -> ResumenMembresias:
        requiere_admin(info)
        return _resumen_membresias()

    @strawberry.field
    def membresias_admin(
        self,
        info: Info,
        estado: Optional[str] = None,
        plan_id: Optional[int] = None,
        buscar: Optional[str] = None,
        limite: int = 20,
        salto: int = 0,
    ) -> PaginaMembresias:
        """estado: activa | programada | vencida | pendiente | cancelada (vacío = todas)."""
        requiere_admin(info)
        filtro = _filtro_membresias(estado, plan_id, buscar)
        limite = max(1, min(limite, 100))
        cursor = db.membresias.find(filtro).sort("_id", DESCENDING).skip(max(0, salto)).limit(limite)
        return PaginaMembresias(
            total=db.membresias.count_documents(filtro),
            membresias=[_membresia(d) for d in cursor],
        )

    @strawberry.field
    def membresia_por_codigo(self, info: Info, codigo: str) -> Membresia:
        """Para la caja: revisa el código que enseña el cliente antes de canjear."""
        requiere_admin(info)
        return _membresia(_membresia_por_codigo(codigo))

    @strawberry.field
    def canjes_hoy(self, info: Info) -> List[CanjeAdmin]:
        requiere_admin(info)
        return _canjes_del_dia(_hoy_txt())

    @strawberry.field
    def clientes_admin(
        self, info: Info, buscar: Optional[str] = None, limite: int = 20, salto: int = 0
    ) -> PaginaClientes:
        requiere_admin(info)
        return _clientes_admin(buscar, limite, salto)


# =========================================================
# Mutation
# =========================================================

def _validar_categoria(categoria_id: int) -> None:
    # Mongo no tiene llaves foráneas: la integridad se revisa aquí
    if db.categorias.count_documents({"_id": categoria_id}, limit=1) == 0:
        raise ValueError(f"No existe la categoría {categoria_id}")


@strawberry.type
class Mutation:
    # ---------------- cuentas ----------------

    @strawberry.mutation
    def registrar_usuario(self, input: RegistroInput) -> AuthPayload:
        nombre = input.nombre.strip()
        email = input.email.strip().lower()

        if not nombre:
            raise ValueError("Escribe tu nombre")
        if not EMAIL_RE.match(email):
            raise ValueError("Ese correo no parece válido")
        if len(input.password) < PASSWORD_MIN:
            raise ValueError(f"La contraseña debe tener al menos {PASSWORD_MIN} caracteres")
        # Teléfono opcional; si viene, exactamente 10 dígitos (se revisa aquí
        # también porque alguien puede mandar la petición sin pasar por el front)
        telefono = input.telefono.strip()
        if telefono and not re.fullmatch(r"\d{10}", telefono):
            raise ValueError("El teléfono debe tener 10 dígitos, solo números")
        if db.usuarios.count_documents({"email": email}, limit=1):
            raise ValueError("Ya existe una cuenta con ese correo")

        doc = {
            "_id": siguiente_id("usuarios"),
            "nombre": nombre,
            "email": email,
            "telefono": telefono,
            "rol": "cliente",  # las cuentas nuevas nunca nacen como admin
            "password_hash": hashear_password(input.password),
            "creado": datetime.now().replace(microsecond=0),
        }
        try:
            db.usuarios.insert_one(doc)
        except DuplicateKeyError:
            # Por si dos registros con el mismo correo llegan al mismo tiempo
            raise ValueError("Ya existe una cuenta con ese correo")

        return AuthPayload(token=crear_token(doc["_id"]), usuario=_usuario(doc))

    @strawberry.mutation
    def iniciar_sesion(self, email: str, password: str) -> AuthPayload:
        usuario = db.usuarios.find_one({"email": email.strip().lower()})
        # Mismo mensaje si no existe el correo o si la contraseña está mal,
        # para no revelar qué correos tienen cuenta.
        if usuario is None or not verificar_password(password, usuario["password_hash"]):
            raise ValueError("Correo o contraseña incorrectos")
        return AuthPayload(token=crear_token(usuario["_id"]), usuario=_usuario(usuario))

    # ---------------- catálogo (solo admin) ----------------

    @strawberry.mutation
    def crear_producto(self, info: Info, input: ProductoInput) -> Producto:
        requiere_admin(info)
        _validar_categoria(input.categoria_id)
        if input.precio < 0 or input.stock < 0:
            raise ValueError("Precio y stock no pueden ser negativos")

        doc = {
            "_id": siguiente_id("productos"),
            "nombre": input.nombre,
            "descripcion": input.descripcion,
            "precio": float(input.precio),
            "stock": input.stock,
            "imagen_url": input.imagen_url,
            "categoria_id": input.categoria_id,
        }
        db.productos.insert_one(doc)
        return _producto(doc)

    @strawberry.mutation
    def actualizar_producto(self, info: Info, id: int, input: ProductoUpdateInput) -> Producto:
        requiere_admin(info)
        campos = {
            "nombre": input.nombre,
            "descripcion": input.descripcion,
            "precio": float(input.precio) if input.precio is not None else None,
            "stock": input.stock,
            "imagen_url": input.imagen_url,
            "categoria_id": input.categoria_id,
        }
        cambios = {k: v for k, v in campos.items() if v is not None}

        if "categoria_id" in cambios:
            _validar_categoria(cambios["categoria_id"])

        try:
            if cambios:
                doc = db.productos.find_one_and_update(
                    {"_id": id},
                    {"$set": cambios},
                    return_document=ReturnDocument.AFTER,
                )
            else:
                doc = db.productos.find_one({"_id": id})
        except WriteError:
            # Lo rechazó el validador $jsonSchema de la colección
            raise ValueError("Datos inválidos: revisa que precio y stock no sean negativos")

        if doc is None:
            raise ValueError(f"No existe el producto {id}")
        if "stock" in cambios:
            _avisar_stock_bajo([id])
        return _producto(doc)

    @strawberry.mutation
    def eliminar_producto(self, info: Info, id: int) -> bool:
        requiere_admin(info)
        # Equivalente al ON DELETE RESTRICT: no se borra si ya se vendió
        if db.pedidos.count_documents({"items.producto_id": id}, limit=1):
            raise ValueError("No se puede eliminar: el producto ya aparece en pedidos")
        return db.productos.delete_one({"_id": id}).deleted_count > 0

    # ---------------- checkout ----------------

    @strawberry.mutation
    def registrar_pedido(self, info: Info, input: PedidoInput) -> Pedido:
        """Checkout: valida stock, calcula el total con el precio vigente,
        descuenta stock y guarda el Pedido con sus items embebidos.

        El descuento de stock usa una actualización condicional atómica
        ({stock: {$gte: cantidad}} + $inc), así dos compras al mismo tiempo
        no pueden vender el mismo stock. Si algún producto falla, se
        regresa el stock que ya se había descontado (compensación), para
        que funcione igual en un MongoDB local sin replica set."""
        usuario = usuario_actual(info)

        if not input.items:
            raise ValueError("El pedido no tiene productos")
        if input.metodo_pago not in METODOS:
            raise ValueError("Elige un método de pago válido")

        # Junta cantidades si el mismo producto viene repetido
        cantidades: dict[int, int] = {}
        for item in input.items:
            if item.cantidad <= 0:
                raise ValueError("La cantidad debe ser mayor a cero")
            cantidades[item.producto_id] = cantidades.get(item.producto_id, 0) + item.cantidad

        descontados: list[tuple[int, int]] = []
        lineas = []
        try:
            for producto_id, cantidad in cantidades.items():
                prod = db.productos.find_one_and_update(
                    {"_id": producto_id, "stock": {"$gte": cantidad}},
                    {"$inc": {"stock": -cantidad}},
                    return_document=ReturnDocument.BEFORE,
                )
                if prod is None:
                    existe = db.productos.find_one({"_id": producto_id})
                    if existe is None:
                        raise ValueError(f"No existe el producto {producto_id}")
                    raise ValueError(
                        f"Stock insuficiente de {existe['nombre']}: "
                        f"quedan {existe['stock']}"
                    )
                descontados.append((producto_id, cantidad))
                lineas.append(
                    {
                        "producto_id": producto_id,
                        "cantidad": cantidad,
                        "precio_unit": float(prod["precio"]),
                    }
                )

            total = round(sum(l["cantidad"] * l["precio_unit"] for l in lineas), 2)
            pedido_id = siguiente_id("pedidos")
            doc = {
                "_id": pedido_id,
                "usuario_id": usuario["_id"],
                "fecha": _ahora(),
                "estado": "registrado",
                "total": total,
                "items": lineas,
                # El cobro arranca pendiente; iniciarPago lleva a la pasarela
                "pago": {
                    "metodo": input.metodo_pago,
                    "estado": "pendiente",
                    "modo": modo_de(input.metodo_pago),
                    "referencia": referencia_de(pedido_id),
                    "proveedor_id": "",
                    "pago_id": "",
                    "detalle": "",
                    "intentos": 0,
                    "fecha_pago": None,
                    "actualizado": _ahora(),
                },
            }
            db.pedidos.insert_one(doc)
            eventos.publicar(
                eventos.PEDIDO_NUEVO,
                f"Pedido nuevo #{pedido_id} de {usuario['nombre']} por {_dinero(total)}"
                f" ({METODOS[input.metodo_pago]['nombre']})",
                pedido_id=pedido_id,
                usuario_id=usuario["_id"],
                monto=total,
            )
            _avisar_stock_bajo(cantidades.keys())
            return _pedido(doc)

        except Exception:
            # Compensación: regresa el stock descontado antes del error
            for producto_id, cantidad in descontados:
                db.productos.update_one({"_id": producto_id}, {"$inc": {"stock": cantidad}})
            raise

    # ---------------- pagos ----------------

    @strawberry.mutation
    def iniciar_pago(self, info: Info, pedido_id: int, metodo: Optional[str] = None) -> InicioPago:
        """Prepara el cobro de un pedido y regresa a dónde mandar al cliente.

        - Mercado Pago / PayPal en sandbox: crea la preferencia/orden y
          regresa la URL de la pasarela real de pruebas.
        - En modo simulado: regresa /pago/simulado (pasarela de prueba local).
        - Transferencia / efectivo: url = null; el front muestra las
          instrucciones que vienen en pedido.pago.instrucciones.

        `metodo` permite cambiar de método si el primer intento falló."""
        usuario = usuario_actual(info)
        pedido = _pedido_propio(usuario, pedido_id)
        pago = pedido.get("pago") or {}

        if pedido["estado"] != "registrado":
            raise ValueError("Este pedido ya no tiene un pago pendiente")
        if pago.get("estado") in PAGO_CERRADO:
            raise ValueError("Este pedido ya está pagado")

        metodo = metodo or pago.get("metodo") or "mercadopago"
        if metodo not in METODOS:
            raise ValueError("Elige un método de pago válido")

        modo = modo_de(metodo)
        intento = int(pago.get("intentos", 0)) + 1
        cambios = {
            "pago.metodo": metodo,
            "pago.modo": modo,
            "pago.estado": "pendiente",
            "pago.referencia": referencia_de(pedido_id),
            "pago.intentos": intento,
            "pago.actualizado": _ahora(),
        }
        if metodo != pago.get("metodo"):
            cambios["pago.proveedor_id"] = ""
            cambios["pago.detalle"] = ""

        url = None
        try:
            if modo == "simulado":
                url = f"/pago/simulado?pedido={pedido_id}"
            elif metodo == "mercadopago":
                r = pagos.mp_crear_preferencia(
                    pedido, _lineas_con_nombre(pedido), usuario["email"], intento
                )
                cambios["pago.proveedor_id"], url = r["proveedor_id"], r["url"]
            elif metodo == "paypal":
                r = pagos.paypal_crear_orden(pedido, intento)
                cambios["pago.proveedor_id"], url = r["proveedor_id"], r["url"]
        except ErrorPago as e:
            raise ValueError(str(e))

        doc = db.pedidos.find_one_and_update(
            {"_id": pedido_id, "estado": "registrado"},
            {"$set": cambios},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise ValueError("Este pedido ya no tiene un pago pendiente")
        return InicioPago(pedido=_pedido(doc), url=url)

    @strawberry.mutation
    def confirmar_pago(self, info: Info, input: ConfirmarPagoInput) -> Pedido:
        """Se llama al regresar de la pasarela. Le pregunta al proveedor
        (nunca le cree al navegador) y actualiza el pedido."""
        usuario = usuario_actual(info)
        pedido = _pedido_propio(usuario, input.pedido_id)
        pago = pedido.get("pago") or {}

        if pago.get("estado") in PAGO_CERRADO:
            return _pedido(pedido)  # ya estaba listo (por ejemplo, recargaron la página)

        # El modo se toma de la configuración actual, no del guardado: si ya
        # pusiste llaves de sandbox, nadie puede "aprobar" con la simulación.
        metodo = pago.get("metodo")
        modo = modo_de(metodo) if metodo else None
        if not METODOS.get(metodo, {}).get("en_linea"):
            raise ValueError("Este pago lo confirma la tienda cuando recibe tu dinero")

        try:
            if modo == "simulado":
                if input.simulacion not in ("aprobado", "rechazado", "pendiente"):
                    raise ValueError("Resultado de simulación inválido")
                resultado = {
                    "estado": input.simulacion,
                    "detalle": f"Pasarela simulada: {input.simulacion}",
                    "pago_id": f"SIM-{pedido['_id']}-{pago.get('intentos', 1)}"
                    if input.simulacion == "aprobado"
                    else "",
                }
            elif metodo == "mercadopago":
                resultado = pagos.mp_consultar(pedido, input.payment_id)
            else:  # paypal
                if not input.paypal_token:
                    resultado = {"estado": "pendiente", "detalle": "Sin aprobar en PayPal"}
                else:
                    resultado = pagos.paypal_capturar(pedido, input.paypal_token)
        except ErrorPago as e:
            raise ValueError(str(e))

        return _pedido(_aplicar_resultado_pago(pedido, resultado))

    @strawberry.mutation
    def cancelar_mi_pedido(self, info: Info, id: int) -> Pedido:
        """El cliente puede cancelar mientras no haya pagado; el stock regresa."""
        usuario = usuario_actual(info)
        pedido = _pedido_propio(usuario, id)
        if pedido["estado"] != "registrado" or (pedido.get("pago") or {}).get("estado") in PAGO_CERRADO:
            raise ValueError("Este pedido ya está pagado; escríbenos para cancelarlo")
        return _pedido(_cancelar(pedido))

    # ---------------- pedidos (solo admin) ----------------

    @strawberry.mutation
    def cambiar_estado_pedido(self, info: Info, id: int, estado: str) -> Pedido:
        """Avanza el pedido respetando TRANSICIONES.
        - registrado → pagado: confirma a mano un pago (transferencia recibida).
        - registrado → entregado: solo efectivo (se cobra al recoger).
        - → cancelado: regresa el stock; si ya estaba pagado queda 'por reembolsar'."""
        requiere_admin(info)
        pedido = db.pedidos.find_one({"_id": id})
        if pedido is None:
            raise ValueError(f"No existe el pedido {id}")
        actual = pedido["estado"]
        if estado not in ESTADOS_PEDIDO:
            raise ValueError("Estado inválido")
        if estado not in TRANSICIONES[actual]:
            raise ValueError(f"Un pedido '{actual}' no puede pasar a '{estado}'")

        if estado == "cancelado":
            return _pedido(_cancelar(pedido))

        pago = pedido.get("pago") or {}
        cambios = {"estado": estado}
        if actual == "registrado":
            # Pasar de registrado a pagado/entregado implica que ya se cobró
            if estado == "entregado" and pago.get("metodo") not in ("efectivo", None):
                raise ValueError("Primero confirma el pago; solo efectivo se entrega sin pagar")
            if pago:
                cambios.update(
                    {
                        "pago.estado": "aprobado",
                        "pago.fecha_pago": _ahora(),
                        "pago.detalle": "Confirmado por la tienda",
                        "pago.actualizado": _ahora(),
                    }
                )

        doc = db.pedidos.find_one_and_update(
            {"_id": id, "estado": actual},  # nadie lo movió mientras tanto
            {"$set": cambios},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise ValueError("Alguien más actualizó este pedido; recarga la página")
        eventos.publicar(
            eventos.PEDIDO_ESTADO,
            f"Pedido #{id} pasó a {estado}",
            pedido_id=id,
            usuario_id=doc["usuario_id"],
        )
        return _pedido(doc)

    @strawberry.mutation
    def marcar_reembolsado(self, info: Info, id: int) -> Pedido:
        requiere_admin(info)
        doc = db.pedidos.find_one_and_update(
            {"_id": id, "pago.estado": "por_reembolsar"},
            {"$set": {"pago.estado": "reembolsado", "pago.actualizado": _ahora()}},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise ValueError("Este pedido no tiene un reembolso pendiente")
        eventos.publicar(
            eventos.PAGO_ACTUALIZADO,
            f"Pedido #{id} reembolsado",
            pedido_id=id,
            usuario_id=doc["usuario_id"],
        )
        return _pedido(doc)

    # ---------------- membresías (cliente) ----------------

    @strawberry.mutation
    def contratar_membresia(self, info: Info, plan_id: int, metodo_pago: str = "mercadopago") -> Membresia:
        """Crea la membresía 'pendiente' con su cobro. Se activa al pagarla.
        Si el cliente ya tiene una vigente, esta queda como renovación y
        empieza cuando termine la actual."""
        usuario = usuario_actual(info)
        if metodo_pago not in METODOS:
            raise ValueError("Elige un método de pago válido")
        plan = db.planes.find_one({"_id": plan_id, "activo": True})
        if plan is None:
            raise ValueError("Ese plan no está disponible")
        if db.membresias.count_documents({"usuario_id": usuario["_id"], "estado": "pendiente"}, limit=1):
            raise ValueError(
                "Ya tienes una membresía esperando pago. Págala o cancélala antes de contratar otra"
            )

        membresia_id = siguiente_id("membresias")
        doc = {
            "_id": membresia_id,
            "usuario_id": usuario["_id"],
            "plan_id": plan_id,
            "estado": "pendiente",
            "precio": float(plan["precio"]),   # precio con el que se vendió
            "creada": _ahora(),
            "inicio": None,
            "fin": None,
            "pago": {
                "metodo": metodo_pago,
                "estado": "pendiente",
                "modo": modo_de(metodo_pago),
                "referencia": referencia_membresia(membresia_id),
                "proveedor_id": "",
                "pago_id": "",
                "detalle": "",
                "intentos": 0,
                "fecha_pago": None,
                "actualizado": _ahora(),
            },
            "canjes": [],
        }
        db.membresias.insert_one(doc)
        eventos.publicar(
            eventos.MEMBRESIA_NUEVA,
            f"{usuario['nombre']} contrató {plan['nombre']} ({_dinero(plan['precio'])},"
            f" {METODOS[metodo_pago]['nombre']})",
            membresia_id=membresia_id,
            usuario_id=usuario["_id"],
            monto=float(plan["precio"]),
        )
        return _membresia(doc)

    @strawberry.mutation
    def iniciar_pago_membresia(
        self, info: Info, membresia_id: int, metodo: Optional[str] = None
    ) -> InicioPagoMembresia:
        """Igual que iniciarPago, pero para una membresía."""
        usuario = usuario_actual(info)
        doc = _membresia_propia(usuario, membresia_id)
        pago = doc.get("pago") or {}
        if doc["estado"] != "pendiente":
            raise ValueError("Esta membresía ya no tiene un pago pendiente")

        metodo = metodo or pago.get("metodo") or "mercadopago"
        if metodo not in METODOS:
            raise ValueError("Elige un método de pago válido")
        modo = modo_de(metodo)
        intento = int(pago.get("intentos", 0)) + 1
        cambios = {
            "pago.metodo": metodo,
            "pago.modo": modo,
            "pago.estado": "pendiente",
            "pago.intentos": intento,
            "pago.actualizado": _ahora(),
        }
        if metodo != pago.get("metodo"):
            cambios["pago.proveedor_id"] = ""
            cambios["pago.detalle"] = ""

        plan = db.planes.find_one({"_id": doc["plan_id"]}) or {"nombre": "Frecuente"}
        cargo = pagos.cargo_membresia({**doc, "total": doc["precio"]}, plan["nombre"])
        url = None
        try:
            if modo == "simulado":
                url = f"/pago/simulado?membresia={membresia_id}"
            elif metodo == "mercadopago":
                lineas = [{"producto_id": f"plan-{plan.get('_id', 0)}", "nombre": f"Membresía {plan['nombre']} (30 días)",
                           "cantidad": 1, "precio_unit": doc["precio"]}]
                r = pagos.mp_crear_preferencia(cargo, lineas, usuario["email"], intento)
                cambios["pago.proveedor_id"], url = r["proveedor_id"], r["url"]
            elif metodo == "paypal":
                r = pagos.paypal_crear_orden(cargo, intento)
                cambios["pago.proveedor_id"], url = r["proveedor_id"], r["url"]
        except ErrorPago as e:
            raise ValueError(str(e))

        nuevo = db.membresias.find_one_and_update(
            {"_id": membresia_id, "estado": "pendiente"},
            {"$set": cambios},
            return_document=ReturnDocument.AFTER,
        )
        if nuevo is None:
            raise ValueError("Esta membresía ya no tiene un pago pendiente")
        return InicioPagoMembresia(membresia=_membresia(nuevo), url=url)

    @strawberry.mutation
    def confirmar_pago_membresia(self, info: Info, input: ConfirmarPagoMembresiaInput) -> Membresia:
        """Al regresar de la pasarela. Igual que confirmarPago: se le
        pregunta al proveedor, nunca se le cree al navegador."""
        usuario = usuario_actual(info)
        doc = _membresia_propia(usuario, input.membresia_id)
        pago = doc.get("pago") or {}
        if pago.get("estado") in PAGO_CERRADO or doc["estado"] != "pendiente":
            return _membresia(doc)

        metodo = pago.get("metodo")
        if not METODOS.get(metodo, {}).get("en_linea"):
            raise ValueError("Este pago lo confirma la tienda cuando recibe tu dinero")
        modo = modo_de(metodo)

        plan = db.planes.find_one({"_id": doc["plan_id"]}) or {"nombre": "Frecuente"}
        cargo = pagos.cargo_membresia({**doc, "total": doc["precio"]}, plan["nombre"])
        try:
            if modo == "simulado":
                if input.simulacion not in ("aprobado", "rechazado", "pendiente"):
                    raise ValueError("Resultado de simulación inválido")
                resultado = {
                    "estado": input.simulacion,
                    "detalle": f"Pasarela simulada: {input.simulacion}",
                    "pago_id": f"SIM-M{doc['_id']}-{pago.get('intentos', 1)}"
                    if input.simulacion == "aprobado"
                    else "",
                }
            elif metodo == "mercadopago":
                resultado = pagos.mp_consultar(cargo, input.payment_id)
            else:
                if not input.paypal_token:
                    resultado = {"estado": "pendiente", "detalle": "Sin aprobar en PayPal"}
                else:
                    resultado = pagos.paypal_capturar(cargo, input.paypal_token)
        except ErrorPago as e:
            raise ValueError(str(e))

        return _membresia(_aplicar_resultado_pago_membresia(doc, resultado))

    @strawberry.mutation
    def cancelar_mi_membresia(self, info: Info, id: int) -> Membresia:
        """El cliente puede cancelar mientras no la haya pagado."""
        usuario = usuario_actual(info)
        doc = db.membresias.find_one_and_update(
            {"_id": id, "usuario_id": usuario["_id"], "estado": "pendiente"},
            {"$set": {"estado": "cancelada", "pago.actualizado": _ahora()}},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise ValueError("Solo puedes cancelar una membresía que no has pagado")
        eventos.publicar(
            eventos.MEMBRESIA_ACTUALIZADA,
            f"{usuario['nombre']} canceló la membresía {referencia_membresia(id)}",
            membresia_id=id,
            usuario_id=usuario["_id"],
        )
        return _membresia(doc)

    # ---------------- membresías (solo admin) ----------------

    @strawberry.mutation
    def confirmar_pago_membresia_manual(self, info: Info, id: int) -> Membresia:
        """Transferencia recibida o pago en efectivo en el local."""
        requiere_admin(info)
        doc = db.membresias.find_one({"_id": id})
        if doc is None:
            raise ValueError(f"No existe la membresía {id}")
        if doc["estado"] != "pendiente":
            raise ValueError("Esta membresía no está esperando pago")
        nuevo = _activar_membresia(doc, {}, "Confirmado por la tienda")
        if nuevo is None:
            raise ValueError("Alguien más actualizó esta membresía; recarga la página")
        return _membresia(nuevo)

    @strawberry.mutation
    def cancelar_membresia(self, info: Info, id: int) -> Membresia:
        """Si ya estaba pagada, el pago queda 'por reembolsar'."""
        requiere_admin(info)
        doc = db.membresias.find_one({"_id": id})
        if doc is None:
            raise ValueError(f"No existe la membresía {id}")
        if doc["estado"] == "cancelada":
            raise ValueError("Esta membresía ya está cancelada")
        cambios = {"estado": "cancelada", "pago.actualizado": _ahora()}
        if (doc.get("pago") or {}).get("estado") == "aprobado":
            cambios["pago.estado"] = "por_reembolsar"
        nuevo = db.membresias.find_one_and_update(
            {"_id": id, "estado": doc["estado"]},
            {"$set": cambios},
            return_document=ReturnDocument.AFTER,
        )
        if nuevo is None:
            raise ValueError("Alguien más actualizó esta membresía; recarga la página")
        eventos.publicar(
            eventos.MEMBRESIA_ACTUALIZADA,
            f"Membresía {referencia_membresia(id)} cancelada por la tienda",
            membresia_id=id,
            usuario_id=doc["usuario_id"],
        )
        return _membresia(nuevo)

    @strawberry.mutation
    def canjear_membresia(
        self,
        info: Info,
        opcion: str,
        codigo: Optional[str] = None,
        membresia_id: Optional[int] = None,
        nota: str = "",
    ) -> Membresia:
        """Registra el beneficio del día en la caja. UNA vez por día.

        El candado es atómico: el filtro exige que en `canjes` no exista ya
        un canje con el día de hoy. Si dos cajas canjean al mismo tiempo,
        MongoDB solo deja pasar una."""
        admin = requiere_admin(info)
        if codigo:
            doc = _membresia_por_codigo(codigo)
        elif membresia_id is not None:
            doc = db.membresias.find_one({"_id": membresia_id})
            if doc is None:
                raise ValueError(f"No existe la membresía {membresia_id}")
        else:
            raise ValueError("Escribe el código del cliente")

        if _estado_membresia(doc) != "activa":
            raise ValueError(f"La membresía no está activa ({_estado_membresia(doc)})")
        hoy = _hoy_txt()
        # Un cliente con renovación tiene dos documentos: el beneficio es
        # por PERSONA y por día, no por documento.
        if db.membresias.count_documents({"usuario_id": doc["usuario_id"], "canjes.dia": hoy}, limit=1):
            raise ValueError("Este cliente ya canjeó su beneficio de hoy")
        plan = db.planes.find_one({"_id": doc["plan_id"]}) or {}
        opciones = plan.get("opciones") or []
        if opciones and opcion not in opciones:
            raise ValueError("Esa opción no está incluida en el plan")

        nuevo = db.membresias.find_one_and_update(
            {
                "_id": doc["_id"],
                "estado": "activa",
                "inicio": {"$lte": _ahora()},
                "fin": {"$gte": _ahora()},
                "canjes.dia": {"$ne": hoy},
            },
            {
                "$push": {
                    "canjes": {
                        "dia": hoy,
                        "fecha": _ahora(),
                        "opcion": opcion,
                        "nota": nota.strip()[:120],
                        "admin_id": admin["_id"],
                    }
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if nuevo is None:
            raise ValueError("Este cliente ya canjeó su beneficio de hoy")

        usuario = db.usuarios.find_one({"_id": nuevo["usuario_id"]}) or {}
        eventos.publicar(
            eventos.CANJE,
            f"{usuario.get('nombre', 'Cliente')} canjeó: {opcion} ({plan.get('nombre', '')})",
            membresia_id=nuevo["_id"],
            usuario_id=nuevo["usuario_id"],
        )
        return _membresia(nuevo)

    @strawberry.mutation
    def crear_plan(self, info: Info, input: PlanInput) -> Plan:
        requiere_admin(info)
        if not input.nombre.strip():
            raise ValueError("Escribe el nombre del plan")
        if input.precio <= 0:
            raise ValueError("El precio debe ser mayor a cero")
        _id = siguiente_id("planes")
        doc = {
            "_id": _id,
            "nombre": input.nombre.strip(),
            "descripcion": input.descripcion.strip(),
            "precio": float(input.precio),
            "incluye": [x.strip() for x in input.incluye if x.strip()],
            "opciones": [x.strip() for x in input.opciones if x.strip()],
            "activo": input.activo,
            "orden": _id,
        }
        db.planes.insert_one(doc)
        return _plan(doc)

    @strawberry.mutation
    def actualizar_plan(self, info: Info, id: int, input: PlanUpdateInput) -> Plan:
        """Cambiar el precio NO afecta a las membresías ya vendidas
        (cada una guarda su propio precio)."""
        requiere_admin(info)
        cambios = {}
        if input.nombre is not None:
            if not input.nombre.strip():
                raise ValueError("Escribe el nombre del plan")
            cambios["nombre"] = input.nombre.strip()
        if input.precio is not None:
            if input.precio <= 0:
                raise ValueError("El precio debe ser mayor a cero")
            cambios["precio"] = float(input.precio)
        if input.descripcion is not None:
            cambios["descripcion"] = input.descripcion.strip()
        if input.incluye is not None:
            cambios["incluye"] = [x.strip() for x in input.incluye if x.strip()]
        if input.opciones is not None:
            cambios["opciones"] = [x.strip() for x in input.opciones if x.strip()]
        if input.activo is not None:
            cambios["activo"] = input.activo
        doc = (
            db.planes.find_one_and_update({"_id": id}, {"$set": cambios}, return_document=ReturnDocument.AFTER)
            if cambios
            else db.planes.find_one({"_id": id})
        )
        if doc is None:
            raise ValueError(f"No existe el plan {id}")
        return _plan(doc)


# =========================================================
# Subscription (tiempo real por WebSocket)
# =========================================================
# Cada campo es un generador asíncrono: mientras el navegador siga
# conectado, cada `yield` le manda un mensaje. Los avisos salen de
# eventos.py, que reparte lo que publican las mutations.

@strawberry.type
class Subscription:
    @strawberry.subscription
    async def eventos_admin(self, info: Info) -> AsyncGenerator[EventoTiempoReal, None]:
        """Feed del backoffice: pedidos nuevos, pagos, cambios de estado,
        stock bajo, membresías y canjes, en el momento en que pasan."""
        admin = requiere_admin(info)
        with eventos.suscribirse() as cola:
            yield _evento(
                {
                    "id": 0,
                    "tipo": "conectado",
                    "mensaje": f"Conectado en vivo como {admin['nombre']}",
                    "fecha": _ahora(),
                }
            )
            while True:
                yield _evento(await cola.get())

    @strawberry.subscription
    async def seguir_pedido(self, info: Info, id: int) -> AsyncGenerator[Pedido, None]:
        """El cliente ve cambiar su pedido (pago aprobado, enviado…) sin recargar."""
        usuario = usuario_actual(info)
        _pedido_propio(usuario, id)  # valida que sea suyo (o admin)
        with eventos.suscribirse() as cola:
            yield _pedido(db.pedidos.find_one({"_id": id}))
            while True:
                evento = await cola.get()
                if evento.get("pedido_id") == id:
                    yield _pedido(db.pedidos.find_one({"_id": id}))

    @strawberry.subscription
    async def seguir_membresia(self, info: Info, id: int) -> AsyncGenerator[Membresia, None]:
        """El cliente ve en vivo cuando la caja registra su canje del día."""
        usuario = usuario_actual(info)
        _membresia_propia(usuario, id)
        with eventos.suscribirse() as cola:
            yield _membresia(db.membresias.find_one({"_id": id}))
            while True:
                evento = await cola.get()
                if evento.get("membresia_id") == id:
                    yield _membresia(db.membresias.find_one({"_id": id}))


schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
