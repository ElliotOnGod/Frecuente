"""
auth.py — contraseñas y sesiones (JWT).

- Las contraseñas NUNCA se guardan en texto plano: se guarda un hash
  PBKDF2-SHA256 con sal aleatoria (librería estándar de Python, hashlib).
- Al iniciar sesión el backend entrega un token JWT firmado. El front lo
  manda en cada petición con el encabezado  Authorization: Bearer <token>
  y aquí se verifica para saber quién es el usuario.

Equipo: Jehu Uribe Bermudez (23100139),
        Jose Fernando Leon Lopez (23100146),
        Elliot Garcia Lopez (22300923)
Materia: Programacion Web II - CETI Colomos
"""

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")

JWT_SECRET = os.getenv("JWT_SECRET", "cambia-esta-clave-en-produccion")
JWT_ALG = "HS256"
JWT_DIAS = 7
ITERACIONES = 260_000


# ---------------- contraseñas ----------------

def hashear_password(password: str) -> str:
    """Regresa 'pbkdf2_sha256$iteraciones$sal$hash' (todo en un string)."""
    sal = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), sal, ITERACIONES)
    return "pbkdf2_sha256${}${}${}".format(
        ITERACIONES,
        base64.b64encode(sal).decode(),
        base64.b64encode(dk).decode(),
    )


def verificar_password(password: str, guardado: str) -> bool:
    try:
        _, iteraciones, sal_b64, hash_b64 = guardado.split("$")
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(sal_b64), int(iteraciones)
        )
        # compare_digest compara en tiempo constante (evita ataques de tiempo)
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


# ---------------- tokens ----------------

class SesionInvalida(Exception):
    """El token no existe, está mal formado o ya expiró."""


def crear_token(usuario_id: int) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {"sub": str(usuario_id), "iat": ahora, "exp": ahora + timedelta(days=JWT_DIAS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def usuario_id_de_token(token: str) -> int:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise SesionInvalida("Tu sesión expiró, inicia sesión de nuevo")


def token_de_request(request) -> str | None:
    """Saca el token del encabezado Authorization: Bearer <token>."""
    if request is None:
        return None
    encabezado = request.headers.get("authorization", "")
    tipo, _, token = encabezado.partition(" ")
    return token.strip() if tipo.lower() == "bearer" and token.strip() else None
