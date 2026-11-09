"""
relacional.py — PostgreSQL: la parte TRANSACCIONAL de Frecuente.

¿Por qué dos bases de datos? (persistencia políglota)

  PostgreSQL  → usuarios, pedidos, renglones, pagos, envíos, suscripciones
                (recompra) y bitácora de correos. Son datos con forma fija,
                relaciones entre sí (llaves foráneas) y operaciones que tocan
                varias tablas a la vez: un pedido nuevo inserta en pedidos,
                pedido_items, pagos y envios, y debe quedar TODO o NADA
                (transacción ACID).
  MongoDB     → catálogo (categorías y productos con galería, variantes y
                métodos de preparación), fotos, planes y membresías con sus
                canjes embebidos. Documentos flexibles que se leen completos.

Las dos se unen por id: pedido_items.producto_id apunta a un producto de
MongoDB y membresias.usuario_id (Mongo) apunta a usuarios.id (Postgres).

Las funciones de aquí regresan "documentos" con la MISMA forma que tenían
cuando todo estaba en MongoDB ({"_id": 12, "items": [...], "pago": {...}}),
así schema.py y pagos.py casi no cambiaron al migrar.

Migraciones: cada archivo de back/sql/ se aplica una sola vez, en orden,
y queda anotado en la tabla `migraciones` (como Flyway o Alembic, en chico).

Equipo: Jehu Uribe Bermudez (23100139),
        Jose Fernando Leon Lopez (23100146),
        Elliot Garcia Lopez (22300923)
Materia: Programacion Web II - CETI Colomos
"""

import atexit
import os
import random
import threading
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from psycopg import errors, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Neon / Render / Supabase dan una URL así:
#   postgresql://usuario:contraseña@host/frecuente?sslmode=require
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or "postgresql://postgres@localhost:5432/frecuente"
MIGRACIONES_DIR = BASE_DIR / "sql"

# Pool de conexiones: abrir una conexión a Postgres cuesta (TLS, login…),
# así que se reutilizan. Los resolvers síncronos de Strawberry corren en
# varios hilos y cada uno toma una conexión prestada del pool.
# prepare_threshold=None: sin "prepared statements", porque el pooler de
# Neon (PgBouncer en modo transacción) no siempre los soporta.
pool = ConnectionPool(
    DATABASE_URL,
    min_size=1,
    max_size=int(os.getenv("PG_POOL_MAX", "10")),
    kwargs={"row_factory": dict_row, "prepare_threshold": None},
    # Neon apaga la base tras unos minutos sin uso y cierra las conexiones:
    # antes de prestar una se revisa que siga viva (si no, se abre otra), y
    # las que llevan 4 minutos sin usarse se cierran solas.
    check=ConnectionPool.check_connection,
    max_idle=240,
    open=False,
    timeout=15,
)
_abierto = False
_candado_apertura = threading.Lock()


@atexit.register
def _cerrar_al_salir() -> None:
    if _abierto and not pool.closed:
        pool.close()

ESTADOS_ABIERTOS = ("registrado", "pagado")


class CorreoDuplicado(Exception):
    """Ya existe una cuenta con ese correo (UNIQUE de la tabla usuarios)."""


def abrir() -> None:
    global _abierto
    with _candado_apertura:
        if not _abierto:
            pool.open(wait=True, timeout=20)
            _abierto = True


@contextmanager
def transaccion():
    """Una conexión del pool dentro de una transacción.
    Si el bloque termina bien → COMMIT; si lanza una excepción → ROLLBACK."""
    abrir()
    with pool.connection() as con:
        yield con


def _f(v) -> float:
    return float(v) if isinstance(v, Decimal) else (float(v) if v is not None else 0.0)


# =========================================================
# Migraciones
# =========================================================

def migrar() -> list[str]:
    """Aplica los .sql de back/sql/ que falten. El candado de asesoría
    (pg_advisory_xact_lock) evita que dos procesos migren al mismo tiempo."""
    aplicadas = []
    with transaccion() as con:
        con.execute("SELECT pg_advisory_xact_lock(7001)")
        con.execute(
            "CREATE TABLE IF NOT EXISTS migraciones ("
            " version TEXT PRIMARY KEY, aplicada TIMESTAMP(0) NOT NULL DEFAULT LOCALTIMESTAMP(0))"
        )
        hechas = {r["version"] for r in con.execute("SELECT version FROM migraciones")}
        for archivo in sorted(MIGRACIONES_DIR.glob("*.sql")):
            if archivo.stem in hechas:
                continue
            con.execute(archivo.read_text(encoding="utf-8"))
            con.execute("INSERT INTO migraciones (version) VALUES (%s)", (archivo.stem,))
            aplicadas.append(archivo.stem)
    if aplicadas:
        print(f"[frecuente] PostgreSQL: migraciones aplicadas {', '.join(aplicadas)}")
    return aplicadas


TABLAS = ["correos", "envios", "pagos", "pedido_items", "pedidos", "suscripcion_items", "suscripciones", "usuarios", "migraciones"]


