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
