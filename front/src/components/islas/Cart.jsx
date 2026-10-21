import { useStore } from "../../store/useStore";
import { pesos, RUTAS } from "../../lib/formato";
import { usePedidoPendiente } from "../../hooks/usePedidoPendiente";

/** Cart — lista editable del carrito, subtotal y paso a checkout. */
export default function Cart() {
  const carrito = useStore((s) => s.carrito);
  const cambiarCantidad = useStore((s) => s.cambiarCantidad);
  const quitarDelCarrito = useStore((s) => s.quitarDelCarrito);

  const subtotal = carrito.reduce((acc, i) => acc + i.precio * i.cantidad, 0);
  const { pendiente } = usePedidoPendiente();

  if (carrito.length === 0) {
    return (
      <>
        <h1>Tu carrito</h1>
        <p className="cf-vacio">
          Todavía no agregas nada. Empieza por el catálogo y elige tu café.
        </p>
        <a className="cf-btn" href={RUTAS.inicio}>Ver el catálogo</a>
      </>
    );
  }

  return (
    <>
      <h1>Tu carrito</h1>

      {pendiente && (
        <p className="cf-alerta cf-alerta--warning" role="status">
          <span className="cf-icon" aria-hidden="true">!</span>
          Este carrito ya tiene el pedido {pendiente.referencia} esperando pago. Se vacía en
          cuanto el pago se apruebe.&nbsp;<a href={RUTAS.pedidoDetalle(pendiente.id)}>Ir a pagarlo</a>
        </p>
      )}

      <table className="cf-tabla">
        <thead>
          <tr>
            <th>Producto</th>
            <th>Cantidad</th>
            <th className="cf-num">Precio</th>
            <th className="cf-num">Subtotal</th>
            <th><span className="cf-label">Quitar</span></th>
          </tr>
        </thead>
        <tbody>
          {carrito.map((item) => (
            <tr key={item.id}>
              <td>{item.nombre}</td>
              <td>
                <input
                  className="cf-input"
                  style={{ width: "80px" }}
                  type="number"
                  min="1"
                  max={item.stock}
                  value={item.cantidad}
                  aria-label={`Cantidad de ${item.nombre}`}
                  onChange={(e) => cambiarCantidad(item.id, Number(e.target.value))}
                />
              </td>
              <td className="cf-num">{pesos(item.precio)}</td>
              <td className="cf-num">{pesos(item.precio * item.cantidad)}</td>
              <td>
                <button
                  className="cf-btn cf-btn--icono"
                  aria-label={`Quitar ${item.nombre}`}
                  onClick={() => quitarDelCarrito(item.id)}
                >
                  ✕
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="cf-resumen">
        <span className="cf-total">Subtotal: {pesos(subtotal)}</span>
        <div className="cf-acciones">
          <a className="cf-btn cf-btn--secundario" href={RUTAS.inicio}>
            Seguir comprando
          </a>
          <a className="cf-btn" href={RUTAS.checkout}>
            Continuar al pago
          </a>
        </div>
      </div>
    </>
  );
}
