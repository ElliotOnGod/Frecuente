import { useEffect, useRef, useState } from "react";
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { useSuscripcion } from "../../hooks/useSuscripcion";
import { estaPagado } from "../../hooks/usePedidoPendiente";
import { useStore } from "../../store/useStore";
import { fechaCorta, pesos, RUTAS } from "../../lib/formato";
import { QUERY_METODOS, QUERY_PEDIDO, SUB_SEGUIR_PEDIDO, cancelarMiPedido, confirmarPago, irAPagar } from "../../lib/pagos";
import { EstadoPago, EstadoPedido, IndicadorEnVivo } from "./Insignia";
import { Skeleton } from "./Skeleton";

/** Mensaje principal según el estado del pedido y de su pago. */
function Aviso({ pedido }) {
  const pago = pedido.pago;
  if (pedido.estado === "cancelado") {
    return (
      <p className="cf-alerta" role="status">
        <span className="cf-icon" aria-hidden="true">i</span>
        Este pedido está cancelado.
        {pago?.estado === "por_reembolsar" && " Te regresaremos tu pago en los próximos días."}
        {pago?.estado === "reembolsado" && " Tu pago ya fue reembolsado."}
      </p>
    );
  }
  if (!pago || pago.estado === "aprobado") {
    return (
      <p className="cf-alerta cf-alerta--success" role="status">
        <span className="cf-icon" aria-hidden="true">✓</span>
        {pago ? "Pago aprobado. " : "Pedido registrado. "}
        Te escribimos por correo para coordinar la entrega.
      </p>
    );
  }
  if (pago.estado === "rechazado") {
    return (
      <p className="cf-alerta cf-alerta--error" role="alert">
        <span className="cf-icon" aria-hidden="true">!</span>
        El pago no se aprobó. Tus productos siguen apartados: puedes intentar
        de nuevo o elegir otro método.
      </p>
    );
  }
  if (!pago.enLinea) {
    return (
      <p className="cf-alerta cf-alerta--warning" role="status">
        <span className="cf-icon" aria-hidden="true">!</span>
        {pago.metodo === "transferencia"
          ? "Pedido registrado. Haz tu transferencia con estos datos y lo confirmamos al ver el depósito."
          : "Pedido apartado. Pásalo a recoger y paga en el local con tu referencia."}
      </p>
    );
  }
  return (
    <p className="cf-alerta cf-alerta--warning" role="status">
      <span className="cf-icon" aria-hidden="true">!</span>
      Tu pago está pendiente. Si ya pagaste, puede tardar unos minutos en
      reflejarse; si no, puedes completarlo ahora.
    </p>
  );
}

/**
 * OrderSuccess — /pedido?id=N. Muestra el pedido con el estado de su pago,
 * las instrucciones para transferencia/efectivo y deja reintentar el cobro,
 * cambiar de método o cancelar mientras no esté pagado.
 */
