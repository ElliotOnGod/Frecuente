import { useEffect, useState } from "react";
import { graphqlRequest } from "../../lib/graphql";
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { usePedidoPendiente } from "../../hooks/usePedidoPendiente";
import { useStore } from "../../store/useStore";
import { pesos, RUTAS } from "../../lib/formato";
import { CAMPOS_PEDIDO, QUERY_METODOS, cancelarMiPedido, irAPagar } from "../../lib/pagos";
import { claveDe, itemsParaApi, subtotalDe } from "../../lib/carrito";
import { DIRECCION_VACIA, entregaParaApi, faltantes } from "../../lib/envios";
import EntregaForm from "./EntregaForm";
import { Skeleton } from "./Skeleton";

// Última dirección usada: comodidad de este navegador, no un dato importante
const LLAVE_DIRECCION = "frecuente-direccion";
function direccionGuardada(usuario) {
  try {
    const guardada = JSON.parse(window.localStorage.getItem(LLAVE_DIRECCION) || "null");
    if (guardada) return { ...DIRECCION_VACIA, ...guardada };
  } catch {
    // sin almacenamiento (modo privado): se empieza vacío
  }
  return { ...DIRECCION_VACIA, nombre: usuario?.nombre ?? "", telefono: usuario?.telefono ?? "" };
}
function guardarDireccion(direccion) {
  try {
    window.localStorage.setItem(LLAVE_DIRECCION, JSON.stringify(direccion));
  } catch {
    // no pasa nada si no se puede guardar
  }
}

const MUTATION_PEDIDO = `
  mutation RegistrarPedido($input: PedidoInput!) {
    registrarPedido(input: $input) { ${CAMPOS_PEDIDO} }
  }
`;

/**
 * Checkout — resume el pedido, deja elegir la entrega (recoger o envío a
 * domicilio con Envia.com), el método de pago y si se repite cada mes, y:
 *  1. registra el pedido (registrarPedido: valida y aparta el stock; el
 *     costo del envío lo pone el servidor con la cotización firmada)
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
      items.some((p) => carrito.find((i) => claveDe(i) === (p.clave ?? `${p.id}|`))?.cantidad !== p.cantidad));
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
  const [entrega, setEntrega] = useState(() => ({
    tipo: "recoger",
    direccion: direccionGuardada(sesion?.usuario),
    opcion: null,
  }));
  const [recompra, setRecompra] = useState({ activa: false, dias: 30 });

  const aDomicilio = entrega.tipo === "domicilio";
  // Efectivo es solo al recoger; la recompra se paga en línea o por transferencia
  const disponibles = metodos.filter(
    (m) => !(m.clave === "efectivo" && (aDomicilio || recompra.activa))
  );

  // Selecciona el primer método disponible (y cambia si el elegido ya no aplica)
  useEffect(() => {
    if (disponibles.length && !disponibles.some((m) => m.clave === metodo)) setMetodo(disponibles[0].clave);
  }, [disponibles, metodo]);

  const items = itemsParaApi(carrito);
  const subtotal = subtotalDe(carrito);
  const costoEnvio = aDomicilio ? entrega.opcion?.costo ?? 0 : 0;
  const total = Math.round((subtotal + costoEnvio) * 100) / 100;
  const elegido = disponibles.find((m) => m.clave === metodo);
  const faltaEntrega = aDomicilio
    ? [...faltantes(entrega.direccion), ...(entrega.opcion ? [] : ["paquetería"])]
    : [];

  const confirmar = async () => {
    if (faltaEntrega.length) {
      setError(`Completa la entrega: ${faltaEntrega.join(", ")}`);
      return;
    }
    setEnviando(true);
    setError(null);
    let pedido;
    try {
      const res = await graphqlRequest(MUTATION_PEDIDO, {
        input: {
          items,
          metodoPago: metodo,
          entrega: entregaParaApi(entrega.tipo, entrega.direccion, entrega.opcion),
          recompraCadaDias: recompra.activa ? recompra.dias : null,
        },
      });
      pedido = res.registrarPedido;
    } catch (err) {
      setError(err.message);
      setEnviando(false);
      return;
    }
    if (aDomicilio) guardarDireccion(entrega.direccion);

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
        <div className="cf-checkout__pasos">
        <EntregaForm valor={entrega} onCambio={setEntrega} items={items} />

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
              {disponibles.map((m) => (
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
          {aDomicilio && (
            <p className="cf-caption">El pago en efectivo solo aplica al recoger en el local.</p>
          )}
        </section>

        <section className="cf-panel" aria-labelledby="titulo-recompra">
          <h2 id="titulo-recompra" className="cf-panel__titulo">Recompra automática</h2>
          <label className="cf-check">
            <input
              type="checkbox"
              checked={recompra.activa}
              onChange={(e) => setRecompra((r) => ({ ...r, activa: e.target.checked }))}
            />
            <span>Repetir este pedido automáticamente</span>
          </label>
          {recompra.activa && (
            <div className="cf-campo" style={{ marginTop: "var(--espacio-sm)" }}>
              <label className="cf-label" htmlFor="recompra-dias">Cada cuánto</label>
              <select
                id="recompra-dias"
                className="cf-input"
                value={recompra.dias}
                onChange={(e) => setRecompra((r) => ({ ...r, dias: Number(e.target.value) }))}
              >
                <option value={15}>Cada 15 días</option>
                <option value={30}>Cada mes (30 días)</option>
                <option value={60}>Cada 2 meses (60 días)</option>
              </select>
            </div>
          )}
          <p className="cf-ayuda">
            {recompra.activa
              ? `Cada ${recompra.dias} días generamos este mismo pedido y te mandamos un correo con el enlace para pagarlo. Puedes pausarlo o cancelarlo en Mi cuenta.`
              : "Ideal para tu café de siempre: no guardamos tu tarjeta, solo te recordamos y preparamos el pedido."}
          </p>
        </section>
        </div>

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
                <tr key={claveDe(i)}>
                  <td>
                    {i.nombre}
                    {i.variante && <span className="cf-caption cf-bloque">{i.variante}</span>}
                  </td>
                  <td className="cf-num">{i.cantidad}</td>
                  <td className="cf-num">{pesos(i.precio * i.cantidad)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <dl className="cf-totales">
            <div><dt>Productos</dt><dd>{pesos(subtotal)}</dd></div>
            <div>
              <dt>Envío</dt>
              <dd>
                {!aDomicilio ? "Recoges en el local" : entrega.opcion ? pesos(costoEnvio) : "Por cotizar"}
              </dd>
            </div>
          </dl>

          <div className="cf-resumen">
            <span className="cf-total">Total: {pesos(total)}</span>
            <button
              className="cf-btn"
              onClick={confirmar}
              disabled={enviando || !metodo || (aDomicilio && !entrega.opcion)}
            >
              {textoBoton}
            </button>
          </div>
        </section>
      </div>
    </>
  );
}
