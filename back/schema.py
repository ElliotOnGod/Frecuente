"""
schema.py — esquema GraphQL (Strawberry) del e-commerce Frecuente.

Tipos: Categoria, Producto, Usuario, Pedido, PedidoItem, Pago, Entrega, MetodoPago,
       InicioPago, ResumenAdmin (+ sus series), PaginaPedidos, OpcionEnvio,
       InfoCodigoPostal, Rastreo, Suscripcion, CorreoEnviado, Integracion,
       Plan, Membresia, Canje, ResumenMembresias, ClienteAdmin, EventoTiempoReal
Query: categorias, categoria, productos(categoriaId, metodo, buscar), producto,
       metodosPreparacion, metodosPago, buscarCodigoPostal, cotizarEnvio, planes,
       yo, misPedidos, pedido, rastrearPedido, misSuscripciones,
       miMembresia, misMembresias, membresia,
       resumenAdmin, pedidosAdmin, resumenMembresias, membresiasAdmin,
       membresiaPorCodigo, canjesHoy, clientesAdmin, suscripcionesAdmin,
       correosAdmin, integraciones                                  (admin)
Mutation: registrarUsuario, iniciarSesion,
          registrarPedido, iniciarPago, confirmarPago, cancelarMiPedido,
          cambiarMiSuscripcion,
          crearProducto, actualizarProducto, eliminarProducto, subirImagen, (admin)
          cambiarEstadoPedido, generarGuia, marcarReembolsado,      (admin)
          procesarRecompras, cambiarRolUsuario, cambiarActivoUsuario, (admin)
          contratarMembresia, iniciarPagoMembresia, confirmarPagoMembresia,
          cancelarMiMembresia,
          confirmarPagoMembresiaManual, cancelarMembresia, canjearMembresia,
          crearPlan, actualizarPlan                                 (admin)
Subscription (tiempo real, WebSocket): eventosAdmin (admin),
          seguirPedido, seguirMembresia (dueño o admin)

Dónde vive cada dato:
  - MongoDB (database.db): categorías, productos, fotos, planes, membresías.
  - PostgreSQL (relacional.py): usuarios, pedidos, pagos, envíos,
    suscripciones de recompra y bitácora de correos.

Sesión: el front manda  Authorization: Bearer <token>  (ver auth.py).
  - Catálogo, metodosPago, buscarCodigoPostal y cotizarEnvio: público.
  - yo, misPedidos, pedido, registrarPedido, iniciarPago, confirmarPago,
    cancelarMiPedido, suscripciones: requieren sesión (cada cliente solo toca lo suyo).
  - Todo lo marcado (admin): requiere sesión con rol "admin".

Equipo: Jehu Uribe Bermudez (23100139),
        Jose Fernando Leon Lopez (23100146),
        Elliot Garcia Lopez (22300923)
Materia: Programacion Web II - CETI Colomos
"""

import base64
import binascii
import hashlib
import hmac
import re
import secrets
from datetime import date, datetime, timedelta
from typing import AsyncGenerator, List, Optional

import strawberry
from bson.binary import Binary
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import WriteError
from strawberry.types import Info

import correos
import envios
import eventos
import relacional
from auth import (
    JWT_SECRET,
    SesionInvalida,
    crear_token,
    gastar_tiempo_de_verificacion,
    hashear_password,
    token_de_request,
    usuario_id_de_token,
    verificar_password,
)
from database import (
    DIAS_MEMBRESIA,
    ESTADOS_PEDIDO,
    MAX_IMAGENES,
    METODOS_PREPARACION,
    a_dict,
    db,
    siguiente_id,
)
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
    nombre: str           # como se llamaba el producto al comprarlo
    variante: str         # "Molido para espresso", "" si no aplica
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
    imagen_url: str       # la foto principal (= imagenes[0]); "" si no tiene
    imagenes: List[str]   # galería completa, la principal primero
    categoria_id: int
    variante_nombre: str  # "Molienda"; "" si el producto no tiene variantes
    variantes: List[str]  # opciones que elige el cliente (mismo precio y stock)
    metodos: List[str]    # métodos de preparación (filtro del catálogo)
    peso_kg: float        # para cotizar el envío

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
class Entrega:
    """Cómo llega el pedido: se recoge en el local o va a domicilio (Envia.com)."""
    tipo: str             # recoger | domicilio
    nombre: str
    telefono: str
    calle: str
    numero: str
    colonia: str
    ciudad: str
    estado: str           # JA, CX, NL…
    cp: str
    referencias: str
    paqueteria: str
    servicio: str
    descripcion: str      # "Estafeta Terrestre"
    dias: str             # "2-3 días"
    costo: float
    modo: str             # simulado | sandbox | manual
    guia: str             # número de rastreo ("" hasta que se envía)
    rastreo_url: str
    etiqueta_url: str


def _entrega(e: dict | None) -> Optional[Entrega]:
    if not e:
        return None
    campos = {k: e.get(k) or "" for k in Entrega.__annotations__ if k != "costo"}
    return Entrega(**campos, costo=float(e.get("costo") or 0))


