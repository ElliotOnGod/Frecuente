"""
database.py — conexión a MongoDB e inicialización automática.

Modelo de documentos (equivale al DER del Reporte P6):

    categorias  { _id, nombre, descripcion, imagen_url }
    productos   { _id, nombre, descripcion, precio, stock, imagen_url, categoria_id }
    usuarios    { _id, nombre, email, telefono, rol, password_hash, creado }
    pedidos     { _id, usuario_id, fecha, estado, total,
                  items: [ { producto_id, cantidad, precio_unit } ],
                  pago:  { metodo, estado, modo, referencia, proveedor_id,
                           pago_id, detalle, intentos, fecha_pago, actualizado } }
    planes      { _id, nombre, descripcion, precio, incluye: [..], opciones: [..],
                  activo, orden }
    membresias  { _id, usuario_id, plan_id, estado, precio, creada, inicio, fin,
                  pago: { …igual que en pedidos… },
                  canjes: [ { dia, fecha, opcion, nota, admin_id } ] }
    contadores  { _id: "<colección>", valor }   ← ids numéricos consecutivos

Membresía: el cliente paga un plan mensual y cada día puede canjear UNA
vez su beneficio en el local. Los canjes van EMBEBIDOS (se leen siempre con
su membresía y son pocos: máximo ~31 por mes). El plan va por REFERENCIA
porque varias membresías comparten el mismo plan y su precio puede cambiar
(por eso la membresía guarda `precio`, el precio con el que se vendió).

El pago también va EMBEBIDO: un pedido tiene un solo cobro y siempre se
muestra junto con él (método, estado y referencia del proveedor).

Los PedidoItem van EMBEBIDOS dentro de su pedido: siempre se leen juntos y
no tienen vida propia, que es el caso típico para embeber en MongoDB.
Categoría→producto y usuario→pedido se dejan como REFERENCIA por id, porque
un producto se consulta solo y un usuario acumula muchos pedidos.

Los _id son enteros (1, 2, 3…) en lugar de ObjectId para que la API GraphQL
y el front sigan usando ids numéricos, igual que en el avance anterior.

Equipo: Jehu Uribe Bermudez (23100139),
        Jose Fernando Leon Lopez (23100146),
        Elliot Garcia Lopez (22300923)
Materia: Programacion Web II - CETI Colomos
"""

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient, ReturnDocument

from auth import hashear_password
from pagos import ESTADOS_PAGO, METODOS

BASE_DIR = Path(__file__).resolve().parent          # .../back
ROOT_DIR = BASE_DIR.parent                          # raíz del proyecto
DATOS_PATH = ROOT_DIR / "datos_ejemplo.json"

load_dotenv(BASE_DIR / ".env")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "frecuente")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tz_aware=False)
db = client[DB_NAME]

COLECCIONES = ["categorias", "productos", "usuarios", "pedidos", "planes", "membresias", "contadores"]

# Ciclo de vida de un pedido:
#   registrado ──(pago aprobado)──▶ pagado ──▶ enviado ──▶ entregado
#        └────────────── cancelado ◀──────────┘
# (efectivo al recoger: registrado ──▶ entregado, se cobra en el local)
ESTADOS_PEDIDO = ["registrado", "pagado", "enviado", "entregado", "cancelado"]

# Ciclo de vida de una membresía:
#   pendiente ──(pago aprobado)──▶ activa ──(pasa la fecha fin)──▶ vencida
#        └──────────────▶ cancelada ◀──────────┘
# "vencida" no se guarda: se calcula comparando `fin` con la fecha actual.
ESTADOS_MEMBRESIA = ["pendiente", "activa", "cancelada"]
DIAS_MEMBRESIA = 30


# ---------------------------------------------------------
# Validación de esquema ($jsonSchema): MongoDB rechaza documentos
# que no cumplan, igual que lo haría un NOT NULL o un CHECK en SQL.
# ---------------------------------------------------------
# Subdocumento de cobro: lo comparten pedidos y membresías
ESQUEMA_PAGO = {
    "bsonType": "object",
    "required": ["metodo", "estado"],
    "properties": {
        "metodo": {"enum": list(METODOS.keys())},
        "estado": {"enum": ESTADOS_PAGO},
        "modo": {"enum": ["simulado", "sandbox", "manual"]},
        "referencia": {"bsonType": "string"},
        "proveedor_id": {"bsonType": "string"},
        "pago_id": {"bsonType": "string"},
        "detalle": {"bsonType": "string"},
        "intentos": {"bsonType": "int", "minimum": 0},
        "fecha_pago": {"bsonType": ["date", "null"]},
        "actualizado": {"bsonType": "date"},
    },
}

