import { useEffect } from "react";
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { RUTAS } from "../../lib/formato";
import ProductCard from "./ProductCard";
import { SkeletonGrid } from "./Skeleton";

const QUERY_CATEGORIA = `
  query Categoria($id: Int!) {
    categoria(id: $id) {
      id nombre descripcion
      productos { id nombre precio stock categoriaId }
    }
  }
`;

/**
 * CategoryDetail — lee el id de la URL (/categoria?id=N), consulta la
 * categoría y lista sus productos. Se monta con client:only porque necesita
 * window.location.
 */
export default function CategoryDetail() {
  const id = Number(new URLSearchParams(window.location.search).get("id"));
  const idValido = Number.isInteger(id) && id > 0;

  const { data, loading, error } = useGraphQLQuery(
    QUERY_CATEGORIA,
    { id },
    { omitir: !idValido }
  );
  const categoria = data?.categoria;

  useEffect(() => {
    if (categoria) document.title = `${categoria.nombre} — Frecuente`;
  }, [categoria]);

  return (
    <>
      <a className="cf-link" href={RUTAS.inicio}>← Volver al inicio</a>

      <h1>{categoria?.nombre || (loading ? "Cargando…" : "Categoría")}</h1>
      {categoria && <p className="cf-caption">{categoria.descripcion}</p>}

      {loading && <SkeletonGrid cantidad={4} />}

      {!idValido && (
        <p className="cf-vacio">Esa categoría no existe. Regresa al inicio y elige otra.</p>
      )}

      {idValido && !loading && !error && !categoria && (
        <p className="cf-vacio">No encontramos esa categoría.</p>
      )}

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span>
          No se pudieron cargar los productos: {error}
        </p>
      )}

      {categoria && !loading && (
        <div className="cf-catalogo">
          {categoria.productos.map((p) => (
            <ProductCard key={p.id} producto={p} />
          ))}
        </div>
      )}

      {categoria && !loading && categoria.productos.length === 0 && (
        <p className="cf-vacio">Todavía no hay productos en esta categoría.</p>
      )}
    </>
  );
}
