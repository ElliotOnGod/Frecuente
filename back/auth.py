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

# La clave firma las sesiones (JWT) y los códigos de canje del día. Si
# fuera pública, cualquiera podría fabricarse un token de admin. Por eso:
#   - sin JWT_SECRET en .env (o con el valor de ejemplo) se genera una
#     clave aleatoria al arrancar. Funciona igual, pero las sesiones se
#     cierran cada vez que reinicias el backend.
#   - para que las sesiones sobrevivan reinicios, pon tu propia clave en .env.
_CLAVES_DE_EJEMPLO = {"", "cambia-esta-clave-en-produccion"}
JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
if JWT_SECRET in _CLAVES_DE_EJEMPLO:
    JWT_SECRET = secrets.token_urlsafe(48)
    print(
        "[frecuente] AVISO: falta JWT_SECRET en back/.env; se generó una clave temporal.\n"
        "            Las sesiones se cerrarán al reiniciar el backend. Para fijarla, pon en .env:\n"
        f"            JWT_SECRET={secrets.token_urlsafe(32)}"
    )
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


# Hash de una contraseña al azar que nadie conoce. Se usa cuando el correo
# no existe, para que el login tarde lo mismo que con un correo real y el
# tiempo de respuesta no delate qué correos tienen cuenta.
_HASH_FALSO = hashear_password(secrets.token_urlsafe(16))


def gastar_tiempo_de_verificacion(password: str) -> None:
    verificar_password(password, _HASH_FALSO)


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
