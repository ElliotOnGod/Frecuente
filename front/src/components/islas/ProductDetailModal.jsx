import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { useStore } from "../../store/useStore";
import { Skeleton } from "./Skeleton";
import { iconoDe, pesos, RUTAS } from "../../lib/formato";

const QUERY_PRODUCTO = `
  query Producto($id: Int!) {
    producto(id: $id) {
      id nombre descripcion precio stock categoriaId
      categoria { nombre }
    }
  }
`;

/**
 * ProductDetailModal — detalle del producto renderizado con createPortal
 * (portal) sobre document.body. Vive en el layout de Astro, así que está
 * disponible en todas las páginas y se controla con selectedProductId.
 */
export default function ProductDetailModal() {
  const id = useStore((s) => s.selectedProductId);
  const closeProduct = useStore((s) => s.closeProduct);
  const agregarAlCarrito = useStore((s) => s.agregarAlCarrito);
  const [cantidad, setCantidad] = useState(1);

  const { data, loading, error } = useGraphQLQuery(
    QUERY_PRODUCTO,
    { id: id ?? 0 },
    { omitir: id === null }
  );
  const producto = data?.producto;

  useEffect(() => setCantidad(1), [id]);

  useEffect(() => {
    const onEsc = (e) => e.key === "Escape" && closeProduct();
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [closeProduct]);

  if (id === null) return null;

  const agotado = producto ? producto.stock <= 0 : false;

  const agregar = () => {
    agregarAlCarrito(producto, cantidad);
    closeProduct();
  };

  const comprarAhora = () => {
    agregarAlCarrito(producto, cantidad);
    closeProduct();
    window.location.href = RUTAS.carrito;
  };

  return createPortal(
    <div
      className="cf-modal-fondo"
      role="dialog"
      aria-modal="true"
      aria-label="Detalle del producto"
      onClick={closeProduct}
    >
      <div className="cf-modal" onClick={(e) => e.stopPropagation()}>
        <div className="cf-modal__barra">
          <h2 style={{ margin: 0 }}>{producto?.nombre || "Cargando…"}</h2>
          <button className="cf-btn cf-btn--icono" aria-label="Cerrar" onClick={closeProduct}>
            ✕
          </button>
        </div>

        {loading && (
          <div className="cf-modal__cuerpo">
            <Skeleton alto="160px" />
            <div>
              <Skeleton alto="20px" ancho="70%" />
              <div style={{ height: "var(--espacio-sm)" }} />
              <Skeleton alto="14px" />
            </div>
          </div>
        )}

        {error && (
          <p className="cf-alerta cf-alerta--error" role="alert">
            <span className="cf-icon" aria-hidden="true">!</span> {error}
          </p>
        )}

        {producto && !loading && (
          <div className="cf-modal__cuerpo">
            <div className="cf-figura cf-figura--alta" aria-hidden="true">
              {iconoDe(producto.categoriaId)}
            </div>

            <div>
              <p className="cf-caption">{producto.categoria?.nombre}</p>
              <p>{producto.descripcion}</p>
              <p className="cf-card__precio">{pesos(producto.precio)}</p>

              <span className={`cf-insignia${agotado ? " cf-insignia--agotado" : ""}`}>
                {agotado ? "Agotado" : `${producto.stock} disponibles`}
              </span>

              <div className="cf-campo" style={{ marginTop: "var(--espacio-md)" }}>
                <label className="cf-label" htmlFor="cantidad">Cantidad</label>
                <div className="cf-cantidad">
                  <button
                    className="cf-btn cf-btn--secundario"
                    aria-label="Quitar uno"
                    onClick={() => setCantidad((c) => Math.max(1, c - 1))}
                  >
                    −
                  </button>
                  <input
                    id="cantidad"
                    className="cf-input"
                    type="number"
                    min="1"
                    max={producto.stock}
                    value={cantidad}
                    onChange={(e) =>
                      setCantidad(
                        Math.max(1, Math.min(Number(e.target.value) || 1, producto.stock))
                      )
                    }
                  />
                  <button
                    className="cf-btn cf-btn--secundario"
                    aria-label="Agregar uno"
                    onClick={() => setCantidad((c) => Math.min(c + 1, producto.stock))}
                  >
                    +
                  </button>
                </div>
              </div>

              <div className="cf-acciones-fila">
                <button className="cf-btn" disabled={agotado} onClick={agregar}>
                  Agregar al carrito
                </button>
                <button
                  className="cf-btn cf-btn--secundario"
                  disabled={agotado}
                  onClick={comprarAhora}
                >
                  Comprar ahora
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
