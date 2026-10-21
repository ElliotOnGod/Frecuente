import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import Sidebar from "./Sidebar";
import CategoryGrid from "./CategoryGrid";
import { SkeletonGrid } from "./Skeleton";

const QUERY_CATEGORIAS = `
  query Categorias {
    categorias {
      id nombre descripcion
      productos { id }
    }
  }
`;

/**
 * CatalogoHome — isla del home: consulta las categorías una sola vez y las
 * reparte entre Sidebar y CategoryGrid. `children` es contenido estático que
 * Astro le pasa (la ContextSection), así no se hidrata de más.
 */
export default function CatalogoHome({ children }) {
  const { data, loading, error } = useGraphQLQuery(QUERY_CATEGORIAS);
  const categorias = data?.categorias ?? [];

  return (
    <div className="cf-layout">
      <Sidebar categorias={categorias} />

      <main>
        <h2>Compra por categoría</h2>

        {loading && <SkeletonGrid cantidad={4} />}

        {error && (
          <p className="cf-alerta cf-alerta--error" role="alert">
            <span className="cf-icon" aria-hidden="true">!</span>
            No se pudo cargar el catálogo: {error}
          </p>
        )}

        {!loading && !error && <CategoryGrid categorias={categorias} />}

        {children}
      </main>
    </div>
  );
}