def reiniciar() -> None:
    """Borra las tablas de Frecuente (solo para `python database.py` y pruebas)."""
    with transaccion() as con:
        for tabla in TABLAS:
            con.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(tabla)))


def _ajustar_secuencias(con) -> None:
    """Después de insertar con ids fijos, el SERIAL debe seguir desde el mayor."""
    for tabla in ("usuarios", "pedidos", "suscripciones"):
        con.execute(
            sql.SQL(
                "SELECT setval(pg_get_serial_sequence({t}, 'id'), COALESCE((SELECT max(id) FROM {i}), 0) + 1, false)"
            ).format(t=sql.Literal(tabla), i=sql.Identifier(tabla))
        )


# =========================================================
# Usuarios
# =========================================================

_COLS_USUARIO = "id, nombre, email, telefono, rol, activo, password_hash, creado"


def _usuario_doc(fila: dict | None) -> dict | None:
    if fila is None:
        return None
    d = dict(fila)
    d["_id"] = d.pop("id")
    return d


def usuario(usuario_id: int) -> dict | None:
    with transaccion() as con:
        return _usuario_doc(
            con.execute(f"SELECT {_COLS_USUARIO} FROM usuarios WHERE id = %s", (usuario_id,)).fetchone()
        )


def usuario_por_email(email: str) -> dict | None:
    with transaccion() as con:
        return _usuario_doc(
            con.execute(f"SELECT {_COLS_USUARIO} FROM usuarios WHERE email = %s", (email,)).fetchone()
        )


def existe_email(email: str) -> bool:
    with transaccion() as con:
        return con.execute("SELECT 1 FROM usuarios WHERE email = %s", (email,)).fetchone() is not None


def crear_usuario(nombre: str, email: str, telefono: str, password_hash: str, rol: str = "cliente") -> dict:
    try:
        with transaccion() as con:
            fila = con.execute(
                f"INSERT INTO usuarios (nombre, email, telefono, rol, password_hash, creado)"
                f" VALUES (%s, %s, %s, %s, %s, LOCALTIMESTAMP(0)) RETURNING {_COLS_USUARIO}",
                (nombre, email, telefono, rol, password_hash),
            ).fetchone()
            return _usuario_doc(fila)
    except errors.UniqueViolation:
        # Dos registros con el mismo correo al mismo tiempo: el UNIQUE decide
        raise CorreoDuplicado(email)


def usuarios_por_ids(ids) -> dict[int, dict]:
    ids = list({int(i) for i in ids if i is not None})
    if not ids:
        return {}
    with transaccion() as con:
        filas = con.execute(f"SELECT {_COLS_USUARIO} FROM usuarios WHERE id = ANY(%s)", (ids,)).fetchall()
    return {f["id"]: _usuario_doc(f) for f in filas}


def nombre_de(usuario_id: int, defecto: str = "Cliente") -> str:
    u = usuarios_por_ids([usuario_id]).get(usuario_id)
    return u["nombre"] if u else defecto


def usuarios_por_email() -> dict[str, int]:
    with transaccion() as con:
        return {f["email"]: f["id"] for f in con.execute("SELECT id, email FROM usuarios WHERE rol = 'cliente'")}


def ids_que_coinciden(texto: str) -> list[int]:
    """Usuarios cuyo nombre o correo contiene el texto (sin importar mayúsculas)."""
    patron = f"%{texto.replace('%', '').replace('_', '')}%"
    with transaccion() as con:
        return [
            f["id"]
            for f in con.execute("SELECT id FROM usuarios WHERE nombre ILIKE %s OR email ILIKE %s", (patron, patron))
        ]


def contar_clientes() -> int:
    with transaccion() as con:
        return con.execute("SELECT count(*) AS n FROM usuarios WHERE rol = 'cliente'").fetchone()["n"]


def clientes_con_estadisticas(buscar: str | None, incluir_admins: bool) -> list[dict]:
    """Usuarios con cuántos pedidos tienen, cuánto han gastado (solo ventas
    pagadas) y su última compra. Un solo SELECT con LEFT JOIN + GROUP BY."""
    condiciones = [] if incluir_admins else ["u.rol = 'cliente'"]
    params: list = []
    if buscar and buscar.strip():
        patron = f"%{buscar.strip()}%"
        condiciones.append("(u.nombre ILIKE %s OR u.email ILIKE %s OR u.telefono ILIKE %s)")
        params += [patron, patron, patron]
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    consulta = f"""
        SELECT u.id, u.nombre, u.email, u.telefono, u.rol, u.activo, u.creado,
               count(p.id)                                   AS pedidos,
               max(p.fecha)                                  AS ultima,
               COALESCE(sum(p.total) FILTER (
                   WHERE g.estado = 'aprobado' AND p.estado <> 'cancelado'), 0) AS gastado
        FROM usuarios u
        LEFT JOIN pedidos p ON p.usuario_id = u.id
        LEFT JOIN pagos   g ON g.pedido_id  = p.id
        {where}
        GROUP BY u.id
        ORDER BY gastado DESC, u.nombre
    """
    with transaccion() as con:
        filas = con.execute(consulta, params).fetchall()
    return [{**f, "gastado": _f(f["gastado"])} for f in filas]