VALIDADORES = {
    "categorias": {
        "bsonType": "object",
        "required": ["_id", "nombre"],
        "properties": {
            "_id": {"bsonType": "int"},
            "nombre": {"bsonType": "string", "minLength": 1},
            "descripcion": {"bsonType": "string"},
            "imagen_url": {"bsonType": "string"},
        },
    },
    "productos": {
        "bsonType": "object",
        "required": ["_id", "nombre", "precio", "stock", "categoria_id"],
        "properties": {
            "_id": {"bsonType": "int"},
            "nombre": {"bsonType": "string", "minLength": 1},
            "descripcion": {"bsonType": "string"},
            "precio": {"bsonType": ["double", "int"], "minimum": 0},
            "stock": {"bsonType": "int", "minimum": 0},
            "imagen_url": {"bsonType": "string"},
            "categoria_id": {"bsonType": "int"},
        },
    },
    "usuarios": {
        "bsonType": "object",
        "required": ["_id", "nombre", "email", "rol", "password_hash"],
        "properties": {
            "_id": {"bsonType": "int"},
            "nombre": {"bsonType": "string", "minLength": 1},
            "email": {"bsonType": "string", "pattern": "^.+@.+$"},
            "telefono": {"bsonType": "string"},
            "rol": {"enum": ["cliente", "admin"]},
            "password_hash": {"bsonType": "string"},
            "creado": {"bsonType": "date"},
        },
    },
    "pedidos": {
        "bsonType": "object",
        "required": ["_id", "usuario_id", "fecha", "estado", "total", "items"],
        "properties": {
            "_id": {"bsonType": "int"},
            "usuario_id": {"bsonType": "int"},
            "fecha": {"bsonType": "date"},
            "estado": {"enum": ESTADOS_PEDIDO},
            "total": {"bsonType": ["double", "int"], "minimum": 0},
            # Subdocumento del cobro (se agregó en la entrega de pagos).
            # Es opcional para que los pedidos viejos sigan siendo válidos.
            "pago": ESQUEMA_PAGO,
            "items": {
                "bsonType": "array",
                "minItems": 1,
                "items": {
                    "bsonType": "object",
                    "required": ["producto_id", "cantidad", "precio_unit"],
                    "properties": {
                        "producto_id": {"bsonType": "int"},
                        "cantidad": {"bsonType": "int", "minimum": 1},
                        "precio_unit": {"bsonType": ["double", "int"], "minimum": 0},
                    },
                },
            },
        },
    },
    "planes": {
        "bsonType": "object",
        "required": ["_id", "nombre", "precio", "activo"],
        "properties": {
            "_id": {"bsonType": "int"},
            "nombre": {"bsonType": "string", "minLength": 1},
            "descripcion": {"bsonType": "string"},
            "precio": {"bsonType": ["double", "int"], "minimum": 0},
            "incluye": {"bsonType": "array", "items": {"bsonType": "string"}},
            "opciones": {"bsonType": "array", "items": {"bsonType": "string"}},
            "activo": {"bsonType": "bool"},
            "orden": {"bsonType": "int"},
        },
    },
    "membresias": {
        "bsonType": "object",
        "required": ["_id", "usuario_id", "plan_id", "estado", "precio", "creada", "canjes"],
        "properties": {
            "_id": {"bsonType": "int"},
            "usuario_id": {"bsonType": "int"},
            "plan_id": {"bsonType": "int"},
            "estado": {"enum": ESTADOS_MEMBRESIA},
            "precio": {"bsonType": ["double", "int"], "minimum": 0},
            "creada": {"bsonType": "date"},
            "inicio": {"bsonType": ["date", "null"]},
            "fin": {"bsonType": ["date", "null"]},
            "pago": ESQUEMA_PAGO,
            "canjes": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["dia", "fecha", "opcion"],
                    "properties": {
                        "dia": {"bsonType": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                        "fecha": {"bsonType": "date"},
                        "opcion": {"bsonType": "string"},
                        "nota": {"bsonType": "string"},
                        "admin_id": {"bsonType": "int"},
                    },
                },
            },
        },
    },
}