@strawberry.type
class Pedido:
    id: int
    usuario_id: int
    fecha: str
    estado: str
    subtotal: float       # productos
    costo_envio: float
    total: float          # subtotal + envío
    suscripcion_id: Optional[int]   # si lo generó una recompra
    # Los renglones, el pago y el envío vienen ya armados (relacional.py);
    # se guardan aquí sin exponerlos tal cual y los campos de abajo los convierten.
    items_doc: strawberry.Private[list]
    pago_doc: strawberry.Private[Optional[dict]]
    entrega_doc: strawberry.Private[Optional[dict]]

    @strawberry.field
    def usuario(self) -> Optional[Usuario]:
        return _usuario(relacional.usuario(self.usuario_id))

    @strawberry.field
    def entrega(self) -> Optional[Entrega]:
        return _entrega(self.entrega_doc)

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
                nombre=it.get("nombre", ""),
                variante=it.get("variante", ""),
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
    # Productos de entregas anteriores solo traen imagen_url (sin galería)
    imagenes = list(d.get("imagenes") or ([d["imagen_url"]] if d.get("imagen_url") else []))
    return Producto(
        id=d["id"],
        nombre=d["nombre"],
        descripcion=d.get("descripcion", ""),
        precio=float(d["precio"]),
        stock=d["stock"],
        imagen_url=imagenes[0] if imagenes else "",
        imagenes=imagenes,
        categoria_id=d["categoria_id"],
        variante_nombre=d.get("variante_nombre", "") if d.get("variantes") else "",
        variantes=list(d.get("variantes") or []),
        metodos=list(d.get("metodos") or []),
        peso_kg=float(d.get("peso_kg") or envios.PESO_DEFECTO_KG),
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
    if doc is None:
        return None
    return Pedido(
        id=doc["_id"],
        usuario_id=doc["usuario_id"],
        fecha=_fecha_txt(doc["fecha"]) or "",
        estado=doc["estado"],
        subtotal=float(doc.get("subtotal", doc["total"])),
        costo_envio=float(doc.get("envio", 0)),
        total=float(doc["total"]),
        suscripcion_id=doc.get("suscripcion_id"),
        items_doc=doc.get("items", []),
        pago_doc=doc.get("pago"),
        entrega_doc=doc.get("entrega"),
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
    recompras_activas: int
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
        return _usuario(relacional.usuario(self.usuario_id))

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
    rol: str
    activo: bool
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


# ---- catálogo, envíos, recompras e integraciones ----

@strawberry.type
class MetodoPreparacion:
    clave: str
    nombre: str


@strawberry.type
class InfoCodigoPostal:
    cp: str
    estado: str           # código de 2 letras (JA)
    estado_nombre: str
    ciudad: str
    colonias: List[str]


@strawberry.type
class OpcionEnvio:
    """Una cotización. `token` es la firma que se manda al registrar el pedido."""
    token: str
    paqueteria: str
    servicio: str
    descripcion: str
    dias: str
    costo: float
    modo: str


@strawberry.type
class EventoRastreo:
    fecha: str
    descripcion: str
    lugar: str


@strawberry.type
class Rastreo:
    guia: str
    paqueteria: str
    estado: str
    rastreo_url: str
    eventos: List[EventoRastreo]


@strawberry.type
class SuscripcionItem:
    producto_id: int
    variante: str
    cantidad: int

    @strawberry.field
    def producto(self) -> Optional[Producto]:
        return _producto(db.productos.find_one({"_id": self.producto_id}))


@strawberry.type
class Suscripcion:
    """Recompra: el mismo pedido se genera solo cada `cada_dias` días."""
    id: int
    usuario_id: int
    estado: str           # activa | pausada | cancelada
    cada_dias: int
    proxima: str          # "2026-12-08"
    metodo_pago: str
    creada: str
    items: List[SuscripcionItem]
    entrega_doc: strawberry.Private[dict]

    @strawberry.field
    def entrega(self) -> Optional[Entrega]:
        return _entrega(self.entrega_doc)

    @strawberry.field
    def usuario(self) -> Optional[Usuario]:
        return _usuario(relacional.usuario(self.usuario_id))

    @strawberry.field
    def pedidos(self) -> List[Pedido]:
        return [_pedido(d) for d in relacional.pedidos_de_suscripcion(self.id)]

    @strawberry.field
    def total_estimado(self) -> float:
        """Con los precios de hoy + el envío elegido."""
        precios = {
            p["_id"]: float(p["precio"])
            for p in db.productos.find({"_id": {"$in": [i.producto_id for i in self.items]}}, {"precio": 1})
        }
        productos = sum(precios.get(i.producto_id, 0) * i.cantidad for i in self.items)
        return round(productos + float(self.entrega_doc.get("costo") or 0), 2)


def _suscripcion(doc: dict | None) -> Optional[Suscripcion]:
    if doc is None:
        return None
    return Suscripcion(
        id=doc["_id"],
        usuario_id=doc["usuario_id"],
        estado=doc["estado"],
        cada_dias=doc["cada_dias"],
        proxima=doc["proxima"].isoformat(),
        metodo_pago=doc["metodo_pago"],
        creada=_fecha_txt(doc["creada"]) or "",
        items=[SuscripcionItem(**i) for i in doc["items"]],
        entrega_doc=doc["entrega"] or {},
    )


@strawberry.type
class CorreoEnviado:
    id: int
    destinatario: str
    asunto: str
    plantilla: str
    estado: str           # enviado | simulado | error
    detalle: str
    pedido_id: Optional[int]
    fecha: str


@strawberry.type
class Integracion:
    """Una API de terceros y en qué modo está (para el panel)."""
    clave: str
    nombre: str
    para_que: str
    modo: str
    activa: bool


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
    # Galería: la primera es la principal. Si viene, manda sobre imagen_url.
    imagenes: List[str] = strawberry.field(default_factory=list)
    categoria_id: int = 1
    variante_nombre: str = ""
    variantes: List[str] = strawberry.field(default_factory=list)
    metodos: List[str] = strawberry.field(default_factory=list)
    peso_kg: float = 0.5


@strawberry.input
class ProductoUpdateInput:
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    precio: Optional[float] = None
    stock: Optional[int] = None
    imagen_url: Optional[str] = None
    imagenes: Optional[List[str]] = None
    categoria_id: Optional[int] = None
    variante_nombre: Optional[str] = None
    variantes: Optional[List[str]] = None
    metodos: Optional[List[str]] = None
    peso_kg: Optional[float] = None


@strawberry.input
class ItemInput:
    producto_id: int
    cantidad: int
    variante: str = ""


@strawberry.input
class EntregaInput:
    """recoger: solo `tipo`. domicilio: la dirección + el token de la opción cotizada."""
    tipo: str = "recoger"
    nombre: str = ""
    telefono: str = ""
    calle: str = ""
    numero: str = ""
    colonia: str = ""
    ciudad: str = ""
    estado: str = ""
    cp: str = ""
    referencias: str = ""
    opcion_token: str = ""


@strawberry.input
class CotizarEnvioInput:
    cp: str
    estado: str
    ciudad: str = ""
    items: List[ItemInput] = strawberry.field(default_factory=list)


@strawberry.input
class PedidoInput:
    # Ya no se manda usuario_id: el pedido es del usuario de la sesión
    items: List[ItemInput]
    metodo_pago: str = "mercadopago"
    entrega: Optional[EntregaInput] = None          # sin entrega = recoger en el local
    recompra_cada_dias: Optional[int] = None        # 15, 30 o 60: repetir este pedido


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

    usuario = relacional.usuario(usuario_id_de_token(token))
    if usuario is None:
        raise SesionInvalida("Tu sesión expiró, inicia sesión de nuevo")
    if not usuario["activo"]:
        # El admin desactivó la cuenta: su token deja de servir al momento
        raise SesionInvalida("Tu cuenta está desactivada. Escríbenos si crees que es un error")
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
    pedido = relacional.pedido(pedido_id, None if usuario.get("rol") == "admin" else usuario["_id"])
    if pedido is None:
        raise ValueError(f"No encontramos el pedido {pedido_id}")
    return pedido


def _aplicar_resultado_pago(pedido: dict, resultado: dict) -> dict:
    """Guarda lo que dijo la pasarela y, si se aprobó, pasa el pedido a 'pagado'.

    Es idempotente: si el mismo aviso llega dos veces (regreso del cliente
    + webhook) el segundo no cambia nada. Un pago ya aprobado nunca vuelve
    a 'pendiente' o 'rechazado'. El renglón del pedido se bloquea
    (SELECT … FOR UPDATE) mientras se decide, así dos avisos simultáneos
    se atienden uno después del otro."""
    estado_pago = resultado["estado"]

    def calcular(actual: dict):
        if actual["pago"]["estado"] in PAGO_CERRADO:
            return None  # ya estaba cerrado: el aviso repetido no cambia nada
        cambios_pago = {
            "estado": estado_pago,
            "detalle": resultado.get("detalle", "")[:200],
            "actualizado": _ahora(),
        }
        if resultado.get("pago_id"):
            cambios_pago["pago_id"] = str(resultado["pago_id"])
        cambios_pedido = {}
        if estado_pago == "aprobado":
            cambios_pago["fecha_pago"] = _ahora()
            if actual["estado"] == "cancelado":
                # Pagaron un pedido que ya se había cancelado: hay que regresar el dinero
                cambios_pago["estado"] = "por_reembolsar"
            elif actual["estado"] == "registrado":
                cambios_pedido["estado"] = "pagado"
        return cambios_pedido, cambios_pago, None

    nuevo = relacional.actualizar_pedido(pedido["_id"], calcular=calcular)
    if nuevo is None:
        return relacional.pedido(pedido["_id"])

    eventos.publicar(
        eventos.PAGO_ACTUALIZADO,
        f"Pago del pedido #{pedido['_id']} {nuevo['pago']['estado']} ({_dinero(pedido['total'])})",
        pedido_id=pedido["_id"],
        usuario_id=pedido["usuario_id"],
        monto=float(pedido["total"]),
    )
    if nuevo["pago"]["estado"] == "aprobado":
        _avisar_pago_aprobado(nuevo)
    return nuevo


def _avisar_pago_aprobado(pedido: dict) -> None:
    cliente = relacional.usuario(pedido["usuario_id"])
    if cliente:
        correos.pedido_confirmado(pedido, cliente)


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

    def calcular(actual: dict):
        if actual["estado"] not in ("registrado", "pagado"):
            return None
        cambios_pago = {"actualizado": _ahora()}
        if actual["pago"]["estado"] == "aprobado":
            cambios_pago["estado"] = "por_reembolsar"
        return {"estado": "cancelado"}, cambios_pago, None

    doc = relacional.actualizar_pedido(pedido["_id"], calcular=calcular)
    if doc is None:
        raise ValueError("Este pedido ya no se puede cancelar")
    # El stock vive en MongoDB: se regresa después de cancelar en Postgres
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
    """Renglones para la pasarela; el envío va como un renglón más."""
    lineas = [
        {**i, "nombre": f"{i['nombre']} ({i['variante']})" if i.get("variante") else i["nombre"]}
        for i in pedido["items"]
    ]
    if pedido.get("envio"):
        lineas.append({"producto_id": "envio", "nombre": "Envío a domicilio", "cantidad": 1, "precio_unit": pedido["envio"]})
    return lineas


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
        usuario = relacional.usuario(nuevo["usuario_id"]) or {}
        if usuario:
            correos.membresia_activada(usuario, plan, nuevo)
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
            # Los usuarios están en PostgreSQL: primero se buscan ahí y con
            # sus ids se filtran las membresías en MongoDB.
            filtro["usuario_id"] = {"$in": relacional.ids_que_coinciden(texto)}
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
    membresias = list(db.membresias.find({"canjes.dia": dia}))
    usuarios = relacional.usuarios_por_ids(m["usuario_id"] for m in membresias)
    filas = []
    for m in membresias:
        usuario = usuarios.get(m["usuario_id"], {})
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


def _clientes_admin(buscar, limite, salto, incluir_admins=False) -> PaginaClientes:
    # Estadísticas de compra con un solo SELECT … GROUP BY en PostgreSQL
    filas = []
    for u in relacional.clientes_con_estadisticas(buscar, incluir_admins):
        vigente = _membresia_vigente(u["id"])
        filas.append(
            ClienteAdmin(
                id=u["id"],
                nombre=u["nombre"],
                email=u["email"],
                telefono=u["telefono"],
                rol=u["rol"],
                activo=u["activo"],
                creado=_fecha_txt(u["creado"]),
                pedidos=u["pedidos"],
                total_gastado=round(u["gastado"], 2),
                ultima_compra=_fecha_txt(u["ultima"]),
                membresia_id=vigente["_id"] if vigente else None,
            )
        )
    limite = max(1, min(limite, 100))
    return PaginaClientes(total=len(filas), clientes=filas[max(0, salto): max(0, salto) + limite])


# =========================================================
# Panel de administración: resumen
# =========================================================

STOCK_BAJO = 10


def _resumen_admin(dias: int) -> ResumenAdmin:
    """Las ventas salen de PostgreSQL (agregaciones SQL en relacional.py);
    el stock bajo, de MongoDB (catálogo)."""
    dias = max(1, min(dias, 365))
    hoy = _ahora().replace(hour=0, minute=0, second=0)
    desde = hoy - timedelta(days=dias - 1)
    r = relacional.resumen_ventas(desde, dias)
    ventas_total = round(r["ventas_total"], 2)

    return ResumenAdmin(
        dias=dias,
        ventas_total=ventas_total,
        ventas_periodo_anterior=round(r["ventas_periodo_anterior"], 2),
        pedidos_pagados=r["pedidos_pagados"],
        ticket_promedio=round(ventas_total / r["pedidos_pagados"], 2) if r["pedidos_pagados"] else 0.0,
        por_cobrar=round(r["por_cobrar"], 2),
        pedidos_por_cobrar=r["pedidos_por_cobrar"],
        pedidos_por_enviar=r["pedidos_por_enviar"],
        pedidos_por_reembolsar=r["pedidos_por_reembolsar"],
        clientes_total=r["clientes_total"],
        clientes_con_compra=r["clientes_con_compra"],
        recompras_activas=r["recompras_activas"],
        ventas_por_dia=[PuntoVenta(fecha=p["fecha"], total=round(p["total"], 2), pedidos=p["pedidos"]) for p in r["por_dia"]],
        por_metodo=[
            VentaMetodo(
                metodo=m,
                nombre=METODOS[m]["nombre"],
                total=round(r["por_metodo"].get(m, {}).get("total", 0.0), 2),
                pedidos=r["por_metodo"].get(m, {}).get("pedidos", 0),
            )
            for m in sorted(METODOS, key=lambda m: -r["por_metodo"].get(m, {}).get("total", 0.0))
        ],
        por_estado=[ConteoEstado(estado=e, pedidos=r["por_estado"].get(e, 0)) for e in ESTADOS_PEDIDO],
        top_productos=[
            ProductoVendido(producto_id=t["producto_id"], nombre=t["nombre"], piezas=t["piezas"], total=round(t["total"], 2))
            for t in r["top"]
        ],
        stock_bajo=[
            _producto(d)
            for d in db.productos.find({"stock": {"$lte": STOCK_BAJO}}).sort("stock", ASCENDING)
        ],
    )


# =========================================================
# Checkout: crear un pedido (lo usan registrarPedido y las recompras)
# =========================================================

TELEFONO_RE = re.compile(r"^\d{10}$")
RECOMPRA_DIAS = (15, 30, 60)


def _juntar_items(items) -> dict[tuple[int, str], int]:
    """{(producto_id, variante): cantidad}, sumando renglones repetidos."""
    cantidades: dict[tuple[int, str], int] = {}
    for item in items:
        cantidad = item["cantidad"] if isinstance(item, dict) else item.cantidad
        producto_id = item["producto_id"] if isinstance(item, dict) else item.producto_id
        variante = (item.get("variante", "") if isinstance(item, dict) else item.variante or "").strip()
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        clave = (producto_id, variante)
        cantidades[clave] = cantidades.get(clave, 0) + cantidad
    return cantidades


def _productos_de(cantidades) -> dict[int, dict]:
    ids = list({pid for pid, _ in cantidades})
    productos = {p["_id"]: p for p in db.productos.find({"_id": {"$in": ids}})}
    for pid in ids:
        if pid not in productos:
            raise ValueError(f"No existe el producto {pid}")
    return productos


def _normalizar_variantes(cantidades, productos) -> dict[tuple[int, str], int]:
    """Valida la variante de cada renglón. Si el producto tiene variantes y
    no se eligió ninguna, se usa la primera (p. ej. "Grano entero")."""
    limpio: dict[tuple[int, str], int] = {}
    for (pid, variante), cantidad in cantidades.items():
        opciones = productos[pid].get("variantes") or []
        if opciones:
            variante = variante or opciones[0]
            if variante not in opciones:
                raise ValueError(f"{productos[pid]['nombre']} no viene en «{variante}»")
        else:
            variante = ""
        limpio[(pid, variante)] = limpio.get((pid, variante), 0) + cantidad
    return limpio


def _peso(cantidades, productos) -> float:
    lineas = [{"producto_id": pid, "cantidad": c} for (pid, _), c in cantidades.items()]
    pesos = {pid: float(p.get("peso_kg") or envios.PESO_DEFECTO_KG) for pid, p in productos.items()}
    return envios.peso_de(lineas, pesos)


def _resolver_entrega(entrega_in: EntregaInput | None, metodo: str, kg: float) -> dict:
    """Valida la dirección y la cotización firmada. El costo del envío sale
    de la FIRMA del servidor, nunca de lo que mande el navegador."""
    if entrega_in is None or entrega_in.tipo == "recoger":
        return {"tipo": "recoger", "modo": "manual", "costo": 0.0}
    if entrega_in.tipo != "domicilio":
        raise ValueError("Elige cómo quieres recibir tu pedido")
    if metodo == "efectivo":
        raise ValueError("El pago en efectivo solo es al recoger en el local")
    d = {k: (getattr(entrega_in, k) or "").strip() for k in
         ("nombre", "telefono", "calle", "numero", "colonia", "ciudad", "estado", "cp", "referencias")}
    faltan = [n for n in ("nombre", "calle", "numero", "colonia", "ciudad", "cp") if not d[n]]
    if faltan:
        raise ValueError(f"Completa la dirección de envío ({', '.join(faltan)})")
    if not TELEFONO_RE.match(d["telefono"]):
        raise ValueError("El teléfono de entrega debe tener 10 dígitos")
    if d["estado"] not in envios.ESTADOS_MX:
        raise ValueError("Elige el estado de la dirección")
    d["referencias"] = d["referencias"][:200]
    try:
        opcion = envios.verificar(entrega_in.opcion_token, d["cp"], kg)
    except envios.ErrorEnvio as e:
        raise ValueError(str(e))
    return {"tipo": "domicilio", **d, **opcion}


def _crear_pedido(
    usuario: dict,
    items,
    metodo: str,
    entrega: dict,
    *,
    recompra_cada_dias: int | None = None,
    suscripcion_id: int | None = None,
    con=None,
) -> dict:
    """Descuenta stock en MongoDB y guarda el pedido en PostgreSQL.

    Stock: actualización condicional atómica ({stock: {$gte: n}} + $inc),
    así dos compras al mismo tiempo no pueden vender la misma pieza. Si
    algo falla después (otro producto sin stock, error en Postgres…), se
    REGRESA el stock ya descontado (compensación), porque una transacción
    no puede abarcar dos bases de datos distintas.

    Pedido: pedido + renglones + pago + envío (+ la suscripción, si pidió
    recompra) se insertan en UNA transacción de PostgreSQL."""
    if metodo not in METODOS:
        raise ValueError("Elige un método de pago válido")
    if metodo == "efectivo" and entrega.get("tipo") == "domicilio":
        raise ValueError("El pago en efectivo solo es al recoger en el local")

    cantidades = _juntar_items(items)
    if not cantidades:
        raise ValueError("El pedido no tiene productos")
    productos = _productos_de(cantidades)
    cantidades = _normalizar_variantes(cantidades, productos)

    por_producto: dict[int, int] = {}
    for (pid, _), c in cantidades.items():
        por_producto[pid] = por_producto.get(pid, 0) + c

    descontados: list[tuple[int, int]] = []
    precios: dict[int, float] = {}
    try:
        for producto_id, cantidad in por_producto.items():
            prod = db.productos.find_one_and_update(
                {"_id": producto_id, "stock": {"$gte": cantidad}},
                {"$inc": {"stock": -cantidad}},
                return_document=ReturnDocument.BEFORE,
            )
            if prod is None:
                existe = db.productos.find_one({"_id": producto_id}) or productos[producto_id]
                raise ValueError(f"Stock insuficiente de {existe['nombre']}: quedan {existe['stock']}")
            descontados.append((producto_id, cantidad))
            precios[producto_id] = float(prod["precio"])

        lineas = [
            {
                "producto_id": pid,
                "nombre": productos[pid]["nombre"],
                "variante": variante,
                "cantidad": cantidad,
                "precio_unit": precios[pid],
            }
            for (pid, variante), cantidad in cantidades.items()
        ]
        pago = {
            "metodo": metodo,
            "estado": "pendiente",
            "modo": modo_de(metodo),
            "actualizado": _ahora(),
        }
        columnas_envio = {k: v for k, v in entrega.items() if k in relacional._COLS_ENVIO}

        def guardar(c) -> int:
            sid = suscripcion_id
            if recompra_cada_dias:
                sid = relacional.crear_suscripcion(
                    c,
                    usuario_id=usuario["_id"],
                    cada_dias=recompra_cada_dias,
                    proxima=date.today() + timedelta(days=recompra_cada_dias),
                    metodo_pago=metodo,
                    entrega=relacional_json(entrega),
                    items=[{"producto_id": pid, "variante": v, "cantidad": n} for (pid, v), n in cantidades.items()],
                )
            return relacional.insertar_pedido(
                c,
                usuario_id=usuario["_id"],
                fecha=_ahora(),
                estado="registrado",
                lineas=lineas,
                envio=float(entrega.get("costo") or 0),
                pago=pago,
                entrega=columnas_envio,
                suscripcion_id=sid,
            )

        if con is not None:
            with con.transaction():   # SAVEPOINT dentro de la transacción de quien llama
                pedido_id = guardar(con)
        else:
            with relacional.transaccion() as c:
                pedido_id = guardar(c)
    except Exception:
        # Compensación: regresa el stock descontado antes del error
        for producto_id, cantidad in descontados:
            db.productos.update_one({"_id": producto_id}, {"$inc": {"stock": cantidad}})
        raise

    return {"_id": pedido_id, "por_producto": por_producto}


def relacional_json(entrega: dict) -> dict:
    """La entrega elegida se guarda en la suscripción (JSONB) para repetirla."""
    return {k: v for k, v in entrega.items() if k in relacional._COLS_ENVIO}


def _despues_de_crear(pedido: dict, usuario: dict, por_producto) -> None:
    eventos.publicar(
        eventos.PEDIDO_NUEVO,
        f"Pedido nuevo #{pedido['_id']} de {usuario['nombre']} por {_dinero(pedido['total'])}"
        f" ({METODOS[pedido['pago']['metodo']]['nombre']})",
        pedido_id=pedido["_id"],
        usuario_id=usuario["_id"],
        monto=float(pedido["total"]),
    )
    _avisar_stock_bajo(por_producto.keys())
    correos.pedido_nuevo_tienda(pedido, usuario)


def procesar_recompras(hoy: date | None = None) -> int:
    """Genera el pedido de cada suscripción a la que ya le tocó.

    Lo corre: el ciclo automático del backend (cada hora), el botón
    "Procesar ahora" del panel y, si se configura, un cron externo
    (POST /tareas/recompras). FOR UPDATE SKIP LOCKED evita pedidos dobles
    si dos de esos corren al mismo tiempo."""
    hoy = hoy or date.today()
    creados: list[tuple[dict, dict, int]] = []
    sin_stock: list[tuple[dict, str]] = []
    with relacional.transaccion() as con:
        for s in relacional.recompras_vencidas(con, hoy):
            usuario = relacional.usuario(s["usuario_id"])
            if usuario is None or not usuario["activo"]:
                continue
            try:
                r = _crear_pedido(usuario, s["items"], s["metodo_pago"], s["entrega"] or {"tipo": "recoger"},
                                  suscripcion_id=s["id"], con=con)
                siguiente = hoy + timedelta(days=s["cada_dias"])
                creados.append((r, usuario, s["cada_dias"]))
            except ValueError as e:
                # Sin stock (u otro problema): se reintenta mañana y se avisa
                siguiente = hoy + timedelta(days=1)
                sin_stock.append((usuario, str(e)))
            con.execute("UPDATE suscripciones SET proxima = %s WHERE id = %s", (siguiente, s["id"]))

    for r, usuario, cada_dias in creados:
        pedido = relacional.pedido(r["_id"])
        _despues_de_crear(pedido, usuario, r["por_producto"])
        correos.recompra_lista(pedido, usuario, cada_dias)
    for usuario, mensaje in sin_stock:
        correos.recompra_sin_stock(usuario, mensaje)
    if creados:
        print(f"[frecuente] Recompras: se generaron {len(creados)} pedidos")
    return len(creados)


def _generar_guia(pedido: dict) -> dict:
    """Pide la guía a Envia.com con el peso real del pedido."""
    productos = {p["_id"]: p for p in db.productos.find({"_id": {"$in": [i["producto_id"] for i in pedido["items"]]}})}
    pesos = {pid: float(p.get("peso_kg") or envios.PESO_DEFECTO_KG) for pid, p in productos.items()}
    try:
        return envios.generar_guia(pedido, envios.peso_de(pedido["items"], pesos))
    except envios.ErrorEnvio as e:
        raise ValueError(str(e))


def _cliente_admin_de(usuario_id: int) -> ClienteAdmin:
    u = relacional.usuario(usuario_id)
    fila = next(
        (c for c in _clientes_admin(u["email"], 100, 0, incluir_admins=True).clientes if c.id == usuario_id), None
    )
    if fila is None:
        raise ValueError(f"No existe el usuario {usuario_id}")
    return fila


def _integraciones() -> List[Integracion]:
    """Las APIs de terceros del proyecto y en qué modo está cada una."""
    return [
        Integracion(clave="mercadopago", nombre="Mercado Pago", para_que="Cobro con tarjeta, OXXO y saldo",
                    modo=modo_de("mercadopago"), activa=True),
        Integracion(clave="paypal", nombre="PayPal", para_que="Cobro con cuenta PayPal",
                    modo=modo_de("paypal"), activa=True),
        Integracion(clave="envia", nombre="Envia.com", para_que="Cotizar envíos, generar guías y rastrear",
                    modo=envios.modo(), activa=True),
        Integracion(clave="envia_geocodes", nombre="Envia Geocodes", para_que="Estado, ciudad y colonias por código postal",
                    modo="real", activa=True),
        Integracion(clave="brevo", nombre="Brevo", para_que="Correos de confirmación, envío y recompra",
                    modo=correos.modo(), activa=True),
        Integracion(clave="openfreemap", nombre="OpenFreeMap + MapLibre", para_que="Mapa del local en la página de inicio",
                    modo="real", activa=True),
    ]


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
    def productos(
        self,
        categoria_id: Optional[int] = None,
        metodo: Optional[str] = None,
        buscar: Optional[str] = None,
    ) -> List[Producto]:
        """Catálogo con filtros: categoría, método de preparación y texto libre
        (busca en nombre, descripción y variantes, sin importar mayúsculas)."""
        filtro: dict = {}
        if categoria_id is not None:
            filtro["categoria_id"] = categoria_id
        if metodo:
            filtro["metodos"] = metodo          # el arreglo contiene ese método
        if buscar and buscar.strip():
            patron = {"$regex": re.escape(buscar.strip()[:60]), "$options": "i"}
            filtro["$or"] = [{"nombre": patron}, {"descripcion": patron}, {"variantes": patron}]
        return [_producto(d) for d in db.productos.find(filtro).sort("_id", ASCENDING)]

    @strawberry.field
    def producto(self, id: int) -> Optional[Producto]:
        return _producto(db.productos.find_one({"_id": id}))

    @strawberry.field
    def metodos_preparacion(self) -> List[MetodoPreparacion]:
        return [MetodoPreparacion(clave=k, nombre=v) for k, v in METODOS_PREPARACION.items()]

    @strawberry.field
    def buscar_codigo_postal(self, cp: str) -> InfoCodigoPostal:
        """Autollenado de la dirección (API pública de Envia)."""
        try:
            return InfoCodigoPostal(**envios.buscar_cp(cp))
        except envios.ErrorEnvio as e:
            raise ValueError(str(e))

    @strawberry.field
    def cotizar_envio(self, input: CotizarEnvioInput) -> List[OpcionEnvio]:
        """Opciones de paquetería para el carrito. El peso se calcula aquí
        con los productos de la base, no con lo que diga el navegador."""
        cantidades = _juntar_items(input.items)
        if not cantidades:
            raise ValueError("Tu carrito está vacío")
        productos = _productos_de(cantidades)
        kg = _peso(cantidades, productos)
        valor = sum(float(productos[pid]["precio"]) * c for (pid, _), c in cantidades.items())
        try:
            opciones = envios.cotizar(
                {"cp": input.cp.strip(), "estado": input.estado.strip().upper(), "ciudad": input.ciudad.strip()},
                kg,
                valor,
            )
        except envios.ErrorEnvio as e:
            raise ValueError(str(e))
        return [OpcionEnvio(**o) for o in opciones]

    @strawberry.field
    def yo(self, info: Info) -> Optional[Usuario]:
        """Usuario de la sesión actual (null si no hay sesión)."""
        return _usuario(usuario_actual(info, requerido=False))

    @strawberry.field
    def mis_pedidos(self, info: Info) -> List[Pedido]:
        usuario = usuario_actual(info)
        return [_pedido(d) for d in relacional.pedidos_de_usuario(usuario["_id"])]

    @strawberry.field
    def pedido(self, info: Info, id: int) -> Optional[Pedido]:
        """Un cliente solo ve sus pedidos; un admin ve cualquiera."""
        usuario = usuario_actual(info)
        return _pedido(relacional.pedido(id, None if usuario.get("rol") == "admin" else usuario["_id"]))

    @strawberry.field
    def rastrear_pedido(self, info: Info, id: int) -> Rastreo:
        """Estado del envío con la paquetería (Envia.com)."""
        pedido = _pedido_propio(usuario_actual(info), id)
        entrega = pedido.get("entrega") or {}
        if entrega.get("tipo") != "domicilio":
            raise ValueError("Este pedido se recoge en el local")
        try:
            r = envios.rastrear(pedido)
        except envios.ErrorEnvio as e:
            raise ValueError(str(e))
        return Rastreo(
            guia=entrega.get("guia", ""),
            paqueteria=entrega.get("descripcion", ""),
            estado=r["estado"],
            rastreo_url=entrega.get("rastreo_url", ""),
            eventos=[EventoRastreo(**e) for e in r["eventos"]],
        )

    @strawberry.field
    def mis_suscripciones(self, info: Info) -> List[Suscripcion]:
        usuario = usuario_actual(info)
        return [_suscripcion(d) for d in relacional.suscripciones(usuario_id=usuario["_id"])]

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
        limite = max(1, min(limite, 100))
        total, docs = relacional.pedidos_admin(estado, metodo, buscar, limite, max(0, salto))
        return PaginaPedidos(total=total, pedidos=[_pedido(d) for d in docs])

    @strawberry.field
    def suscripciones_admin(self, info: Info, estado: Optional[str] = None) -> List[Suscripcion]:
        requiere_admin(info)
        return [_suscripcion(d) for d in relacional.suscripciones(estado=estado or None)]

    @strawberry.field
    def correos_admin(self, info: Info, limite: int = 30) -> List[CorreoEnviado]:
        """Bitácora de correos (Brevo o simulados)."""
        requiere_admin(info)
        return [
            CorreoEnviado(
                id=c["id"], destinatario=c["destinatario"], asunto=c["asunto"], plantilla=c["plantilla"],
                estado=c["estado"], detalle=c["detalle"], pedido_id=c["pedido_id"], fecha=_fecha_txt(c["creado"]) or "",
            )
            for c in relacional.correos_recientes(max(1, min(limite, 100)))
        ]

    @strawberry.field
    def integraciones(self, info: Info) -> List[Integracion]:
        requiere_admin(info)
        return _integraciones()

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
        self,
        info: Info,
        buscar: Optional[str] = None,
        limite: int = 20,
        salto: int = 0,
        incluir_admins: bool = False,
    ) -> PaginaClientes:
        requiere_admin(info)
        return _clientes_admin(buscar, limite, salto, incluir_admins)


# =========================================================
# Mutation
# =========================================================

# ---------------- imágenes de productos ----------------

IMAGEN_SUBIDA_RE = re.compile(r"^/imagenes/[0-9a-f]{32}$")
IMAGEN_MAX_BYTES = 3 * 1024 * 1024   # el front ya las comprime a ~100–300 KB


def _tipo_imagen(datos: bytes) -> str | None:
    """Tipo real del archivo según sus primeros bytes ("número mágico"),
    sin creerle a la extensión ni a lo que diga el navegador.
    SVG no se acepta: puede traer JavaScript adentro."""
    if datos.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    return None


def _validar_imagenes(imagenes: List[str]) -> List[str]:
    """Galería de un producto: máximo MAX_IMAGENES, sin repetidas, y cada
    una debe ser una foto subida aquí (/imagenes/<id>) o una URL https."""
    limpias: List[str] = []
    for url in imagenes:
        url = (url or "").strip()
        if not url or url in limpias:
            continue
        if IMAGEN_SUBIDA_RE.match(url):
            if db.imagenes.count_documents({"_id": url.rsplit("/", 1)[1]}, limit=1) == 0:
                raise ValueError("Una de las imágenes ya no existe; vuelve a subirla")
        elif not (url.startswith("https://") and len(url) <= 500 and not re.search(r"\s", url)):
            raise ValueError("Las imágenes deben subirse desde el panel o ser una URL https://")
        limpias.append(url)
    if len(limpias) > MAX_IMAGENES:
        raise ValueError(f"Máximo {MAX_IMAGENES} imágenes por producto")
    return limpias


def _validar_categoria(categoria_id: int) -> None:
    # Mongo no tiene llaves foráneas: la integridad se revisa aquí
    if db.categorias.count_documents({"_id": categoria_id}, limit=1) == 0:
        raise ValueError(f"No existe la categoría {categoria_id}")


def _limpiar_variantes(variantes: List[str]) -> List[str]:
    limpias: List[str] = []
    for v in variantes:
        v = (v or "").strip()[:60]
        if v and v not in limpias:
            limpias.append(v)
    if len(limpias) > 12:
        raise ValueError("Máximo 12 variantes por producto")
    return limpias


def _limpiar_metodos(metodos: List[str]) -> List[str]:
    invalidos = [m for m in metodos if m not in METODOS_PREPARACION]
    if invalidos:
        raise ValueError(f"Método de preparación desconocido: {', '.join(invalidos)}")
    return list(dict.fromkeys(metodos))


def _validar_peso(peso_kg: float) -> float:
    if not 0 < peso_kg <= 30:
        raise ValueError("El peso debe estar entre 0 y 30 kg (sirve para cotizar el envío)")
    return round(float(peso_kg), 3)


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
        if relacional.existe_email(email):
            raise ValueError("Ya existe una cuenta con ese correo")

        try:
            # rol "cliente": las cuentas nuevas nunca nacen como admin
            doc = relacional.crear_usuario(nombre, email, telefono, hashear_password(input.password))
        except relacional.CorreoDuplicado:
            # Por si dos registros con el mismo correo llegan al mismo tiempo
            # (lo detecta el UNIQUE de la tabla usuarios)
            raise ValueError("Ya existe una cuenta con ese correo")

        correos.bienvenida(doc)
        return AuthPayload(token=crear_token(doc["_id"]), usuario=_usuario(doc))

    @strawberry.mutation
    def iniciar_sesion(self, email: str, password: str) -> AuthPayload:
        usuario = relacional.usuario_por_email(email.strip().lower())
        # Mismo mensaje Y mismo tiempo si no existe el correo o si la
        # contraseña está mal, para no revelar qué correos tienen cuenta.
        if usuario is None:
            gastar_tiempo_de_verificacion(password)
            raise ValueError("Correo o contraseña incorrectos")
        if not verificar_password(password, usuario["password_hash"]):
            raise ValueError("Correo o contraseña incorrectos")
        if not usuario["activo"]:
            raise ValueError("Tu cuenta está desactivada. Escríbenos si crees que es un error")
        return AuthPayload(token=crear_token(usuario["_id"]), usuario=_usuario(usuario))

    # ---------------- catálogo (solo admin) ----------------

    @strawberry.mutation
    def crear_producto(self, info: Info, input: ProductoInput) -> Producto:
        requiere_admin(info)
        _validar_categoria(input.categoria_id)
        if not input.nombre.strip():
            raise ValueError("Escribe el nombre del producto")
        if input.precio < 0 or input.stock < 0:
            raise ValueError("Precio y stock no pueden ser negativos")
        imagenes = _validar_imagenes(
            input.imagenes or ([input.imagen_url] if input.imagen_url else [])
        )
        variantes = _limpiar_variantes(input.variantes)

        doc = {
            "_id": siguiente_id("productos"),
            "nombre": input.nombre.strip(),
            "descripcion": input.descripcion,
            "precio": float(input.precio),
            "stock": input.stock,
            "imagen_url": imagenes[0] if imagenes else "",
            "imagenes": imagenes,
            "categoria_id": input.categoria_id,
            "variante_nombre": (input.variante_nombre.strip() or "Presentación") if variantes else "",
            "variantes": variantes,
            "metodos": _limpiar_metodos(input.metodos),
            "peso_kg": _validar_peso(input.peso_kg),
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

        # La galería manda: la principal (imagenes[0]) también queda en imagen_url
        if input.imagenes is not None or "imagen_url" in cambios:
            lista = input.imagenes if input.imagenes is not None else [cambios["imagen_url"]]
            imagenes = _validar_imagenes(lista)
            cambios["imagenes"] = imagenes
            cambios["imagen_url"] = imagenes[0] if imagenes else ""

        if "nombre" in cambios:
            if not cambios["nombre"].strip():
                raise ValueError("Escribe el nombre del producto")
            cambios["nombre"] = cambios["nombre"].strip()
        if "categoria_id" in cambios:
            _validar_categoria(cambios["categoria_id"])
        if input.variantes is not None:
            cambios["variantes"] = _limpiar_variantes(input.variantes)
            if not cambios["variantes"]:
                cambios["variante_nombre"] = ""
        if input.variante_nombre is not None and cambios.get("variantes", True):
            cambios["variante_nombre"] = input.variante_nombre.strip() or "Presentación"
        if input.metodos is not None:
            cambios["metodos"] = _limpiar_metodos(input.metodos)
        if input.peso_kg is not None:
            cambios["peso_kg"] = _validar_peso(input.peso_kg)

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
    def subir_imagen(self, info: Info, datos: str) -> str:
        """Sube una foto (en base64) y regresa su ruta: /imagenes/<id>.
        Después se pone en la galería del producto con crear/actualizarProducto.

        Se guarda en MongoDB y la sirve GET /imagenes/<id> (main.py).
        Solo se aceptan JPEG, PNG y WebP de hasta 3 MB, revisando los bytes
        del archivo (no la extensión)."""
        admin = requiere_admin(info)
        if datos.startswith("data:") and "," in datos[:100]:
            datos = datos.split(",", 1)[1]  # quita el "data:image/webp;base64,"
        if len(datos) > IMAGEN_MAX_BYTES * 4 // 3 + 8:
            raise ValueError("La imagen pesa más de 3 MB")
        try:
            contenido = base64.b64decode(datos, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("La imagen llegó dañada; intenta de nuevo")
        tipo = _tipo_imagen(contenido)
        if tipo is None:
            raise ValueError("Solo se aceptan imágenes JPG, PNG o WebP")
        if len(contenido) > IMAGEN_MAX_BYTES:
            raise ValueError("La imagen pesa más de 3 MB")

        imagen_id = secrets.token_hex(16)
        db.imagenes.insert_one(
            {
                "_id": imagen_id,
                "tipo": tipo,
                "datos": Binary(contenido),
                "bytes": len(contenido),
                "creada": _ahora(),
                "admin_id": admin["_id"],
            }
        )
        return f"/imagenes/{imagen_id}"

    @strawberry.mutation
    def eliminar_producto(self, info: Info, id: int) -> bool:
        requiere_admin(info)
        # Equivalente al ON DELETE RESTRICT: no se borra si ya se vendió
        # (los renglones de pedidos están en PostgreSQL)
        if relacional.producto_vendido(id):
            raise ValueError("No se puede eliminar: el producto ya aparece en pedidos")
        return db.productos.delete_one({"_id": id}).deleted_count > 0

    # ---------------- checkout ----------------

    @strawberry.mutation
    def registrar_pedido(self, info: Info, input: PedidoInput) -> Pedido:
        """Checkout: valida stock, calcula el total con el precio vigente y el
        envío firmado, descuenta stock y guarda el pedido (ver _crear_pedido).

        Con recompraCadaDias (15, 30 o 60) además crea la suscripción: el
        mismo pedido se generará solo cada ese número de días."""
        usuario = usuario_actual(info)
        if not input.items:
            raise ValueError("El pedido no tiene productos")
        if input.recompra_cada_dias is not None and input.recompra_cada_dias not in RECOMPRA_DIAS:
            raise ValueError("La recompra puede ser cada 15, 30 o 60 días")
        if input.recompra_cada_dias and input.metodo_pago == "efectivo":
            raise ValueError("La recompra se paga en línea o por transferencia, no en efectivo")

        cantidades = _juntar_items(input.items)
        productos = _productos_de(cantidades)
        kg = _peso(_normalizar_variantes(cantidades, productos), productos)
        entrega = _resolver_entrega(input.entrega, input.metodo_pago, kg)

        r = _crear_pedido(
            usuario, input.items, input.metodo_pago, entrega, recompra_cada_dias=input.recompra_cada_dias
        )
        pedido = relacional.pedido(r["_id"])
        _despues_de_crear(pedido, usuario, r["por_producto"])
        return _pedido(pedido)

    # ---------------- recompras (cliente) ----------------

    @strawberry.mutation
    def cambiar_mi_suscripcion(
        self,
        info: Info,
        id: int,
        estado: Optional[str] = None,
        cada_dias: Optional[int] = None,
    ) -> Suscripcion:
        """Pausar ('pausada'), reanudar ('activa'), cancelar ('cancelada') o
        cambiar cada cuántos días llega. Una cancelada ya no se reactiva."""
        usuario = usuario_actual(info)
        cambios: dict = {}
        if estado is not None:
            if estado not in ("activa", "pausada", "cancelada"):
                raise ValueError("Estado de suscripción inválido")
            cambios["estado"] = estado
        if cada_dias is not None:
            if cada_dias not in RECOMPRA_DIAS:
                raise ValueError("La recompra puede ser cada 15, 30 o 60 días")
            cambios["cada_dias"] = cada_dias
        if not cambios:
            raise ValueError("No hay nada que cambiar")
        actual = relacional.suscripcion(id, usuario["_id"])
        if actual is None:
            raise ValueError(f"No encontramos la suscripción {id}")
        if cambios.get("estado") == "activa" and actual["proxima"] < date.today():
            # Al reanudar después de mucho tiempo no se generan pedidos atrasados
            cambios["proxima"] = date.today() + timedelta(days=cambios.get("cada_dias", actual["cada_dias"]))
        doc = relacional.cambiar_suscripcion(id, usuario["_id"], **cambios)
        if doc is None:
            raise ValueError("Esta suscripción ya está cancelada")
        return _suscripcion(doc)

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
        if metodo == "efectivo" and (pedido.get("entrega") or {}).get("tipo") == "domicilio":
            raise ValueError("El pago en efectivo solo es al recoger en el local")

        modo = modo_de(metodo)
        intento = int(pago.get("intentos", 0)) + 1
        cambios = {
            "metodo": metodo,
            "modo": modo,
            "estado": "pendiente",
            "referencia": referencia_de(pedido_id),
            "intentos": intento,
            "actualizado": _ahora(),
        }
        if metodo != pago.get("metodo"):
            cambios["proveedor_id"] = ""
            cambios["detalle"] = ""

        url = None
        try:
            if modo == "simulado":
                url = f"/pago/simulado?pedido={pedido_id}"
            elif metodo == "mercadopago":
                r = pagos.mp_crear_preferencia(
                    pedido, _lineas_con_nombre(pedido), usuario["email"], intento
                )
                cambios["proveedor_id"], url = r["proveedor_id"], r["url"]
            elif metodo == "paypal":
                r = pagos.paypal_crear_orden(pedido, intento)
                cambios["proveedor_id"], url = r["proveedor_id"], r["url"]
        except ErrorPago as e:
            raise ValueError(str(e))

        doc = relacional.actualizar_pedido(
            pedido_id,
            pago=cambios,
            condicion=lambda actual: actual["estado"] == "registrado"
            and actual["pago"]["estado"] not in PAGO_CERRADO,
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
        pedido = relacional.pedido(id)
        if pedido is None:
            raise ValueError(f"No existe el pedido {id}")
        actual = pedido["estado"]
        if estado not in ESTADOS_PEDIDO:
            raise ValueError("Estado inválido")
        if estado not in TRANSICIONES[actual]:
            raise ValueError(f"Un pedido '{actual}' no puede pasar a '{estado}'")

        if estado == "cancelado":
            return _pedido(_cancelar(pedido))

        pago = pedido["pago"]
        entrega = pedido.get("entrega") or {}
        cambios_pago = {}
        if actual == "registrado":
            # Pasar de registrado a pagado/entregado implica que ya se cobró
            if estado == "entregado" and pago["metodo"] != "efectivo":
                raise ValueError("Primero confirma el pago; solo efectivo se entrega sin pagar")
            cambios_pago = {
                "estado": "aprobado",
                "fecha_pago": _ahora(),
                "detalle": "Confirmado por la tienda",
                "actualizado": _ahora(),
            }

        # Al enviarlo a domicilio se genera la guía con la paquetería elegida
        cambios_entrega = None
        if estado == "enviado" and entrega.get("tipo") == "domicilio" and not entrega.get("guia"):
            cambios_entrega = _generar_guia(pedido)

        doc = relacional.actualizar_pedido(
            id,
            pedido={"estado": estado},
            pago=cambios_pago,
            entrega=cambios_entrega,
            condicion=lambda a: a["estado"] == actual,  # nadie lo movió mientras tanto
        )
        if doc is None:
            raise ValueError("Alguien más actualizó este pedido; recarga la página")
        eventos.publicar(
            eventos.PEDIDO_ESTADO,
            f"Pedido #{id} pasó a {estado}",
            pedido_id=id,
            usuario_id=doc["usuario_id"],
        )
        cliente = relacional.usuario(doc["usuario_id"])
        if cliente and cambios_pago and estado == "pagado":
            correos.pedido_confirmado(doc, cliente)
        if cliente and estado == "enviado" and (doc.get("entrega") or {}).get("tipo") == "domicilio":
            correos.pedido_enviado(doc, cliente)
        return _pedido(doc)

    @strawberry.mutation
    def generar_guia(self, info: Info, id: int) -> Pedido:
        """Genera (o regenera si falló) la guía de un pedido a domicilio sin
        cambiar su estado. Normalmente se hace sola al marcarlo enviado."""
        requiere_admin(info)
        pedido = relacional.pedido(id)
        if pedido is None:
            raise ValueError(f"No existe el pedido {id}")
        if pedido["estado"] not in ("pagado", "enviado"):
            raise ValueError("Solo se genera guía de pedidos pagados")
        doc = relacional.actualizar_pedido(id, entrega=_generar_guia(pedido))
        return _pedido(doc)

    @strawberry.mutation
    def procesar_recompras(self, info: Info) -> int:
        """Genera ya los pedidos de las suscripciones que vencen hoy o antes."""
        requiere_admin(info)
        return procesar_recompras()

    # ---------------- usuarios (solo admin) ----------------

    @strawberry.mutation
    def cambiar_rol_usuario(self, info: Info, id: int, rol: str) -> ClienteAdmin:
        admin = requiere_admin(info)
        if rol not in ("cliente", "admin"):
            raise ValueError("Rol inválido")
        if id == admin["_id"] and rol != "admin":
            raise ValueError("No puedes quitarte el rol de administrador a ti mismo")
        if relacional.actualizar_usuario(id, rol=rol) is None:
            raise ValueError(f"No existe el usuario {id}")
        return _cliente_admin_de(id)

    @strawberry.mutation
    def cambiar_activo_usuario(self, info: Info, id: int, activo: bool) -> ClienteAdmin:
        """Desactivar = ya no puede iniciar sesión y su token deja de servir.
        No se borra: sus pedidos y pagos se conservan (historial contable)."""
        admin = requiere_admin(info)
        if id == admin["_id"] and not activo:
            raise ValueError("No puedes desactivar tu propia cuenta")
        if relacional.actualizar_usuario(id, activo=activo) is None:
            raise ValueError(f"No existe el usuario {id}")
        return _cliente_admin_de(id)

    @strawberry.mutation
    def marcar_reembolsado(self, info: Info, id: int) -> Pedido:
        requiere_admin(info)
        doc = relacional.actualizar_pedido(
            id,
            pago={"estado": "reembolsado", "actualizado": _ahora()},
            condicion=lambda a: a["pago"]["estado"] == "por_reembolsar",
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

        usuario = relacional.usuario(nuevo["usuario_id"]) or {}
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
            yield _pedido(relacional.pedido(id))
            while True:
                evento = await cola.get()
                if evento.get("pedido_id") == id:
                    yield _pedido(relacional.pedido(id))

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