def actualizar_usuario(usuario_id: int, **campos) -> dict | None:
    permitidos = {"rol", "activo", "nombre", "telefono"}
    campos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos:
        return usuario(usuario_id)
    asignaciones = sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in campos)
    with transaccion() as con:
        fila = con.execute(
            sql.SQL("UPDATE usuarios SET {} WHERE id = %s RETURNING " + _COLS_USUARIO).format(asignaciones),
            [*campos.values(), usuario_id],
        ).fetchone()
    return _usuario_doc(fila)


def contar_admins_activos() -> int:
    with transaccion() as con:
        return con.execute("SELECT count(*) AS n FROM usuarios WHERE rol = 'admin' AND activo").fetchone()["n"]


# =========================================================
# Pedidos (con sus renglones, pago y envío)
# =========================================================

_SQL_PEDIDOS = """
    SELECT p.id, p.usuario_id, p.suscripcion_id, p.fecha, p.estado, p.subtotal, p.envio, p.total,
           g.metodo, g.estado AS pago_estado, g.modo, g.referencia, g.proveedor_id, g.pago_id,
           g.detalle, g.intentos, g.fecha_pago, g.actualizado
    FROM pedidos p
    JOIN pagos g ON g.pedido_id = p.id
"""


def _armar_pedidos(con, filas: list[dict]) -> list[dict]:
    """Filas de pedidos+pagos → documentos completos. Los renglones y los
    envíos se traen en DOS consultas para todos los pedidos juntos (no una
    por pedido), para no caer en el problema N+1."""
    ids = [f["id"] for f in filas]
    items: dict[int, list] = defaultdict(list)
    envios: dict[int, dict] = {}
    if ids:
        for it in con.execute(
            "SELECT pedido_id, producto_id, nombre, variante, cantidad, precio_unit"
            " FROM pedido_items WHERE pedido_id = ANY(%s) ORDER BY id",
            (ids,),
        ):
            items[it["pedido_id"]].append(
                {
                    "producto_id": it["producto_id"],
                    "nombre": it["nombre"],
                    "variante": it["variante"],
                    "cantidad": it["cantidad"],
                    "precio_unit": _f(it["precio_unit"]),
                }
            )
        for e in con.execute("SELECT * FROM envios WHERE pedido_id = ANY(%s)", (ids,)):
            e = dict(e)
            pid = e.pop("pedido_id")
            envios[pid] = {**e, "costo": _f(e["costo"])}
    docs = []
    for f in filas:
        docs.append(
            {
                "_id": f["id"],
                "usuario_id": f["usuario_id"],
                "suscripcion_id": f["suscripcion_id"],
                "fecha": f["fecha"],
                "estado": f["estado"],
                "subtotal": _f(f["subtotal"]),
                "envio": _f(f["envio"]),
                "total": _f(f["total"]),
                "items": items[f["id"]],
                "pago": {
                    "metodo": f["metodo"],
                    "estado": f["pago_estado"],
                    "modo": f["modo"],
                    "referencia": f["referencia"],
                    "proveedor_id": f["proveedor_id"],
                    "pago_id": f["pago_id"],
                    "detalle": f["detalle"],
                    "intentos": f["intentos"],
                    "fecha_pago": f["fecha_pago"],
                    "actualizado": f["actualizado"],
                },
                "entrega": envios.get(f["id"]),
            }
        )
    return docs


def _pedido_en(con, pedido_id: int, usuario_id: int | None = None) -> dict | None:
    consulta = _SQL_PEDIDOS + " WHERE p.id = %s"
    params: list = [pedido_id]
    if usuario_id is not None:
        consulta += " AND p.usuario_id = %s"
        params.append(usuario_id)
    filas = con.execute(consulta, params).fetchall()
    docs = _armar_pedidos(con, filas)
    return docs[0] if docs else None


def pedido(pedido_id: int, usuario_id: int | None = None) -> dict | None:
    """El pedido; si se da usuario_id, solo si es de ese usuario."""
    with transaccion() as con:
        return _pedido_en(con, pedido_id, usuario_id)


def pedidos_de_usuario(usuario_id: int) -> list[dict]:
    with transaccion() as con:
        filas = con.execute(_SQL_PEDIDOS + " WHERE p.usuario_id = %s ORDER BY p.id DESC", (usuario_id,)).fetchall()
        return _armar_pedidos(con, filas)


def pedidos_de_suscripcion(suscripcion_id: int) -> list[dict]:
    with transaccion() as con:
        filas = con.execute(
            _SQL_PEDIDOS + " WHERE p.suscripcion_id = %s ORDER BY p.id DESC", (suscripcion_id,)
        ).fetchall()
        return _armar_pedidos(con, filas)


