"""
eventos.py — avisos en tiempo real para las Subscriptions de GraphQL.

Funciona como un "periódico" (patrón publicar/suscribir, pub/sub):

  - Cada pestaña que abre el backoffice (o la página de un pedido o de una
    membresía) se SUSCRIBE y recibe una cola propia (asyncio.Queue).
  - Cuando pasa algo (pedido nuevo, pago aprobado, canje…) el resolver
    llama a publicar(...) y el aviso se copia a la cola de cada suscriptor.
  - La Subscription de Strawberry lee su cola y le manda cada aviso al
    navegador por WebSocket (protocolo graphql-transport-ws).

Todo vive en memoria del proceso: es suficiente para un solo servidor
(uvicorn). Con varios servidores se cambiaría por Redis pub/sub o por
Change Streams de MongoDB, sin tocar el resto del código.

publicar() se puede llamar desde cualquier hilo (los resolvers síncronos y
el webhook), por eso usa loop.call_soon_threadsafe para dejar el aviso en
la cola dentro del event loop correcto.

Equipo: Jehu Uribe Bermudez (23100139),
        Jose Fernando Leon Lopez (23100146),
        Elliot Garcia Lopez (22300923)
Materia: Programacion Web II - CETI Colomos
"""

import asyncio
import itertools
from contextlib import contextmanager
from datetime import datetime

# Tipos de evento que se publican
PEDIDO_NUEVO = "pedido_nuevo"
PAGO_ACTUALIZADO = "pago_actualizado"
PEDIDO_ESTADO = "pedido_estado"
STOCK_BAJO = "stock_bajo"
MEMBRESIA_NUEVA = "membresia_nueva"
MEMBRESIA_ACTUALIZADA = "membresia_actualizada"
CANJE = "canje"

_contador = itertools.count(1)
_suscriptores: dict[int, tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = {}


@contextmanager
def suscribirse(max_pendientes: int = 100):
    """Regresa una cola que recibe todos los eventos mientras dure el `with`.
    Al salir (el navegador se desconecta) se da de baja sola."""
    loop = asyncio.get_running_loop()
    cola: asyncio.Queue = asyncio.Queue(maxsize=max_pendientes)
    clave = next(_contador)
    _suscriptores[clave] = (loop, cola)
    try:
        yield cola
    finally:
        _suscriptores.pop(clave, None)


def _entregar(cola: asyncio.Queue, evento: dict) -> None:
    try:
        cola.put_nowait(evento)
    except asyncio.QueueFull:
        # Un cliente muy lento no debe frenar a los demás: se descarta
        # el aviso más viejo y se mete el nuevo.
        try:
            cola.get_nowait()
            cola.put_nowait(evento)
        except (asyncio.QueueEmpty, asyncio.QueueFull):
            pass


def publicar(tipo: str, mensaje: str, **datos) -> dict:
    """Manda un aviso a todos los suscriptores. Nunca truena: si nadie
    está escuchando, simplemente no pasa nada."""
    evento = {
        "id": next(_contador),
        "tipo": tipo,
        "mensaje": mensaje,
        "fecha": datetime.now().replace(microsecond=0),
        "pedido_id": datos.get("pedido_id"),
        "membresia_id": datos.get("membresia_id"),
        "usuario_id": datos.get("usuario_id"),
        "monto": datos.get("monto"),
    }
    for loop, cola in list(_suscriptores.values()):
        try:
            loop.call_soon_threadsafe(_entregar, cola, evento)
        except RuntimeError:
            # El loop de ese suscriptor ya se cerró
            pass
    return evento


def total_suscriptores() -> int:
    return len(_suscriptores)
