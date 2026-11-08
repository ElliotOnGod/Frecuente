"""
database.py — conexión a MongoDB e inicialización de las DOS bases.

Desde esta entrega Frecuente usa persistencia políglota:

  MongoDB (aquí)       catálogo y membresías, documentos flexibles
  PostgreSQL           usuarios, pedidos, pagos, envíos, recompras y correos
                       (ver relacional.py y back/sql/)

Modelo de documentos en MongoDB:

    categorias  { _id, nombre, descripcion, imagen_url }
    productos   { _id, nombre, descripcion, precio, stock, imagen_url, imagenes: [..],
                  categoria_id, variante_nombre, variantes: [..], metodos: [..], peso_kg }
    imagenes    { _id: "<hex>", tipo, datos (binario), bytes, creada, admin_id }
    planes      { _id, nombre, descripcion, precio, incluye: [..], opciones: [..],
                  activo, orden }
    membresias  { _id, usuario_id, plan_id, estado, precio, creada, inicio, fin,
                  pago: { metodo, estado, modo, referencia, ... },
                  canjes: [ { dia, fecha, opcion, nota, admin_id } ] }
    contadores  { _id: "<colección>", valor }   <- ids numéricos consecutivos

Variantes: un café se vende "en grano", "molido para espresso", "para V60"...
sin duplicar el producto: es el MISMO producto (mismo precio y stock) y la
variante elegida se guarda en el renglón del pedido. `metodos` son los
métodos de preparación para los que sirve (filtro del catálogo).

Membresía: el cliente paga un plan mensual y cada día puede canjear UNA
vez su beneficio en el local. Los canjes van EMBEBIDOS (se leen siempre con
su membresía y son pocos: máximo ~31 por mes). El plan va por REFERENCIA
porque varias membresías comparten el mismo plan y su precio puede cambiar
(por eso la membresía guarda `precio`, el precio con el que se vendió).
membresias.usuario_id apunta a usuarios.id de PostgreSQL.

Los _id son enteros (1, 2, 3...) en lugar de ObjectId para que la API GraphQL
y el front usen ids numéricos.

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

import relacional
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

COLECCIONES = ["categorias", "productos", "planes", "membresias", "contadores", "imagenes"]
# Colecciones de entregas anteriores que ahora viven en PostgreSQL. Solo se
# leen una vez para migrarlas (relacional.inicializar) y luego no se usan.
COLECCIONES_MIGRADAS = ["usuarios", "pedidos"]

# Fotos de un producto: la primera es la principal (también queda en imagen_url)
MAX_IMAGENES = 6

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

# Métodos de preparación para el filtro del catálogo
METODOS_PREPARACION = {
    "espresso": "Espresso y latte",
    "filtro": "V60 / Chemex",
    "prensa": "Prensa francesa",
    "goteo": "Cafetera de goteo",
    "frio": "Bebidas frías",
    "batido": "Matcha batido",
}


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
            # Galería: URLs externas (https://…) o fotos subidas (/imagenes/<id>)
            "imagenes": {"bsonType": "array", "maxItems": MAX_IMAGENES, "items": {"bsonType": "string"}},
            "categoria_id": {"bsonType": "int"},
            "variante_nombre": {"bsonType": "string"},
            "variantes": {"bsonType": "array", "maxItems": 12, "items": {"bsonType": "string"}},
            "metodos": {"bsonType": "array", "items": {"enum": list(METODOS_PREPARACION)}},
            "peso_kg": {"bsonType": ["double", "int"], "minimum": 0},
        },
    },
    # Fotos que sube el admin. Se guardan en MongoDB (no en disco) para que
    # no se pierdan si el backend se publica en un servicio sin disco fijo.
    "imagenes": {
        "bsonType": "object",
        "required": ["_id", "tipo", "datos", "bytes"],
        "properties": {
            "_id": {"bsonType": "string", "pattern": "^[0-9a-f]{32}$"},
            "tipo": {"enum": ["image/jpeg", "image/png", "image/webp"]},
            "datos": {"bsonType": "binData"},
            "bytes": {"bsonType": "int", "minimum": 1},
            "creada": {"bsonType": "date"},
            "admin_id": {"bsonType": "int"},
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
    db.productos.create_index([("metodos", ASCENDING)])
    # Membresías: las de un usuario y las activas por fecha de fin
    db.membresias.create_index([("usuario_id", ASCENDING), ("creada", ASCENDING)])
    db.membresias.create_index([("estado", ASCENDING), ("fin", ASCENDING)])


def _actualizar_validadores() -> None:
    """Si la base se creó con una versión anterior (sin pagos), le pone los
    validadores nuevos sin borrar datos (collMod = ALTER TABLE de Mongo)."""
    for nombre, esquema in VALIDADORES.items():
        try:
            db.command("collMod", nombre, validator={"$jsonSchema": esquema})
        except Exception as e:
            # Por ejemplo, en una base de pruebas en memoria que no lo soporta
            print(f"[frecuente] No se actualizó el validador de {nombre}: {e}")


def init_db(force: bool = False) -> None:
    """Prepara MongoDB (catálogo, planes, membresías) y PostgreSQL (usuarios,
    pedidos...). Si ya hay datos solo agrega lo que falte, salvo force=True:
    entonces borra todo y vuelve a cargar los datos de ejemplo."""
    datos = json.loads(DATOS_PATH.read_text(encoding="utf-8"))

    if force:
        relacional.reiniciar()
        for nombre in COLECCIONES + COLECCIONES_MIGRADAS:
            db.drop_collection(nombre)

    if db.productos.estimated_document_count() == 0:
        _cargar_catalogo(datos)
    else:
        # Base de una entrega anterior: agrega colecciones y campos nuevos
        for nombre, esquema in VALIDADORES.items():
            if nombre not in db.list_collection_names():
                db.create_collection(nombre, validator={"$jsonSchema": esquema})
        _actualizar_validadores()
        _crear_indices()
        if db.planes.estimated_document_count() == 0:
            cargar_planes()
        completar_catalogo_de_ejemplo(datos)

    # PostgreSQL: crea las tablas y migra o carga usuarios y pedidos
    relacional.inicializar(db, datos, hashear_password)

    if db.membresias.estimated_document_count() == 0:
        cargar_membresias_demo()


def _cargar_catalogo(datos: dict) -> None:
    for nombre in COLECCIONES:
        db.drop_collection(nombre)
    for nombre, esquema in VALIDADORES.items():
        db.create_collection(nombre, validator={"$jsonSchema": esquema})
    _crear_indices()
    for coleccion in ("categorias", "productos"):
        docs = []
        for d in datos[coleccion]:
            d = dict(d)
            d["_id"] = d.pop("id")
            if "precio" in d:
                d["precio"] = float(d["precio"])
            if "peso_kg" in d:
                d["peso_kg"] = float(d["peso_kg"])
            docs.append(d)
        db[coleccion].insert_many(docs)
        db.contadores.insert_one({"_id": coleccion, "valor": max(d["_id"] for d in docs)})
    cargar_planes()
    print(f"[frecuente] Catálogo '{DB_NAME}' creado en MongoDB desde datos_ejemplo.json")


def completar_catalogo_de_ejemplo(datos: dict) -> None:
    """Base de una entrega anterior: a cada producto/categoría de ejemplo le
    pone lo que le falte (fotos, variantes, métodos, peso) SIN tocar lo que
    el admin ya editó."""
    cambios = 0
    for c in datos.get("categorias", []):
        if c.get("imagen_url"):
            r = db.categorias.update_one(
                {"_id": c["id"], "imagen_url": {"$in": ["", None]}},
                {"$set": {"imagen_url": c["imagen_url"]}},
            )
            cambios += r.modified_count
    for p in datos.get("productos", []):
        imagenes = p.get("imagenes") or ([p["imagen_url"]] if p.get("imagen_url") else [])
        if imagenes:
            r = db.productos.update_one(
                {
                    "_id": p["id"],
                    "imagen_url": {"$in": ["", None]},
                    "$or": [{"imagenes": {"$exists": False}}, {"imagenes": {"$size": 0}}],
                },
                {"$set": {"imagen_url": imagenes[0], "imagenes": imagenes}},
            )
            cambios += r.modified_count
        for campo in ("variante_nombre", "variantes", "metodos", "peso_kg"):
            if campo in p:
                valor = float(p[campo]) if campo == "peso_kg" else p[campo]
                r = db.productos.update_one({"_id": p["id"], campo: {"$exists": False}}, {"$set": {campo: valor}})
                cambios += r.modified_count
    if cambios:
        print(f"[frecuente] Se completaron {cambios} datos de ejemplo del catálogo")


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
    usuarios = relacional.usuarios_por_email()
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


if __name__ == "__main__":
    # python database.py  → borra y recrea todo con los datos de ejemplo
    init_db(force=True)