def insertar_pedido(
    con,
    *,
    usuario_id: int,
    fecha: datetime,
    estado: str,
    lineas: list[dict],
    envio: float,
    pago: dict,
    entrega: dict | None,
    suscripcion_id: int | None = None,
    pedido_id: int | None = None,
) -> int:
    """Inserta pedido + renglones + pago + envío con la conexión dada (dentro
    de la transacción de quien llama).
    Sin `pago["referencia"]` se usa FREC-000012 con el id que asigne Postgres."""
    from pagos import referencia_de

    subtotal = round(sum(l["cantidad"] * l["precio_unit"] for l in lineas), 2)
    total = round(subtotal + envio, 2)
    if pedido_id is None:
        fila = con.execute(
            "INSERT INTO pedidos (usuario_id, suscripcion_id, fecha, estado, subtotal, envio, total)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (usuario_id, suscripcion_id, fecha, estado, subtotal, envio, total),
        ).fetchone()
        pedido_id = fila["id"]
    else:
        con.execute(
            "INSERT INTO pedidos (id, usuario_id, suscripcion_id, fecha, estado, subtotal, envio, total)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (pedido_id, usuario_id, suscripcion_id, fecha, estado, subtotal, envio, total),
        )
    with con.cursor() as cur:
        cur.executemany(
            "INSERT INTO pedido_items (pedido_id, producto_id, nombre, variante, cantidad, precio_unit)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            [
                (pedido_id, l["producto_id"], l.get("nombre") or f"Producto {l['producto_id']}",
                 l.get("variante", ""), l["cantidad"], l["precio_unit"])
                for l in lineas
            ],
        )
    con.execute(
        "INSERT INTO pagos (pedido_id, metodo, estado, modo, referencia, proveedor_id, pago_id, detalle,"
        " intentos, fecha_pago, actualizado) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            pedido_id,
            pago["metodo"],
            pago.get("estado", "pendiente"),
            pago.get("modo", "manual"),
            pago.get("referencia") or referencia_de(pedido_id),
            pago.get("proveedor_id", ""),
            pago.get("pago_id", ""),
            pago.get("detalle", ""),
            pago.get("intentos", 0),
            pago.get("fecha_pago"),
            pago.get("actualizado") or fecha,
        ),
    )
    if entrega:
        columnas = [c for c in _COLS_ENVIO if c in entrega]
        con.execute(
            sql.SQL("INSERT INTO envios (pedido_id, {}) VALUES (%s, {})").format(
                sql.SQL(", ").join(map(sql.Identifier, columnas)),
                sql.SQL(", ").join(sql.Placeholder() * len(columnas)),
            ),
            [pedido_id, *[entrega[c] for c in columnas]],
        )
    return pedido_id


_COLS_PEDIDO = {"estado"}
_COLS_PAGO = {"metodo", "estado", "modo", "referencia", "proveedor_id", "pago_id", "detalle", "intentos", "fecha_pago", "actualizado"}
_COLS_ENVIO = [
    "tipo", "nombre", "telefono", "calle", "numero", "colonia", "ciudad", "estado", "cp", "referencias",
    "paqueteria", "servicio", "descripcion", "dias", "costo", "modo", "guia", "rastreo_url", "etiqueta_url",
]


def _set(con, tabla: str, llave: str, valor: int, campos: dict, permitidas) -> None:
    campos = {k: v for k, v in campos.items() if k in permitidas}
    if not campos:
        return
    asignaciones = sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in campos)
    con.execute(
        sql.SQL("UPDATE {} SET {} WHERE {} = %s").format(sql.Identifier(tabla), asignaciones, sql.Identifier(llave)),
        [*campos.values(), valor],
    )


def actualizar_pedido(
    pedido_id: int,
    *,
    pedido: dict | None = None,
    pago: dict | None = None,
    entrega: dict | None = None,
    condicion=None,
    calcular=None,
) -> dict | None:
    """Cambio condicional de un pedido (equivale al find_one_and_update de Mongo).

    1. SELECT … FOR UPDATE bloquea el renglón del pedido: si otra petición
       quiere tocar el mismo pedido, espera a que esta termine.
    2. `condicion(doc)` revisa el estado YA bloqueado (ej. "sigue pendiente").
       Si no se cumple, no cambia nada y regresa None.
       `calcular(doc)` es la versión flexible: con el estado bloqueado
       decide los cambios y regresa (pedido, pago, entrega) o None.
    3. Actualiza pedidos, pagos y envios en la MISMA transacción."""
    with transaccion() as con:
        if con.execute("SELECT id FROM pedidos WHERE id = %s FOR UPDATE", (pedido_id,)).fetchone() is None:
            return None
        actual = _pedido_en(con, pedido_id)
        if condicion is not None and not condicion(actual):
            return None
        if calcular is not None:
            decision = calcular(actual)
            if decision is None:
                return None
            pedido, pago, entrega = decision
        _set(con, "pedidos", "id", pedido_id, pedido or {}, _COLS_PEDIDO)
        _set(con, "pagos", "pedido_id", pedido_id, pago or {}, _COLS_PAGO)
        if entrega:
            _set(con, "envios", "pedido_id", pedido_id, entrega, set(_COLS_ENVIO))
        return _pedido_en(con, pedido_id)


