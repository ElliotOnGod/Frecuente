import { useStore } from "../../store/useStore";
import { pesos } from "../../lib/formato";
import Foto from "./Foto";

/** ProductCard — tarjeta de producto del catálogo. Dispara openProduct. */
export default function ProductCard({ producto }) {
  const openProduct = useStore((s) => s.openProduct);
  const agotado = producto.stock <= 0;

  return (
    <article className="cf-card">
      <button
        type="button"
        className="cf-card__foto"
        onClick={() => openProduct(producto.id)}
        tabIndex={-1}
        aria-hidden="true"
      >
        {/* Atajo con el mouse: el botón "Ver detalle" es el accesible con teclado */}
        <Foto src={producto.imagenUrl} alt={producto.nombre} categoriaId={producto.categoriaId} ancho={480} />
      </button>
      <div className="cf-card__cuerpo">
        <h3 className="cf-card__titulo">{producto.nombre}</h3>
        <p className="cf-card__precio">{pesos(producto.precio)}</p>
        <span className={`cf-insignia${agotado ? " cf-insignia--agotado" : ""}`}>
          {agotado ? "Agotado" : `${producto.stock} disponibles`}
        </span>
        <button
          className="cf-btn"
          style={{ marginTop: "var(--espacio-sm)" }}
          onClick={() => openProduct(producto.id)}
        >
          Ver detalle
        </button>
      </div>
    </article>
  );
}
