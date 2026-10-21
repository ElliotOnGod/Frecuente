import { useStore } from "../../store/useStore";
import { iconoDe, pesos } from "../../lib/formato";

/** ProductCard — tarjeta de producto del catálogo. Dispara openProduct. */
export default function ProductCard({ producto }) {
  const openProduct = useStore((s) => s.openProduct);
  const agotado = producto.stock <= 0;

  return (
    <article className="cf-card">
      <div className="cf-figura" aria-hidden="true">{iconoDe(producto.categoriaId)}</div>
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