def siguiente_id(coleccion: str) -> int:
    """Id consecutivo para una colección (como AUTO_INCREMENT).
    $inc es atómico: dos peticiones al mismo tiempo nunca reciben el mismo."""
    doc = db.contadores.find_one_and_update(
        {"_id": coleccion},
        {"$inc": {"valor": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc["valor"]


def a_dict(doc: dict | None) -> dict | None:
    """Documento de Mongo → dict listo para los tipos GraphQL
    (_id pasa a id y las fechas a texto)."""
    if doc is None:
        return None
    out = {}
    for k, v in doc.items():
        if k == "_id":
            k = "id"
        if k == "password_hash":
            continue  # nunca sale de la base
        if isinstance(v, datetime):
            v = v.isoformat(sep=" ", timespec="seconds")
        out[k] = v
    return out


def _crear_indices() -> None:
    """Índices: equivalen a las llaves foráneas indexadas y al UNIQUE de SQL.
    create_index no hace nada si el índice ya existe."""
    db.productos.create_index([("categoria_id", ASCENDING)])
    db.usuarios.create_index([("email", ASCENDING)], unique=True)
    db.pedidos.create_index([("usuario_id", ASCENDING), ("fecha", ASCENDING)])
    db.pedidos.create_index([("items.producto_id", ASCENDING)])
    # Para el panel de administración (filtros por estado y método)
    db.pedidos.create_index([("estado", ASCENDING), ("fecha", ASCENDING)])
    db.pedidos.create_index([("pago.metodo", ASCENDING)])
    # Membresías: las de un usuario y las activas por fecha de fin
    db.membresias.create_index([("usuario_id", ASCENDING), ("creada", ASCENDING)])
    db.membresias.create_index([("estado", ASCENDING), ("fin", ASCENDING)])


def _actualizar_validadores() -> None:
    """Si la base se creó con una versión anterior (sin pagos), le pone los
    validadores nuevos sin borrar datos (collMod = ALTER TABLE de Mongo)."""
    for nombre, esquema in VALIDADORES.items():
        try:
            db.command("collMod", nombre, validator={"$jsonSchema": esquema})
        except Exception:
            # Por ejemplo, en una base de pruebas en memoria que no lo soporta
            pass


def init_db(force: bool = False) -> None:
    """Crea colecciones, validadores e índices y carga datos_ejemplo.json.
    Si ya hay productos solo actualiza validadores e índices, salvo que
    force=True (entonces borra todo y vuelve a cargar los datos)."""
    if db.productos.estimated_document_count() > 0 and not force:
        # Base de una entrega anterior: se agregan las colecciones nuevas
        # (planes y membresías) sin tocar lo que ya había.
        for nombre, esquema in VALIDADORES.items():
            if nombre not in db.list_collection_names():
                db.create_collection(nombre, validator={"$jsonSchema": esquema})
        _actualizar_validadores()
        _crear_indices()
        if db.planes.estimated_document_count() == 0:
            cargar_planes()
            cargar_membresias_demo()
            print("[frecuente] Se agregaron los planes de membresía a la base existente")
        return

    for nombre in COLECCIONES:
        db.drop_collection(nombre)

    for nombre, esquema in VALIDADORES.items():
        db.create_collection(nombre, validator={"$jsonSchema": esquema})

    _crear_indices()

    datos = json.loads(DATOS_PATH.read_text(encoding="utf-8"))
    for coleccion in ("categorias", "productos", "usuarios"):
        docs = []
        for d in datos[coleccion]:
            d = dict(d)
            d["_id"] = d.pop("id")
            if "precio" in d:
                d["precio"] = float(d["precio"])
            if "password" in d:
                # El JSON trae la contraseña demo en texto; aquí se guarda el hash
                d["password_hash"] = hashear_password(d.pop("password"))
                d["email"] = d["email"].lower()
                d["creado"] = datetime.now().replace(microsecond=0)
            docs.append(d)
        db[coleccion].insert_many(docs)
        db.contadores.insert_one({"_id": coleccion, "valor": max(d["_id"] for d in docs)})

    db.contadores.insert_one({"_id": "pedidos", "valor": 0})
    cargar_pedidos_demo()
    cargar_planes()
    cargar_membresias_demo()
    print(f"[frecuente] Base '{DB_NAME}' creada en MongoDB desde datos_ejemplo.json")


def cargar_planes() -> None:
    """Planes de membresía desde datos_ejemplo.json."""
    datos = json.loads(DATOS_PATH.read_text(encoding="utf-8"))
    docs = []
    for i, d in enumerate(datos.get("planes", []), start=1):
        d = dict(d)
        d["_id"] = d.pop("id")
        d["precio"] = float(d["precio"])
        d.setdefault("activo", True)
        d.setdefault("orden", i)
        docs.append(d)
    if docs:
        db.planes.insert_many(docs)
        db.contadores.update_one(
            {"_id": "planes"}, {"$set": {"valor": max(d["_id"] for d in docs)}}, upsert=True
        )


def cargar_membresias_demo() -> None:
    """Algunas membresías de ejemplo con canjes de días pasados (ninguno de
    hoy, para que en la demo se pueda canjear en vivo)."""
    from datetime import timedelta

    from pagos import modo_de, referencia_membresia

    planes = {p["_id"]: p for p in db.planes.find()}
    usuarios = {u["email"]: u["_id"] for u in db.usuarios.find({"rol": "cliente"})}
    if not planes or not usuarios:
        return

    ahora = datetime.now().replace(microsecond=0)
    hoy = ahora.replace(hour=0, minute=0, second=0)

    # (correo, plan, estado, días desde que inició, método, días con canje)
    ejemplos = [
        ("demo@frecuente.mx", 2, "activa", 12, "mercadopago", [1, 2, 3, 5, 6, 8, 9, 11]),
        ("mariana@frecuente.mx", 1, "activa", 4, "paypal", [1, 2, 3]),
        ("compras@andares.mx", 3, "activa", 20, "transferencia", [1, 2, 4, 5, 6, 7, 9, 12, 13, 15]),
        ("carlos@frecuente.mx", 1, "activa", 40, "mercadopago", [31, 33, 35, 38]),  # ya venció
        ("carlos@frecuente.mx", 2, "pendiente", 0, "transferencia", []),
    ]
    for correo, plan_id, estado, dias, metodo, dias_canje in ejemplos:
        if correo not in usuarios or plan_id not in planes:
            continue
        plan = planes[plan_id]
        _id = siguiente_id("membresias")
        inicio = (hoy - timedelta(days=dias)).replace(hour=9) if estado == "activa" else None
        opciones = plan.get("opciones") or ["Beneficio del día"]
        canjes = [
            {
                "dia": (hoy - timedelta(days=d)).strftime("%Y-%m-%d"),
                "fecha": (hoy - timedelta(days=d)).replace(hour=8 + d % 9, minute=(d * 7) % 60),
                "opcion": opciones[d % len(opciones)],
                "nota": "",
                "admin_id": 2,
            }
            for d in sorted(dias_canje, reverse=True)
        ]
        db.membresias.insert_one(
            {
                "_id": _id,
                "usuario_id": usuarios[correo],
                "plan_id": plan_id,
                "estado": estado,
                "precio": float(plan["precio"]),
                "creada": inicio or ahora - timedelta(hours=3),
                "inicio": inicio,
                "fin": inicio + timedelta(days=DIAS_MEMBRESIA) if inicio else None,
                "pago": {
                    "metodo": metodo,
                    "estado": "aprobado" if estado == "activa" else "pendiente",
                    "modo": modo_de(metodo),
                    "referencia": referencia_membresia(_id),
                    "proveedor_id": "",
                    "pago_id": f"DEMO-M{_id}" if estado == "activa" else "",
                    "detalle": "Membresía de ejemplo",
                    "intentos": 1,
                    "fecha_pago": inicio,
                    "actualizado": inicio or ahora,
                },
                "canjes": canjes,
            }
        )


def cargar_pedidos_demo(cantidad: int = 36, dias: int = 30) -> None:
    """Historial de pedidos de ejemplo repartidos en los últimos `dias`,
    para que el panel de administración tenga algo que mostrar en la demo.

    Son ventas "pasadas": no descuentan stock. Se generan con una semilla
    fija, así siempre salen los mismos pedidos (pero con fechas recientes)."""
    import random
    from datetime import timedelta

    from pagos import modo_de, referencia_de

    azar = random.Random(2026)
    productos = list(db.productos.find())
    clientes = [u["_id"] for u in db.usuarios.find({"rol": "cliente"})]
    if not productos or not clientes:
        return

    metodos = ["mercadopago"] * 5 + ["paypal"] * 2 + ["transferencia"] * 2 + ["efectivo"]
    ahora = datetime.now().replace(microsecond=0)

    # Primero las fechas, ordenadas, para que los ids queden en orden cronológico
    fechas = []
    for _ in range(cantidad):
        dias_atras = azar.randint(0, dias - 1)
        fecha = (ahora - timedelta(days=dias_atras)).replace(
            hour=azar.randint(8, 20), minute=azar.randint(0, 59), second=0
        )
        if fecha > ahora:
            fecha = ahora - timedelta(minutes=azar.randint(5, 120))
        fechas.append(fecha)
    fechas.sort()

    # Los últimos pedidos se fijan a mano para que la demo tenga de todo:
    # pagos pendientes, uno rechazado y uno cancelado por reembolsar.
    especiales = {
        cantidad - 1: ("transferencia", "registrado", "pendiente", 2),
        cantidad - 2: ("mercadopago", "registrado", "rechazado", 5),
        cantidad - 3: ("efectivo", "registrado", "pendiente", 9),
        cantidad - 4: ("paypal", "cancelado", "por_reembolsar", 20),
    }

    for indice, fecha in enumerate(fechas):
        if indice in especiales:
            fecha = ahora - timedelta(hours=especiales[indice][3])
        dias_atras = (ahora.date() - fecha.date()).days

        elegidos = azar.sample(productos, k=azar.randint(1, 3))
        items = [
            {"producto_id": p["_id"], "cantidad": azar.randint(1, 3), "precio_unit": float(p["precio"])}
            for p in elegidos
        ]
        total = round(sum(i["cantidad"] * i["precio_unit"] for i in items), 2)
        metodo = azar.choice(metodos)

        # Los pedidos viejos ya avanzaron; los de los últimos días siguen en proceso
        if dias_atras >= 5:
            estado = azar.choice(["entregado"] * 6 + ["enviado"] + ["cancelado"])
        elif dias_atras >= 2:
            estado = azar.choice(["pagado", "enviado", "entregado", "registrado"])
        else:
            estado = azar.choice(["registrado", "pagado", "pagado"])

        if metodo == "efectivo" and estado in ("pagado", "enviado"):
            # En efectivo no hay envío: se cobra y se entrega en el local
            estado = "entregado" if dias_atras >= 2 else "registrado"

        if estado == "cancelado":
            estado_pago = azar.choice(["rechazado", "pendiente"])
        elif estado == "registrado":
            estado_pago = "pendiente" if metodo != "mercadopago" else azar.choice(["pendiente", "rechazado"])
        else:
            estado_pago = "aprobado"

        if indice in especiales:
            metodo, estado, estado_pago, _ = especiales[indice]

        _id = siguiente_id("pedidos")
        db.pedidos.insert_one(
            {
                "_id": _id,
                "usuario_id": azar.choice(clientes),
                "fecha": fecha,
                "estado": estado,
                "total": total,
                "items": items,
                "pago": {
                    "metodo": metodo,
                    "estado": estado_pago,
                    "modo": modo_de(metodo),
                    "referencia": referencia_de(_id),
                    "proveedor_id": "",
                    "pago_id": f"DEMO-{_id}" if estado_pago in ("aprobado", "por_reembolsar") else "",
                    "detalle": "Pedido de ejemplo",
                    "intentos": 1,
                    "fecha_pago": fecha + timedelta(minutes=3)
                    if estado_pago in ("aprobado", "por_reembolsar")
                    else None,
                    "actualizado": fecha,
                },
            }
        )


if __name__ == "__main__":
    # python database.py  → borra y recrea todo con los datos de ejemplo
    init_db(force=True)
