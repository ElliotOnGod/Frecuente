"""Contraseñas, tokens, registro, inicio de sesión y permisos."""

import pytest

from conftest import ErrorGraphQL

YO = "{ yo { id nombre rol } }"


def test_hash_no_guarda_la_contrasena_y_verifica():
    from auth import hashear_password, verificar_password

    h = hashear_password("cafe1234")
    assert "cafe1234" not in h and h.startswith("pbkdf2_sha256$260000$")
    assert verificar_password("cafe1234", h)
    assert not verificar_password("cafe12345", h)
    # Misma contraseña, sal distinta → hash distinto
    assert hashear_password("cafe1234") != h


def test_token_ida_y_vuelta_y_token_alterado():
    from auth import SesionInvalida, crear_token, usuario_id_de_token

    t = crear_token(7)
    assert usuario_id_de_token(t) == 7
    with pytest.raises(SesionInvalida):
        usuario_id_de_token(t[:-3] + ("aaa" if not t.endswith("aaa") else "bbb"))


def test_registro_crea_cliente_y_manda_bienvenida(gql, nuevo_cliente):
    import relacional

    token, usuario = nuevo_cliente("Ana Registro")
    assert gql(YO, token=token)["yo"]["rol"] == "cliente"
    correos = [c for c in relacional.correos_recientes(20) if c["destinatario"] == usuario["email"]]
    assert correos and correos[0]["plantilla"] == "bienvenida" and correos[0]["estado"] == "simulado"


def test_registro_valida_datos(gql, nuevo_cliente):
    _, usuario = nuevo_cliente()
    mutacion = "mutation($i:RegistroInput!){ registrarUsuario(input:$i){ token } }"
    with pytest.raises(ErrorGraphQL, match="Ya existe"):
        gql(mutacion, {"i": {"nombre": "X", "email": usuario["email"].upper(), "password": "12345678"}})
    with pytest.raises(ErrorGraphQL, match="al menos 8"):
        gql(mutacion, {"i": {"nombre": "X", "email": "corta@prueba.frecuente", "password": "123"}})
    with pytest.raises(ErrorGraphQL, match="10 dígitos"):
        gql(mutacion, {"i": {"nombre": "X", "email": "tel@prueba.frecuente", "password": "12345678", "telefono": "juan"}})


def test_login_mismo_mensaje_si_no_existe_o_esta_mal(gql):
    m = "mutation($e:String!,$p:String!){ iniciarSesion(email:$e,password:$p){ token } }"
    with pytest.raises(ErrorGraphQL) as a:
        gql(m, {"e": "nadie@frecuente.mx", "p": "lo-que-sea"})
    with pytest.raises(ErrorGraphQL) as b:
        gql(m, {"e": "demo@frecuente.mx", "p": "mal-password"})
    assert str(a.value) == str(b.value) == "Correo o contraseña incorrectos"


def test_cliente_no_puede_usar_el_panel(gql, token_cliente):
    with pytest.raises(ErrorGraphQL, match="administrador"):
        gql("{ resumenAdmin { ventasTotal } }", token=token_cliente)
    with pytest.raises(ErrorGraphQL, match="iniciar sesión"):
        gql("{ misPedidos { id } }")


def test_admin_desactiva_cuenta_y_su_token_deja_de_servir(gql, token_admin, nuevo_cliente):
    token, usuario = nuevo_cliente()
    m = "mutation($id:Int!,$a:Boolean!){ cambiarActivoUsuario(id:$id, activo:$a){ id activo } }"
    assert gql(m, {"id": usuario["id"], "a": False}, token=token_admin)["cambiarActivoUsuario"]["activo"] is False
    with pytest.raises(ErrorGraphQL, match="desactivada"):
        gql(YO, token=token)
    gql(m, {"id": usuario["id"], "a": True}, token=token_admin)
    assert gql(YO, token=token)["yo"]["id"] == usuario["id"]


def test_admin_no_se_puede_quitar_su_propio_rol(gql, token_admin):
    yo = gql(YO, token=token_admin)["yo"]
    with pytest.raises(ErrorGraphQL, match="a ti mismo"):
        gql("mutation($id:Int!){ cambiarRolUsuario(id:$id, rol:\"cliente\"){ id } }", {"id": yo["id"]}, token=token_admin)


# ---------------- recuperación de contraseña (RQF4, RQF5) ----------------

SOLICITAR = "mutation($c:String!){ solicitarRecuperacion(correo:$c) }"
RESTABLECER = "mutation($t:String!,$p:String!){ restablecerContrasena(token:$t, contrasena:$p) }"
LOGIN = "mutation($e:String!,$p:String!){ iniciarSesion(email:$e,password:$p){ token } }"


