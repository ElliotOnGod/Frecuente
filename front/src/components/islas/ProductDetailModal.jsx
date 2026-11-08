import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { useStore } from "../../store/useStore";
import { Skeleton } from "./Skeleton";
import { pesos, RUTAS } from "../../lib/formato";
import Foto from "./Foto";

const NOMBRE_METODO = {
  espresso: "Espresso y latte",
  filtro: "V60 / Chemex",
  prensa: "Prensa francesa",
  goteo: "Cafetera de goteo",
  frio: "Bebidas frías",
  batido: "Matcha batido",
};

/** Variantes (molienda) como botones de opción: mismo precio y stock. */
function SelectorVariante({ producto, valor, onElegir }) {
  if (!producto.variantes?.length) return null;
  return (
    <fieldset className="cf-variantes">
      <legend className="cf-label">{producto.varianteNombre || "Presentación"}</legend>
      <div className="cf-chips">
        {producto.variantes.map((v) => (
          <label key={v} className="cf-chip" data-elegido={valor === v ? "true" : undefined}>
            <input type="radio" name="variante" value={v} checked={valor === v} onChange={() => onElegir(v)} />
            {v}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

const QUERY_PRODUCTO = `
  query Producto($id: Int!) {
    producto(id: $id) {
      id nombre descripcion precio stock categoriaId imagenUrl imagenes
      varianteNombre variantes metodos pesoKg
      categoria { nombre }
    }
  }
`;

/**
 * Galería del modal: foto grande + miniaturas para cambiarla.
 * Con una sola foto (o ninguna) solo se ve la grande.
 */
function Galeria({ producto, actual, onElegir }) {
  const fotos = producto.imagenes?.length ? producto.imagenes : [producto.imagenUrl].filter(Boolean);
  const i = Math.min(actual, Math.max(0, fotos.length - 1));

  return (
    <div className="cf-galeria">
      <Foto
        key={fotos[i] || "sin-foto"}
        src={fotos[i]}
        alt={fotos.length > 1 ? `${producto.nombre}, foto ${i + 1} de ${fotos.length}` : producto.nombre}
        categoriaId={producto.categoriaId}
        ancho={640}
        className="cf-figura--alta"
        prioridad
      />
      {fotos.length > 1 && (
        <div className="cf-galeria__miniaturas" role="group" aria-label="Fotos del producto">
          {fotos.map((url, n) => (
            <button
              key={url}
              type="button"
              className="cf-galeria__mini"
              aria-label={`Ver foto ${n + 1}`}
              aria-pressed={n === i}
              onClick={() => onElegir(n)}
            >
              <Foto src={url} alt="" categoriaId={producto.categoriaId} ancho={120} prioridad />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

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
  const [foto, setFoto] = useState(0);
  const [variante, setVariante] = useState("");

  const { data, loading, error } = useGraphQLQuery(
    QUERY_PRODUCTO,
    { id: id ?? 0 },
    { omitir: id === null }
  );
  const producto = data?.producto;

  useEffect(() => {
    setCantidad(1);
    setFoto(0);
    setVariante("");
  }, [id]);

  // Al cargar, la primera variante queda elegida (ej. "Grano entero")
  useEffect(() => {
    if (producto?.variantes?.length && !producto.variantes.includes(variante)) setVariante(producto.variantes[0]);
  }, [producto, variante]);

  useEffect(() => {
    const onEsc = (e) => e.key === "Escape" && closeProduct();
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [closeProduct]);

  if (id === null) return null;

  const agotado = producto ? producto.stock <= 0 : false;

  const agregar = () => {
    agregarAlCarrito(producto, cantidad, variante);
    closeProduct();
  };

  const comprarAhora = () => {
    agregarAlCarrito(producto, cantidad, variante);
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
            <Galeria producto={producto} actual={foto} onElegir={setFoto} />

            <div>
              <p className="cf-caption">{producto.categoria?.nombre}</p>
              <p>{producto.descripcion}</p>
              {producto.metodos?.length > 0 && (
                <p className="cf-metodos-prep">
                  <span className="cf-caption">Ideal para: </span>
                  {producto.metodos.map((m) => (
                    <a key={m} className="cf-etiqueta" href={RUTAS.tiendaMetodo(m)}>{NOMBRE_METODO[m] ?? m}</a>
                  ))}
                </p>
              )}
              <p className="cf-card__precio">{pesos(producto.precio)}</p>

              <span className={`cf-insignia${agotado ? " cf-insignia--agotado" : ""}`}>
                {agotado ? "Agotado" : `${producto.stock} disponibles`}
              </span>

              <SelectorVariante producto={producto} valor={variante} onElegir={setVariante} />

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
