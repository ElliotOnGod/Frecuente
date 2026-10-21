import { useEffect, useState } from "react";
import { graphqlRequest } from "../../lib/graphql";
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { usePedidoPendiente } from "../../hooks/usePedidoPendiente";
import { useStore } from "../../store/useStore";
import { pesos, RUTAS } from "../../lib/formato";
import { CAMPOS_PEDIDO, QUERY_METODOS, cancelarMiPedido, irAPagar } from "../../lib/pagos";
import { Skeleton } from "./Skeleton";

const MUTATION_PEDIDO = `
  mutation RegistrarPedido($input: PedidoInput!) {
    registrarPedido(input: $input) { ${CAMPOS_PEDIDO} }
  }
`;

/**
 * Checkout — resume el pedido, deja elegir el método de pago y:
 *  1. registra el pedido (registrarPedido: valida y aparta el stock)
 *  2. inicia el cobro (iniciarPago) y manda a la pasarela o a las instrucciones.
 * Pide sesión: el backend toma al usuario del token, no del formulario.
 *
 * El carrito se conserva hasta que el pago se aprueba. Si ya hay un pedido
 * de este carrito esperando pago, no se crea otro (se duplicaría el stock
 * apartado): se ofrece pagarlo o cancelarlo y hacer uno nuevo.
 */

