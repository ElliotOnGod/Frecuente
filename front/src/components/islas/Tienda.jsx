import { useEffect, useState } from "react";
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { RUTAS, leerParametros } from "../../lib/formato";
import ProductCard from "./ProductCard";
import { SkeletonGrid } from "./Skeleton";

const QUERY_FILTROS = `
  query FiltrosTienda {
    categorias { id nombre }
    metodosPreparacion { clave nombre }
  }
`;

const QUERY_PRODUCTOS = `
  query Tienda($categoriaId: Int, $metodo: String, $buscar: String) {
    productos(categoriaId: $categoriaId, metodo: $metodo, buscar: $buscar) {
      id nombre precio stock categoriaId imagenUrl variantes
    }
  }
`;

/** El texto se manda al servidor cuando dejas de escribir (no en cada tecla). */
function useRetrasado(valor, ms = 300) {
  const [retrasado, setRetrasado] = useState(valor);
  useEffect(() => {
    const t = setTimeout(() => setRetrasado(valor), ms);
    return () => clearTimeout(t);
  }, [valor, ms]);
  return retrasado;
}

/**
 * Tienda — todo el catálogo con buscador y filtros por categoría y por
 * método de preparación (/tienda?metodo=prensa&categoria=1&q=etiopía).
 * Los filtros se guardan en la URL: se puede compartir o volver atrás.
 */
export default function Tienda() {
  const inicial = leerParametros();
  const [texto, setTexto] = useState(inicial.q ?? "");
  const [categoria, setCategoria] = useState(inicial.categoria ? Number(inicial.categoria) : null);
  const [metodo, setMetodo] = useState(inicial.metodo ?? "");
  const buscar = useRetrasado(texto.trim());

  const filtros = useGraphQLQuery(QUERY_FILTROS);
  const { data, loading, error } = useGraphQLQuery(QUERY_PRODUCTOS, {
    categoriaId: categoria,
    metodo: metodo || null,
    buscar: buscar || null,
  });
  const productos = data?.productos ?? [];
  const categorias = filtros.data?.categorias ?? [];
  const metodos = filtros.data?.metodosPreparacion ?? [];

  // Refleja los filtros en la URL sin recargar la página
  useEffect(() => {
    const p = new URLSearchParams();
    if (buscar) p.set("q", buscar);
    if (categoria) p.set("categoria", String(categoria));
    if (metodo) p.set("metodo", metodo);
    const url = `${RUTAS.tienda}${p.toString() ? `?${p}` : ""}`;
    window.history.replaceState(null, "", url);
  }, [buscar, categoria, metodo]);

  const hayFiltros = Boolean(texto || categoria || metodo);
  const limpiar = () => {
    setTexto("");
    setCategoria(null);
    setMetodo("");
  };

  return (
    <>
      <h1>Tienda</h1>
      <p className="cf-caption">Café de especialidad, leches, matcha y accesorios para preparar en casa.</p>

      <div className="cf-tienda-filtros" role="search">
        <div className="cf-campo cf-tienda-filtros__buscar">
          <label className="cf-label" htmlFor="buscar-producto">Buscar</label>
          <input
            id="buscar-producto"
            className="cf-input"
            type="search"
            placeholder="Etiopía, avena, prensa…"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
          />
        </div>
        <div className="cf-campo">
          <label className="cf-label" htmlFor="filtro-categoria">Categoría</label>
          <select
            id="filtro-categoria"
            className="cf-input"
            value={categoria ?? ""}
            onChange={(e) => setCategoria(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Todas</option>
            {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </div>
      </div>

      <div className="cf-chips" role="group" aria-label="Método de preparación">
        <button type="button" className="cf-chip" aria-pressed={!metodo} onClick={() => setMetodo("")}>
          Todos los métodos
        </button>
        {metodos.map((m) => (
          <button
            key={m.clave}
            type="button"
            className="cf-chip"
            aria-pressed={metodo === m.clave}
            onClick={() => setMetodo(metodo === m.clave ? "" : m.clave)}
          >
            {m.nombre}
          </button>
        ))}
      </div>

      <p className="cf-caption" aria-live="polite" style={{ marginTop: "var(--espacio-md)" }}>
        {loading ? "Buscando…" : `${productos.length} ${productos.length === 1 ? "producto" : "productos"}`}
        {hayFiltros && !loading && (
          <>
            {" · "}
            <button className="cf-link" onClick={limpiar}>Quitar filtros</button>
          </>
        )}
      </p>

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> No se pudo cargar la tienda: {error}
        </p>
      )}

      {loading && !data && <SkeletonGrid cantidad={6} />}

      {!error && data && productos.length === 0 && !loading && (
        <p className="cf-vacio">No encontramos productos con esos filtros.</p>
      )}

      {productos.length > 0 && (
        <div className="cf-catalogo" aria-busy={loading}>
          {productos.map((p) => <ProductCard key={p.id} producto={p} />)}
        </div>
      )}
    </>
  );
}
