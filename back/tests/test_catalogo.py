"""Catálogo en MongoDB: filtros, variantes, validaciones del admin y fotos."""

import base64

import pytest

from conftest import ErrorGraphQL

PRODUCTOS = "query($m:String,$b:String,$c:Int){ productos(metodo:$m, buscar:$b, categoriaId:$c){ id nombre metodos variantes varianteNombre pesoKg } }"


def test_filtro_por_metodo_de_preparacion(gql):
    productos = gql(PRODUCTOS, {"m": "prensa"})["productos"]
    assert productos and all("prensa" in p["metodos"] for p in productos)
    assert {"Prensa francesa 600 ml", "Blend de Casa 250 g"} <= {p["nombre"] for p in productos}


def test_buscador_ignora_mayusculas_y_busca_en_descripcion(gql):
    assert [p["id"] for p in gql(PRODUCTOS, {"b": "ETIOP"})["productos"]] == [2]
    assert any(p["id"] == 2 for p in gql(PRODUCTOS, {"b": "floral"})["productos"])
    # Los caracteres especiales no rompen la búsqueda (se escapan)
    assert gql(PRODUCTOS, {"b": ".*("})["productos"] == []


def test_los_cafes_tienen_variantes_de_molienda(gql):
    cafes = gql(PRODUCTOS, {"c": 1})["productos"]
    assert all(p["varianteNombre"] == "Molienda" and "Grano entero" in p["variantes"] for p in cafes)
    leches = gql(PRODUCTOS, {"c": 2})["productos"]
    assert all(p["variantes"] == [] for p in leches)


def test_admin_crea_producto_con_variantes_y_valida_metodos(gql, token_admin, token_cliente):
    crear = "mutation($i:ProductoInput!){ crearProducto(input:$i){ id varianteNombre variantes metodos pesoKg } }"
    entrada = {"nombre": "Kenia AA 250 g", "precio": 290, "stock": 5, "categoriaId": 1,
               "varianteNombre": "Molienda", "variantes": ["Grano", "Grano", " Espresso "], "metodos": ["filtro"], "pesoKg": 0.3}
    with pytest.raises(ErrorGraphQL, match="administrador"):
        gql(crear, {"i": entrada}, token=token_cliente)
    p = gql(crear, {"i": entrada}, token=token_admin)["crearProducto"]
    assert p["variantes"] == ["Grano", "Espresso"] and p["metodos"] == ["filtro"]
    with pytest.raises(ErrorGraphQL, match="desconocido"):
        gql(crear, {"i": {**entrada, "metodos": ["microondas"]}}, token=token_admin)
    with pytest.raises(ErrorGraphQL, match="peso"):
        gql(crear, {"i": {**entrada, "pesoKg": 0}}, token=token_admin)
    gql("mutation($id:Int!){ eliminarProducto(id:$id) }", {"id": p["id"]}, token=token_admin)


def test_no_se_borra_un_producto_que_ya_se_vendio(gql, token_admin):
    with pytest.raises(ErrorGraphQL, match="ya aparece en pedidos"):
        gql("mutation{ eliminarProducto(id: 1) }", token=token_admin)


def test_subir_imagen_revisa_los_bytes_no_la_extension(gql, token_admin):
    m = "mutation($d:String!){ subirImagen(datos:$d) }"
    svg = base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>').decode()
    with pytest.raises(ErrorGraphQL, match="JPG, PNG o WebP"):
        gql(m, {"d": "data:image/png;base64," + svg}, token=token_admin)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    ruta = gql(m, {"d": base64.b64encode(png).decode()}, token=token_admin)["subirImagen"]
    assert ruta.startswith("/imagenes/") and len(ruta) == len("/imagenes/") + 32