def filtro_pedidos_admin(estado, metodo, buscar) -> tuple[str, list]:
    condiciones, params = [], []
    if estado:
        if estado == "por_cobrar":
            condiciones.append("p.estado = 'registrado'")
        elif estado == "por_reembolsar":
            condiciones.append("g.estado = 'por_reembolsar'")
        elif estado == "recompra":
            condiciones.append("p.suscripcion_id IS NOT NULL")
        else:
            condiciones.append("p.estado = %s")
            params.append(estado)
    if metodo:
        condiciones.append("g.metodo = %s")
        params.append(metodo)
    if buscar and buscar.strip():
        import re

        texto = buscar.strip()
        numero = re.sub(r"(?i)^(frec-)?#?0*", "", texto)
        if numero.isdigit():
            condiciones.append("p.id = %s")
            params.append(int(numero))
        else:
            patron = f"%{texto}%"
            condiciones.append(
                "p.usuario_id IN (SELECT id FROM usuarios WHERE nombre ILIKE %s OR email ILIKE %s)"
            )
            params += [patron, patron]
    return (" WHERE " + " AND ".join(condiciones)) if condiciones else "", params


def pedidos_admin(estado, metodo, buscar, limite: int, salto: int) -> tuple[int, list[dict]]:
    where, params = filtro_pedidos_admin(estado, metodo, buscar)
    with transaccion() as con:
        total = con.execute(
            "SELECT count(*) AS n FROM pedidos p JOIN pagos g ON g.pedido_id = p.id" + where, params
        ).fetchone()["n"]
        filas = con.execute(
            _SQL_PEDIDOS + where + " ORDER BY p.id DESC LIMIT %s OFFSET %s", [*params, limite, salto]
        ).fetchall()
        return total, _armar_pedidos(con, filas)


def producto_vendido(producto_id: int) -> bool:
    with transaccion() as con:
        return con.execute(
            "SELECT 1 FROM pedido_items WHERE producto_id = %s LIMIT 1", (producto_id,)
        ).fetchone() is not None


# =========================================================
# Panel: resumen de ventas (todo con SQL de agregación)
# =========================================================

_VENTA = "g.estado = 'aprobado' AND p.estado <> 'cancelado'"


def resumen_ventas(desde: datetime, dias: int) -> dict:
    desde_anterior = desde - timedelta(days=dias)
    with transaccion() as con:
        actual = con.execute(
            f"""SELECT COALESCE(sum(p.total), 0) AS total, count(*) AS n,
                       count(DISTINCT p.usuario_id) AS clientes
                FROM pedidos p JOIN pagos g ON g.pedido_id = p.id
                WHERE p.fecha >= %s AND {_VENTA}""",
            (desde,),
        ).fetchone()
        anterior = con.execute(
            f"""SELECT COALESCE(sum(p.total), 0) AS total
                FROM pedidos p JOIN pagos g ON g.pedido_id = p.id
                WHERE p.fecha >= %s AND p.fecha < %s AND {_VENTA}""",
            (desde_anterior, desde),
        ).fetchone()
        # generate_series crea un renglón por día aunque ese día no haya ventas
        por_dia = con.execute(
            f"""SELECT to_char(d.dia, 'YYYY-MM-DD') AS fecha,
                       COALESCE(sum(p.total), 0) AS total, count(p.id) AS pedidos
                FROM generate_series(%s::date, %s::date + (%s - 1), interval '1 day') AS d(dia)
                LEFT JOIN (pedidos p JOIN pagos g ON g.pedido_id = p.id AND {_VENTA})
                       ON p.fecha::date = d.dia::date
                GROUP BY d.dia ORDER BY d.dia""",
            (desde, desde, dias),
        ).fetchall()
        por_metodo = {
            f["metodo"]: f
            for f in con.execute(
                f"""SELECT g.metodo, COALESCE(sum(p.total), 0) AS total, count(*) AS pedidos
                    FROM pedidos p JOIN pagos g ON g.pedido_id = p.id
                    WHERE p.fecha >= %s AND {_VENTA} GROUP BY g.metodo""",
                (desde,),
            )
        }
        por_estado = {
            f["estado"]: f["n"]
            for f in con.execute(
                "SELECT estado, count(*) AS n FROM pedidos WHERE fecha >= %s GROUP BY estado", (desde,)
            )
        }
        top = con.execute(
            f"""SELECT i.producto_id, max(i.nombre) AS nombre, sum(i.cantidad) AS piezas,
                       sum(i.cantidad * i.precio_unit) AS total
                FROM pedido_items i
                JOIN pedidos p ON p.id = i.pedido_id
                JOIN pagos   g ON g.pedido_id = p.id
                WHERE p.fecha >= %s AND {_VENTA}
                GROUP BY i.producto_id
                ORDER BY piezas DESC, total DESC LIMIT 5""",
            (desde,),
        ).fetchall()
        pendientes = con.execute(
            """SELECT COALESCE(sum(total), 0) AS total, count(*) AS n
               FROM pedidos WHERE estado = 'registrado'"""
        ).fetchone()
        por_enviar = con.execute("SELECT count(*) AS n FROM pedidos WHERE estado = 'pagado'").fetchone()["n"]
        por_reembolsar = con.execute(
            "SELECT count(*) AS n FROM pagos WHERE estado = 'por_reembolsar'"
        ).fetchone()["n"]
        clientes = con.execute("SELECT count(*) AS n FROM usuarios WHERE rol = 'cliente'").fetchone()["n"]
        recompras = con.execute(
            "SELECT count(*) AS n FROM suscripciones WHERE estado = 'activa'"
        ).fetchone()["n"]
    return {
        "ventas_total": _f(actual["total"]),
        "pedidos_pagados": actual["n"],
        "clientes_con_compra": actual["clientes"],
        "ventas_periodo_anterior": _f(anterior["total"]),
        "por_dia": [{"fecha": f["fecha"], "total": _f(f["total"]), "pedidos": f["pedidos"]} for f in por_dia],
        "por_metodo": {m: {"total": _f(f["total"]), "pedidos": f["pedidos"]} for m, f in por_metodo.items()},
        "por_estado": por_estado,
        "top": [
            {"producto_id": t["producto_id"], "nombre": t["nombre"], "piezas": int(t["piezas"]), "total": _f(t["total"])}
            for t in top
        ],
        "por_cobrar": _f(pendientes["total"]),
        "pedidos_por_cobrar": pendientes["n"],
        "pedidos_por_enviar": por_enviar,
        "pedidos_por_reembolsar": por_reembolsar,
        "clientes_total": clientes,
        "recompras_activas": recompras,
    }