@pytest.fixture
def enlaces(monkeypatch):
    """Captura el token que el correo de recuperación llevaría en su enlace."""
    import correos

    capturados = []
    original = correos.recuperacion

    def capturar(usuario, token, minutos):
        capturados.append(token)
        original(usuario, token, minutos)  # también queda en la bitácora de correos

    monkeypatch.setattr(correos, "recuperacion", capturar)
    return capturados


def test_recuperacion_mismo_mensaje(gql, nuevo_cliente, enlaces):
    """RQNF11: misma respuesta tenga o no cuenta el correo; solo hay correo si la tiene."""
    import relacional

    _, usuario = nuevo_cliente()
    con_cuenta = gql(SOLICITAR, {"c": usuario["email"]})["solicitarRecuperacion"]
    sin_cuenta = gql(SOLICITAR, {"c": "nadie-registrado@prueba.frecuente"})["solicitarRecuperacion"]
    assert con_cuenta == sin_cuenta == "Si el correo tiene una cuenta, te enviamos un enlace para cambiar tu contraseña."
    assert len(enlaces) == 1
    enviados = [c for c in relacional.correos_recientes(30) if c["plantilla"] == "recuperacion"]
    assert any(c["destinatario"] == usuario["email"] for c in enviados)
    assert not any(c["destinatario"] == "nadie-registrado@prueba.frecuente" for c in enviados)


def test_enlace_recuperacion_caduca(gql, nuevo_cliente, enlaces):
    """RQNF12: el enlace vence 30 minutos después de emitirse."""
    from datetime import datetime, timedelta, timezone

    import jwt

    import relacional
    from auth import JWT_ALG, JWT_SECRET, crear_token_recuperacion

    _, usuario = nuevo_cliente()
    gql(SOLICITAR, {"c": usuario["email"]})
    datos = jwt.decode(enlaces[0], JWT_SECRET, algorithms=[JWT_ALG])
    assert datos["exp"] - datos["iat"] == 30 * 60

    guardado = relacional.usuario(usuario["id"])["password_hash"]
    hace_31 = datetime.now(timezone.utc) - timedelta(minutes=31)
    vencido = crear_token_recuperacion(usuario["id"], guardado, ahora=hace_31)
    with pytest.raises(ErrorGraphQL, match="no es válido o ya venció"):
        gql(RESTABLECER, {"t": vencido, "p": "nueva-clave-1"})
    hace_29 = datetime.now(timezone.utc) - timedelta(minutes=29)
    vigente = crear_token_recuperacion(usuario["id"], guardado, ahora=hace_29)
    assert "Listo" in gql(RESTABLECER, {"t": vigente, "p": "nueva-clave-1"})["restablecerContrasena"]


def test_enlace_recuperacion_un_solo_uso(gql, nuevo_cliente, enlaces):
    """RQNF13: el enlace deja de servir después de usarse una vez."""
    _, usuario = nuevo_cliente()
    gql(SOLICITAR, {"c": usuario["email"]})
    enlace = enlaces[0]
    # El enlace no sirve como sesión
    with pytest.raises(ErrorGraphQL, match="sesión expiró"):
        gql(YO, token=enlace)

    assert "Listo" in gql(RESTABLECER, {"t": enlace, "p": "otra-clave-123"})["restablecerContrasena"]
    assert gql(LOGIN, {"e": usuario["email"], "p": "otra-clave-123"})["iniciarSesion"]["token"]
    with pytest.raises(ErrorGraphQL, match="Correo o contraseña incorrectos"):
        gql(LOGIN, {"e": usuario["email"], "p": "contrasena-segura"})
    with pytest.raises(ErrorGraphQL, match="no es válido o ya venció"):
        gql(RESTABLECER, {"t": enlace, "p": "tercera-clave-99"})


def test_recuperacion_valida_contrasena(gql, nuevo_cliente, enlaces):
    """RQNF14: rechaza contraseñas de menos de 8 caracteres con el mensaje del registro."""
    _, usuario = nuevo_cliente()
    gql(SOLICITAR, {"c": usuario["email"]})
    with pytest.raises(ErrorGraphQL) as corta:
        gql(RESTABLECER, {"t": enlaces[0], "p": "1234567"})
    with pytest.raises(ErrorGraphQL) as registro:
        gql(
            "mutation($i:RegistroInput!){ registrarUsuario(input:$i){ token } }",
            {"i": {"nombre": "X", "email": "corta2@prueba.frecuente", "password": "1234567"}},
        )
    assert str(corta.value) == str(registro.value) == "La contraseña debe tener al menos 8 caracteres"
    # El enlace sigue sirviendo con una contraseña válida (no se gastó)
    assert "Listo" in gql(RESTABLECER, {"t": enlaces[0], "p": "12345678"})["restablecerContrasena"]
