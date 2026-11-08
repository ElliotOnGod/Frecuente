"""
Pruebas automatizadas del backend (pytest). Corren contra un MongoDB y un
PostgreSQL REALES pero de prueba (bases *_test), que se borran y se vuelven
a llenar con los datos de ejemplo al empezar. En GitHub Actions las dos
bases las levanta el workflow como "services" (ver .github/workflows/ci.yml).

    cd back
    pytest

Variables (con estos valores por defecto):
    DATABASE_URL = postgresql://postgres:postgres@localhost:5432/frecuente_test
    MONGO_URI    = mongodb://localhost:27017      MONGO_DB = frecuente_test
"""

import os
import sys
from pathlib import Path

# Antes de importar el backend: configuración de prueba. load_dotenv no
# pisa variables que ya existen, así que el .env local no se mezcla.
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/frecuente_test")
os.environ["MONGO_DB"] = os.environ.get("MONGO_DB_TEST", "frecuente_test")
os.environ["JWT_SECRET"] = "clave-solo-para-pruebas-automatizadas-0123456789"
os.environ["PAGOS_MODO"] = "simulado"
os.environ["CORREOS_SINCRONO"] = "1"
os.environ["RECOMPRAS_AUTOMATICAS"] = "0"
os.environ["CRON_SECRET"] = "cron-de-pruebas"
for llave in ("BREVO_API_KEY", "BREVO_REMITENTE", "ENVIA_TOKEN", "MP_ACCESS_TOKEN", "PAYPAL_CLIENT_ID", "PAYPAL_SECRET", "CORS_ORIGENES"):
    os.environ[llave] = ""
os.environ["CORREO_TIENDA"] = "tienda@prueba.frecuente"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def app():
    import database

    database.init_db(force=True)
    import main

    return main.app


@pytest.fixture(scope="session")
def cliente(app):
    with TestClient(app) as c:
        yield c


class ErrorGraphQL(Exception):
    pass


@pytest.fixture(scope="session")
def gql(cliente):
    """gql(consulta, variables=None, token=None) → data; lanza ErrorGraphQL con el mensaje."""

    def ejecutar(consulta, variables=None, token=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        r = cliente.post("/graphql", json={"query": consulta, "variables": variables or {}}, headers=headers)
        cuerpo = r.json()
        if cuerpo.get("errors"):
            raise ErrorGraphQL(cuerpo["errors"][0]["message"])
        return cuerpo["data"]

    return ejecutar


def _login(gql, email, password):
    return gql(
        "mutation($e:String!,$p:String!){ iniciarSesion(email:$e,password:$p){ token } }",
        {"e": email, "p": password},
    )["iniciarSesion"]["token"]


@pytest.fixture(scope="session")
def token_admin(gql):
    return _login(gql, "admin@frecuente.mx", "admin1234")


@pytest.fixture(scope="session")
def token_cliente(gql):
    return _login(gql, "demo@frecuente.mx", "cafe1234")


@pytest.fixture
def nuevo_cliente(gql):
    """Una cuenta nueva por prueba (correo único)."""
    import uuid

    def crear(nombre="Cliente Prueba"):
        correo = f"prueba-{uuid.uuid4().hex[:10]}@prueba.frecuente"
        r = gql(
            "mutation($i:RegistroInput!){ registrarUsuario(input:$i){ token usuario{ id email } } }",
            {"i": {"nombre": nombre, "email": correo, "password": "contrasena-segura", "telefono": "3312345678"}},
        )["registrarUsuario"]
        return r["token"], r["usuario"]

    return crear


@pytest.fixture
def stock():
    """Leer y fijar el stock de un producto directamente en MongoDB."""
    from database import db

    class Stock:
        def __call__(self, pid):
            return db.productos.find_one({"_id": pid})["stock"]

        def fijar(self, pid, n):
            db.productos.update_one({"_id": pid}, {"$set": {"stock": n}})

    return Stock()