# =========================================================
# Suscripciones de recompra
# =========================================================

def _suscripcion_docs(con, filas) -> list[dict]:
    ids = [f["id"] for f in filas]
    items: dict[int, list] = defaultdict(list)
    if ids:
        for it in con.execute(
            "SELECT suscripcion_id, producto_id, variante, cantidad FROM suscripcion_items"
            " WHERE suscripcion_id = ANY(%s) ORDER BY producto_id, variante",
            (ids,),
        ):
            items[it["suscripcion_id"]].append(
                {"producto_id": it["producto_id"], "variante": it["variante"], "cantidad": it["cantidad"]}
            )
    return [{**f, "_id": f["id"], "items": items[f["id"]]} for f in filas]


def crear_suscripcion(con, *, usuario_id, cada_dias, proxima: date, metodo_pago, entrega: dict, items) -> int:
    sid = con.execute(
        "INSERT INTO suscripciones (usuario_id, estado, cada_dias, proxima, metodo_pago, entrega, creada)"
        " VALUES (%s, 'activa', %s, %s, %s, %s, LOCALTIMESTAMP(0)) RETURNING id",
        (usuario_id, cada_dias, proxima, metodo_pago, Jsonb(entrega)),
    ).fetchone()["id"]
    with con.cursor() as cur:
        cur.executemany(
            "INSERT INTO suscripcion_items (suscripcion_id, producto_id, variante, cantidad) VALUES (%s, %s, %s, %s)",
            [(sid, i["producto_id"], i.get("variante", ""), i["cantidad"]) for i in items],
        )
    return sid


def suscripcion(suscripcion_id: int, usuario_id: int | None = None) -> dict | None:
    consulta = "SELECT * FROM suscripciones WHERE id = %s"
    params: list = [suscripcion_id]
    if usuario_id is not None:
        consulta += " AND usuario_id = %s"
        params.append(usuario_id)
    with transaccion() as con:
        docs = _suscripcion_docs(con, con.execute(consulta, params).fetchall())
    return docs[0] if docs else None


def suscripciones(usuario_id: int | None = None, estado: str | None = None) -> list[dict]:
    condiciones, params = [], []
    if usuario_id is not None:
        condiciones.append("usuario_id = %s")
        params.append(usuario_id)
    if estado:
        condiciones.append("estado = %s")
        params.append(estado)
    where = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    with transaccion() as con:
        return _suscripcion_docs(con, con.execute("SELECT * FROM suscripciones" + where + " ORDER BY id DESC", params).fetchall())


def cambiar_suscripcion(suscripcion_id: int, usuario_id: int | None, **campos) -> dict | None:
    """Pausar / reanudar / cancelar / cambiar frecuencia. Una cancelada ya no revive."""
    permitidos = {"estado", "cada_dias", "proxima"}
    campos = {k: v for k, v in campos.items() if k in permitidos}
    condicion = "id = %s AND estado <> 'cancelada'"
    params_cond: list = [suscripcion_id]
    if usuario_id is not None:
        condicion += " AND usuario_id = %s"
        params_cond.append(usuario_id)
    asignaciones = sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in campos)
    with transaccion() as con:
        fila = con.execute(
            sql.SQL("UPDATE suscripciones SET {} WHERE " + condicion + " RETURNING *").format(asignaciones),
            [*campos.values(), *params_cond],
        ).fetchone()
        return _suscripcion_docs(con, [fila])[0] if fila else None