export default function OrderSuccess() {
  const sesion = useStore((s) => s.sesion);
  const ultimo = useStore((s) => s.pedido);

  const idUrl = Number(new URLSearchParams(window.location.search).get("id"));
  const id = idUrl || ultimo?.id || null;

  const consulta = useGraphQLQuery(QUERY_PEDIDO, { id }, { omitir: !id || !sesion });
  const { data: dataMetodos } = useGraphQLQuery(QUERY_METODOS);

  // Copia local para reflejar cambios (cancelar) sin volver a consultar
  const [editado, setPedido] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const [otroMetodo, setOtroMetodo] = useState("");
  const [confirmarCancelar, setConfirmarCancelar] = useState(false);

  // En vivo: si la tienda confirma tu transferencia o envía el pedido,
  // la página cambia sola (Subscription seguirPedido).
  // Gana el dato más reciente: lo que llega en vivo o lo que cambiamos aquí
  // (cancelar, revisar el pago), en el orden en que pasa.
  const vivo = useSuscripcion(SUB_SEGUIR_PEDIDO, { id }, { omitir: !id || !sesion });
  useEffect(() => {
    if (vivo.dato?.seguirPedido) setPedido(vivo.dato.seguirPedido);
  }, [vivo.dato]);
  const pedido = editado ?? consulta.data?.pedido ?? null;

  // El carrito se vacía hasta que el pago se aprueba (aunque lo apruebe la
  // tienda mientras el cliente tiene esta página abierta). Si se cancela,
  // el carrito se queda para volver a intentarlo.
  const pagoConfirmado = useStore((s) => s.pagoConfirmado);
  const liberarPedido = useStore((s) => s.liberarPedido);
  useEffect(() => {
    if (!pedido) return;
    if (estaPagado(pedido)) pagoConfirmado(pedido.id);
    else if (pedido.estado === "cancelado") liberarPedido(pedido.id);
  }, [pedido, pagoConfirmado, liberarPedido]);

  // Mercado Pago / PayPal reales (sandbox): si el cliente pagó pero no
  // regresó a la tienda (cerró la pestaña, no dio "Volver al sitio"…), el
  // pago se queda "pendiente" aquí. Al abrir el pedido se le pregunta UNA vez
  // a la pasarela, y también hay un botón para volver a revisar.
  const [revisando, setRevisando] = useState(false);
  const yaReviso = useRef(false);
  const revisable =
    pedido?.estado === "registrado" &&
    pedido?.pago?.enLinea &&
    pedido?.pago?.modo === "sandbox" &&
    pedido?.pago?.estado === "pendiente";

  const revisarPago = async () => {
    setRevisando(true);
    setError(null);
    try {
      setPedido(await confirmarPago({ pedidoId: pedido.id }));
    } catch (err) {
      setError(err.message);
    }
    setRevisando(false);
  };

  useEffect(() => {
    if (!revisable || yaReviso.current) return;
    yaReviso.current = true;
    revisarPago();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revisable]);

  if (!id) {
    return (
      <>
        <h1>Sin pedidos recientes</h1>
        <p className="cf-vacio">Aquí verás la confirmación cuando registres un pedido.</p>
        <a className="cf-btn" href={RUTAS.inicio}>Ver el catálogo</a>
      </>
    );
  }

  if (!sesion) {
    return (
      <>
        <h1>Pedido #{id}</h1>
        <p className="cf-vacio">Inicia sesión para ver el estado de tu pedido.</p>
        <a className="cf-btn" href={RUTAS.login(RUTAS.pedidoDetalle(id))}>Iniciar sesión</a>
      </>
    );
  }

  if (consulta.loading) {
    return (
      <>
        <h1>Pedido #{id}</h1>
        <div className="cf-panel">
          <Skeleton alto="20px" />
          <div style={{ height: "var(--espacio-md)" }} />
          <Skeleton alto="20px" ancho="70%" />
        </div>
      </>
    );
  }

  if (consulta.error || !pedido) {
    return (
      <>
        <h1>Pedido #{id}</h1>
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span>
          {consulta.error || "No encontramos este pedido en tu cuenta."}
        </p>
        <a className="cf-btn cf-btn--secundario" href={RUTAS.cuenta}>Ver mis pedidos</a>
      </>
    );
  }

  const pago = pedido.pago;
  const porPagar = pedido.estado === "registrado" && pago && pago.estado !== "aprobado";
  const metodos = (dataMetodos?.metodosPago ?? []).filter((m) => m.clave !== pago?.metodo);

  const pagar = async (metodo = null) => {
    setOcupado(true);
    setError(null);
    try {
      await irAPagar(pedido.id, metodo);
    } catch (err) {
      setError(err.message);
      setOcupado(false);
    }
  };

  const cancelar = async () => {
    setOcupado(true);
    setError(null);
    try {
      setPedido(await cancelarMiPedido(pedido.id));
      setConfirmarCancelar(false);
    } catch (err) {
      setError(err.message);
    }
    setOcupado(false);
  };

  return (
    <>
      <Aviso pedido={pedido} />

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}

      <div className="cf-resumen" style={{ marginTop: 0 }}>
        <div>
          <h1 style={{ margin: 0 }}>Pedido #{pedido.id}</h1>
          <p className="cf-caption" style={{ margin: 0 }}>
            {fechaCorta(pedido.fecha)} · referencia {pedido.referencia}
          </p>
        </div>
        <div className="cf-acciones cf-acciones--envolver">
          <IndicadorEnVivo estado={vivo.estado} />
          <EstadoPedido estado={pedido.estado} />
        </div>
      </div>

      {pago && (
        <div className="cf-panel cf-datos">
          <div>
            <span className="cf-caption">Método de pago</span>
            <p>{pago.metodoNombre}</p>
          </div>
          <div>
            <span className="cf-caption">Estado del pago</span>
            <p><EstadoPago estado={pago.estado} /></p>
          </div>
          <div>
            <span className="cf-caption">
              {pago.fechaPago ? "Pagado el" : "Total a pagar"}
            </span>
            <p>{pago.fechaPago ? fechaCorta(pago.fechaPago) : pesos(pedido.total)}</p>
          </div>
        </div>
      )}

      {porPagar && pago.instrucciones.length > 0 && (
        <section className="cf-panel cf-instrucciones" aria-labelledby="titulo-instr">
          <h2 id="titulo-instr" className="cf-panel__titulo">
            {pago.metodo === "transferencia" ? "Datos para tu transferencia" : "Para recoger tu pedido"}
          </h2>
          <dl>
            {pago.instrucciones.map((d) => (
              <div key={d.etiqueta}>
                <dt className="cf-caption">{d.etiqueta}</dt>
                <dd>{d.valor}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {porPagar && (
        <section className="cf-panel" aria-label="Opciones de pago">
          {revisable && (
            <p className="cf-ayuda" style={{ marginTop: 0 }}>
              ¿Ya pagaste en {pago.metodoNombre}?{" "}
              <button className="cf-link" onClick={revisarPago} disabled={revisando || ocupado}>
                {revisando ? "Revisando…" : "Revisar mi pago"}
              </button>
            </p>
          )}
          <div className="cf-acciones cf-acciones--envolver">
            {pago.enLinea && (
              <button className="cf-btn" onClick={() => pagar()} disabled={ocupado}>
                {pago.estado === "rechazado" ? "Intentar de nuevo" : "Pagar ahora"} con{" "}
                {pago.metodoNombre}
              </button>
            )}

            {metodos.length > 0 && (
              <div className="cf-cambiar-metodo">
                <label className="cf-label" htmlFor="otro-metodo">Pagar con otro método</label>
                <div className="cf-acciones">
                  <select
                    id="otro-metodo"
                    className="cf-input"
                    value={otroMetodo}
                    onChange={(e) => setOtroMetodo(e.target.value)}
                  >
                    <option value="">Elige…</option>
                    {metodos.map((m) => (
                      <option key={m.clave} value={m.clave}>{m.nombre}</option>
                    ))}
                  </select>
                  <button
                    className="cf-btn cf-btn--secundario"
                    disabled={!otroMetodo || ocupado}
                    onClick={() => pagar(otroMetodo)}
                  >
                    Cambiar
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="cf-cancelar">
            {!confirmarCancelar ? (
              <button className="cf-link" onClick={() => setConfirmarCancelar(true)} disabled={ocupado}>
                Cancelar este pedido
              </button>
            ) : (
              <div className="cf-acciones cf-acciones--envolver" role="group" aria-label="Confirmar cancelación">
                <span>¿Seguro? Los productos regresan al inventario.</span>
                <button className="cf-btn cf-btn--peligro" onClick={cancelar} disabled={ocupado}>
                  Sí, cancelar
                </button>
                <button className="cf-btn cf-btn--secundario" onClick={() => setConfirmarCancelar(false)}>
                  No
                </button>
              </div>
            )}
          </div>
        </section>
      )}

      <div className="cf-panel">
        <table className="cf-tabla">
          <thead>
            <tr>
              <th>Producto</th>
              <th className="cf-num">Cantidad</th>
              <th className="cf-num">Subtotal</th>
            </tr>
          </thead>
          <tbody>
            {pedido.items?.map((item, i) => (
              <tr key={i}>
                <td>{item.producto?.nombre}</td>
                <td className="cf-num">{item.cantidad}</td>
                <td className="cf-num">{pesos(item.subtotal)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="cf-resumen">
          <span className="cf-total">Total: {pesos(pedido.total ?? 0)}</span>
          <div className="cf-acciones">
            <a className="cf-btn cf-btn--secundario" href={RUTAS.cuenta}>Ver mis pedidos</a>
            <a className="cf-btn" href={RUTAS.inicio}>Volver al inicio</a>
          </div>
        </div>
      </div>
    </>
  );
}