/** Aviso cuando el carrito ya tiene un pedido registrado sin pagar. */
function PedidoSinPagar({ pedido }) {
  const liberarPedido = useStore((s) => s.liberarPedido);
  const carrito = useStore((s) => s.carrito);
  const items = useStore((s) => s.pendienteItems);
  // ¿Cambió el carrito desde que se registró ese pedido?
  const cambio =
    items != null &&
    (items.length !== carrito.length ||
      items.some((p) => carrito.find((i) => i.id === p.id)?.cantidad !== p.cantidad));
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);

  const pagar = async () => {
    setOcupado(true);
    setError(null);
    try {
      await irAPagar(pedido.id);
    } catch (err) {
      setError(err.message);
      setOcupado(false);
    }
  };

  const cancelarYRehacer = async () => {
    setOcupado(true);
    setError(null);
    try {
      await cancelarMiPedido(pedido.id); // el stock apartado regresa al inventario
      liberarPedido(pedido.id); // el carrito queda listo para un pedido nuevo
    } catch (err) {
      setError(err.message);
    }
    setOcupado(false);
  };

  return (
    <>
      <a className="cf-link" href={RUTAS.carrito}>← Volver al carrito</a>
      <h1>Confirma tu pedido</h1>
      <p className="cf-alerta cf-alerta--warning" role="status">
        <span className="cf-icon" aria-hidden="true">!</span>
        Ya registraste el pedido {pedido.referencia} ({pesos(pedido.total)}) con este carrito y
        todavía no está pagado. Tus productos siguen apartados.
      </p>
      {cambio && (
        <p className="cf-alerta" role="note">
          <span className="cf-icon" aria-hidden="true">i</span>
          Tu carrito cambió desde ese pedido. Si pagas ese pedido, lo que agregaste
          después se queda en tu carrito para otra compra. Si prefieres pedir todo
          junto, cancela ese pedido y haz uno nuevo.
        </p>
      )}
      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}
      <div className="cf-panel">
        <div className="cf-acciones cf-acciones--envolver">
          <button className="cf-btn" onClick={pagar} disabled={ocupado}>
            {pedido.pago?.enLinea ? `Pagar ${pesos(pedido.total)} con ${pedido.pago.metodoNombre}` : "Ver cómo pagar"}
          </button>
          <a className="cf-btn cf-btn--secundario" href={RUTAS.pedidoDetalle(pedido.id)}>Ver el pedido</a>
        </div>
        <p className="cf-ayuda">
          ¿Cambiaste tu carrito o quieres otro método de pago?{" "}
          <button className="cf-link" onClick={cancelarYRehacer} disabled={ocupado}>
            Cancelar ese pedido y hacer uno nuevo
          </button>
        </p>
      </div>
    </>
  );
}
export default function Checkout() {
  const sesion = useStore((s) => s.sesion);
  const carrito = useStore((s) => s.carrito);
  const completeCheckout = useStore((s) => s.completeCheckout);
  const { pendiente, cargando } = usePedidoPendiente();

  const { data, loading, error: errorMetodos } = useGraphQLQuery(QUERY_METODOS);
  const metodos = data?.metodosPago ?? [];

  const [metodo, setMetodo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  // Selecciona el primer método en cuanto llegan
  useEffect(() => {
    if (!metodo && metodos.length) setMetodo(metodos[0].clave);
  }, [metodos, metodo]);

  const total = carrito.reduce((acc, i) => acc + i.precio * i.cantidad, 0);
  const elegido = metodos.find((m) => m.clave === metodo);

  const confirmar = async () => {
    setEnviando(true);
    setError(null);
    let pedido;
    try {
      const res = await graphqlRequest(MUTATION_PEDIDO, {
        input: {
          items: carrito.map((i) => ({ productoId: i.id, cantidad: i.cantidad })),
          metodoPago: metodo,
        },
      });
      pedido = res.registrarPedido;
    } catch (err) {
      setError(err.message);
      setEnviando(false);
      return;
    }

    // El pedido ya existe; el carrito se conserva hasta que se apruebe el pago
    completeCheckout(pedido);
    try {
      await irAPagar(pedido.id, metodo);
    } catch {
      // Si la pasarela falló, en la página del pedido se puede reintentar
      window.location.href = RUTAS.pedidoDetalle(pedido.id);
    }
  };

  if (carrito.length === 0) {
    return (
      <>
        <h1>Confirma tu pedido</h1>
        <p className="cf-vacio">Tu carrito está vacío, no hay nada que confirmar.</p>
        <a className="cf-btn" href={RUTAS.inicio}>Ver el catálogo</a>
      </>
    );
  }

  if (!sesion) {
    return (
      <>
        <a className="cf-link" href={RUTAS.carrito}>← Volver al carrito</a>
        <h1>Confirma tu pedido</h1>
        <div className="cf-panel">
          <p style={{ marginTop: 0 }}>
            Para registrar tu pedido necesitas una cuenta. Tu carrito se queda
            como está.
          </p>
          <div className="cf-acciones">
            <a className="cf-btn" href={RUTAS.login(RUTAS.checkout)}>Iniciar sesión</a>
            <a className="cf-btn cf-btn--secundario" href={RUTAS.registro(RUTAS.checkout)}>
              Crear cuenta
            </a>
          </div>
        </div>
      </>
    );
  }

  if (cargando) {
    return (
      <>
        <h1>Confirma tu pedido</h1>
        <div className="cf-panel"><Skeleton alto="80px" /></div>
      </>
    );
  }

  if (pendiente) return <PedidoSinPagar pedido={pendiente} />;

  const textoBoton = enviando
    ? "Procesando…"
    : elegido?.enLinea
      ? `Pagar ${pesos(total)}`
      : "Registrar pedido";

  return (
    <>
      <a className="cf-link" href={RUTAS.carrito}>← Volver al carrito</a>
      <h1>Confirma tu pedido</h1>
      <p className="cf-caption">
        A nombre de {sesion.usuario.nombre} · {sesion.usuario.email}
      </p>

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}

      <div className="cf-checkout">
        <section className="cf-panel" aria-labelledby="titulo-metodo">
          <h2 id="titulo-metodo" className="cf-panel__titulo">Método de pago</h2>

          {loading && (
            <div className="cf-metodos">
              {[1, 2, 3, 4].map((n) => <Skeleton key={n} alto="72px" />)}
            </div>
          )}

          {errorMetodos && (
            <p className="cf-alerta cf-alerta--error" role="alert">
              <span className="cf-icon" aria-hidden="true">!</span>
              No se pudieron cargar los métodos de pago: {errorMetodos}
            </p>
          )}

          {!loading && metodos.length > 0 && (
            <fieldset className="cf-metodos">
              <legend className="cf-sr">Elige cómo quieres pagar</legend>
              {metodos.map((m) => (
                <label
                  key={m.clave}
                  className="cf-metodo"
                  data-elegido={metodo === m.clave ? "true" : undefined}
                >
                  <input
                    type="radio"
                    name="metodo"
                    value={m.clave}
                    checked={metodo === m.clave}
                    onChange={() => setMetodo(m.clave)}
                  />
                  <span className="cf-metodo__texto">
                    <strong>{m.nombre}</strong>
                    <span className="cf-caption">{m.descripcion}</span>
                  </span>
                  {m.enLinea && m.modo !== "sandbox" && (
                    <span className="cf-estado cf-estado--info">Prueba</span>
                  )}
                  {m.modo === "sandbox" && (
                    <span className="cf-estado cf-estado--info">Sandbox</span>
                  )}
                </label>
              ))}
            </fieldset>
          )}

          {elegido && (
            <p className="cf-ayuda">
              {elegido.enLinea
                ? `Te llevaremos a ${elegido.nombre} para completar el pago de forma segura. Tu pedido se confirma en cuanto se apruebe.`
                : elegido.clave === "transferencia"
                  ? "Al registrar el pedido te mostramos la CLABE y la referencia. Lo confirmamos al ver tu depósito."
                  : "Apartamos tus productos y pagas en el local al recogerlos con tu referencia."}
            </p>
          )}
        </section>

        <section className="cf-panel" aria-labelledby="titulo-resumen">
          <h2 id="titulo-resumen" className="cf-panel__titulo">Tu pedido</h2>
          <table className="cf-tabla">
            <thead>
              <tr>
                <th>Producto</th>
                <th className="cf-num">Cantidad</th>
                <th className="cf-num">Subtotal</th>
              </tr>
            </thead>
            <tbody>
              {carrito.map((i) => (
                <tr key={i.id}>
                  <td>{i.nombre}</td>
                  <td className="cf-num">{i.cantidad}</td>
                  <td className="cf-num">{pesos(i.precio * i.cantidad)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="cf-resumen">
            <span className="cf-total">Total: {pesos(total)}</span>
            <button
              className="cf-btn"
              onClick={confirmar}
              disabled={enviando || !metodo}
            >
              {textoBoton}
            </button>
          </div>
        </section>
      </div>
    </>
  );
}