def recompras_vencidas(con, hoy: date) -> list[dict]:
    """Suscripciones activas a las que ya les toca pedido. FOR UPDATE SKIP
    LOCKED: si dos procesos corren al mismo tiempo, cada uno toma renglones
    distintos y ningún cliente recibe dos pedidos el mismo día."""
    filas = con.execute(
        "SELECT * FROM suscripciones WHERE estado = 'activa' AND proxima <= %s"
        " ORDER BY proxima, id FOR UPDATE SKIP LOCKED",
        (hoy,),
    ).fetchall()
    return _suscripcion_docs(con, filas)


# =========================================================
# Bitácora de correos
# =========================================================

def registrar_correo(destinatario, asunto, plantilla, estado, proveedor_id="", detalle="", pedido_id=None) -> None:
    with transaccion() as con:
        con.execute(
            "INSERT INTO correos (destinatario, asunto, plantilla, estado, proveedor_id, detalle, pedido_id, creado)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, LOCALTIMESTAMP(0))",
            (destinatario, asunto[:200], plantilla, estado, proveedor_id[:120], detalle[:300], pedido_id),
        )


def correos_recientes(limite: int = 30) -> list[dict]:
    with transaccion() as con:
        return con.execute("SELECT * FROM correos ORDER BY id DESC LIMIT %s", (limite,)).fetchall()


# =========================================================
# Datos iniciales: migrar desde MongoDB o cargar la demo
# =========================================================

def inicializar(mongo_db, datos: dict, hashear) -> None:
    """Crea las tablas y, si están vacías, las llena:
    - Si MongoDB todavía tiene usuarios/pedidos (base de una entrega
      anterior), los copia CONSERVANDO los ids, para que las membresías
      (que siguen en Mongo y apuntan a usuario_id) no se rompan.
    - Si no, carga los usuarios de datos_ejemplo.json y pedidos de ejemplo."""
    migrar()
    with transaccion() as con:
        con.execute("SELECT pg_advisory_xact_lock(7002)")
        if con.execute("SELECT count(*) AS n FROM usuarios").fetchone()["n"] > 0:
            return
        if "usuarios" in mongo_db.list_collection_names() and mongo_db.usuarios.estimated_document_count() > 0:
            n_u, n_p = _migrar_desde_mongo(con, mongo_db)
            print(f"[frecuente] PostgreSQL: se migraron {n_u} usuarios y {n_p} pedidos desde MongoDB")
        else:
            _cargar_usuarios_demo(con, datos, hashear)
            productos = list(mongo_db.productos.find())
            _cargar_pedidos_demo(con, productos)
            print("[frecuente] PostgreSQL: se cargaron los usuarios y pedidos de ejemplo")
        _ajustar_secuencias(con)


def _migrar_desde_mongo(con, mongo_db) -> tuple[int, int]:
    from pagos import referencia_de

    import re

    n_u = 0
    for u in mongo_db.usuarios.find().sort("_id", 1):
        # Versiones viejas no validaban el teléfono: lo que no sean 10
        # dígitos se deja vacío para que pase el CHECK de la tabla.
        telefono = re.sub(r"\D", "", str(u.get("telefono") or ""))
        con.execute(
            "INSERT INTO usuarios (id, nombre, email, telefono, rol, activo, password_hash, creado)"
            " VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s)",
            (u["_id"], (u.get("nombre") or "").strip() or "Cliente", u["email"].strip().lower(),
             telefono if len(telefono) == 10 else "",
             u.get("rol") if u.get("rol") in ("cliente", "admin") else "cliente",
             u["password_hash"], u.get("creado") or datetime.now().replace(microsecond=0)),
        )
        n_u += 1
    nombres = {p["_id"]: p["nombre"] for p in mongo_db.productos.find({}, {"nombre": 1})}
    n_p = 0
    for p in mongo_db.pedidos.find().sort("_id", 1):
        pago = p.get("pago") or {
            # Pedidos de antes de los pagos en línea: se cobraban en el local
            "metodo": "efectivo",
            "estado": "aprobado" if p["estado"] in ("pagado", "enviado", "entregado") else "pendiente",
            "modo": "manual",
            "detalle": "Pedido anterior a los pagos en línea",
        }
        pago = {**pago, "referencia": pago.get("referencia") or referencia_de(p["_id"])}
        lineas = [
            {**i, "nombre": nombres.get(i["producto_id"], f"Producto {i['producto_id']}"), "variante": ""}
            for i in p["items"]
        ]
        insertar_pedido(
            con,
            pedido_id=p["_id"],
            usuario_id=p["usuario_id"],
            fecha=p["fecha"],
            estado=p["estado"],
            lineas=lineas,
            envio=0.0,
            pago=pago,
            entrega={"tipo": "recoger", "modo": "manual"},
        )
        n_p += 1
    return n_u, n_p


def _cargar_usuarios_demo(con, datos: dict, hashear) -> None:
    ahora = datetime.now().replace(microsecond=0)
    for u in datos["usuarios"]:
        con.execute(
            "INSERT INTO usuarios (id, nombre, email, telefono, rol, password_hash, creado)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (u["id"], u["nombre"], u["email"].lower(), u.get("telefono", ""), u["rol"], hashear(u["password"]), ahora),
        )


# Direcciones de ejemplo para los pedidos con envío de la demo
_DIRECCIONES_DEMO = [
    {"calle": "Av. Chapultepec Sur", "numero": "480", "colonia": "Americana", "ciudad": "Guadalajara", "estado": "JA", "cp": "44160"},
    {"calle": "Av. Patria", "numero": "1891", "colonia": "Puerta de Hierro", "ciudad": "Zapopan", "estado": "JA", "cp": "45116"},
    {"calle": "Av. Andares", "numero": "3500", "colonia": "Puerta de Hierro", "ciudad": "Zapopan", "estado": "JA", "cp": "45116"},
    {"calle": "Calle Amsterdam", "numero": "240", "colonia": "Hipódromo", "ciudad": "Ciudad de México", "estado": "CX", "cp": "06100"},
]


def _cargar_pedidos_demo(con, productos: list[dict], cantidad: int = 36, dias: int = 30) -> None:
    """Historial de pedidos de ejemplo en los últimos `dias` para que el
    panel tenga qué mostrar. Son ventas "pasadas": no descuentan stock.
    Semilla fija: siempre salen los mismos pedidos (con fechas recientes)."""
    from pagos import modo_de

    clientes = [f["id"] for f in con.execute("SELECT id FROM usuarios WHERE rol = 'cliente' ORDER BY id")]
    if not productos or not clientes:
        return
    azar = random.Random(2026)
    metodos = ["mercadopago"] * 5 + ["paypal"] * 2 + ["transferencia"] * 2 + ["efectivo"]
    ahora = datetime.now().replace(microsecond=0)

    fechas = []
    for _ in range(cantidad):
        fecha = (ahora - timedelta(days=azar.randint(0, dias - 1))).replace(
            hour=azar.randint(8, 20), minute=azar.randint(0, 59), second=0
        )
        if fecha > ahora:
            fecha = ahora - timedelta(minutes=azar.randint(5, 120))
        fechas.append(fecha)
    fechas.sort()

    # Los últimos se fijan a mano para que la demo tenga de todo
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
        lineas = []
        for p in elegidos:
            variantes = p.get("variantes") or []
            lineas.append(
                {
                    "producto_id": p["_id"],
                    "nombre": p["nombre"],
                    "variante": azar.choice(variantes) if variantes else "",
                    "cantidad": azar.randint(1, 3),
                    "precio_unit": float(p["precio"]),
                }
            )
        metodo = azar.choice(metodos)
        if dias_atras >= 5:
            estado = azar.choice(["entregado"] * 6 + ["enviado"] + ["cancelado"])
        elif dias_atras >= 2:
            estado = azar.choice(["pagado", "enviado", "entregado", "registrado"])
        else:
            estado = azar.choice(["registrado", "pagado", "pagado"])
        if metodo == "efectivo" and estado in ("pagado", "enviado"):
            estado = "entregado" if dias_atras >= 2 else "registrado"
        if estado == "cancelado":
            estado_pago = azar.choice(["rechazado", "pendiente"])
        elif estado == "registrado":
            estado_pago = "pendiente" if metodo != "mercadopago" else azar.choice(["pendiente", "rechazado"])
        else:
            estado_pago = "aprobado"
        if indice in especiales:
            metodo, estado, estado_pago, _ = especiales[indice]

        cliente = azar.choice(clientes)
        a_domicilio = metodo != "efectivo" and azar.random() < 0.7
        if a_domicilio:
            direccion = _DIRECCIONES_DEMO[cliente % len(_DIRECCIONES_DEMO)]
            foraneo = direccion["estado"] != "JA"
            costo = 189.0 if foraneo else 129.0
            entrega = {
                "tipo": "domicilio",
                "nombre": f"Cliente {cliente}",
                "telefono": "3300000000",
                **direccion,
                "paqueteria": "estafeta",
                "servicio": "terrestre",
                "descripcion": "Estafeta Terrestre",
                "dias": "3-5 días" if foraneo else "2-3 días",
                "costo": costo,
                "modo": "simulado",
            }
            if estado in ("enviado", "entregado"):
                entrega["guia"] = f"SIM{fecha:%y%m%d}{indice:04d}"
        else:
            costo = 0.0
            entrega = {"tipo": "recoger", "modo": "manual"}

        aprobado = estado_pago in ("aprobado", "por_reembolsar")
        insertar_pedido(
            con,
            usuario_id=cliente,
            fecha=fecha,
            estado=estado,
            lineas=lineas,
            envio=costo,
            pago={
                "metodo": metodo,
                "estado": estado_pago,
                "modo": modo_de(metodo),
                "pago_id": "DEMO" if aprobado else "",
                "detalle": "Pedido de ejemplo",
                "intentos": 1,
                "fecha_pago": fecha + timedelta(minutes=3) if aprobado else None,
                "actualizado": fecha,
            },
            entrega=entrega,
        )
