import { useEffect, useRef, useState } from "react";
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { useSuscripcion } from "../../hooks/useSuscripcion";
import { useStore } from "../../store/useStore";
import { RUTAS, fechaCorta, fechaLarga, hora, pesos } from "../../lib/formato";
import { QUERY_METODOS } from "../../lib/pagos";
import {
  QUERY_MI_MEMBRESIA,
  SUB_SEGUIR_MEMBRESIA,
  cancelarMiMembresia,
  confirmarPagoMembresia,
  irAPagarMembresia,
} from "../../lib/membresias";
import { EstadoMembresia, EstadoPago, IndicadorEnVivo } from "./Insignia";
import { Skeleton } from "./Skeleton";

/** Tarjeta grande con el código del día (lo que se enseña en caja). */
function CodigoDelDia({ m, estadoVivo }) {
  const usadoHoy = m.canjeHoy;
  return (
    <section className="cf-codigo" data-usado={usadoHoy ? "true" : undefined} aria-labelledby="titulo-codigo">
      <div className="cf-codigo__barra">
        <h2 id="titulo-codigo" className="cf-panel__titulo">Tu código de hoy</h2>
        <IndicadorEnVivo estado={estadoVivo} />
      </div>

      <p className="cf-codigo__valor" aria-label={`Código ${m.codigoHoy?.split("").join(" ")}`}>
        {m.codigoHoy}
      </p>

      {usadoHoy ? (
        <p className="cf-alerta cf-alerta--success" role="status">
          <span className="cf-icon" aria-hidden="true">✓</span>
          Ya canjeaste hoy: <strong>&nbsp;{usadoHoy.opcion}</strong>&nbsp;a las {hora(usadoHoy.fecha)} —
          mañana tienes un código nuevo.
        </p>
      ) : (
        <p className="cf-codigo__ayuda">
          Enséñalo en caja para canjear tu beneficio de hoy. Cambia cada día y solo sirve una vez.
        </p>
      )}
    </section>
  );
}

/** Pago pendiente: instrucciones, pagar ahora, cambiar de método o cancelar. */
function PagoPendiente({ m, onCambio }) {
  const { data } = useGraphQLQuery(QUERY_METODOS);
  const [otro, setOtro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const [confirmar, setConfirmar] = useState(false);
  const pago = m.pago;
  const metodos = (data?.metodosPago ?? []).filter((x) => x.clave !== pago?.metodo);

  const pagar = async (metodo = null) => {
    setOcupado(true);
    setError(null);
    try {
      await irAPagarMembresia(m.id, metodo);
    } catch (err) {
      setError(err.message);
      setOcupado(false);
    }
  };

  // Mercado Pago / PayPal reales (sandbox): si pagaste pero no regresaste a
  // la tienda, se le pregunta a la pasarela una vez al abrir esta página
  // (y hay un botón para volver a revisar).
  const revisable = pago?.enLinea && pago?.modo === "sandbox" && pago?.estado === "pendiente";
  const yaReviso = useRef(false);
  const revisarPago = async () => {
    setOcupado(true);
    setError(null);
    try {
      await confirmarPagoMembresia({ membresiaId: m.id });
      onCambio();
    } catch (err) {
      setError(err.message);
    }
    setOcupado(false);
  };
  useEffect(() => {
    if (!revisable || yaReviso.current) return;
    yaReviso.current = true;
    revisarPago();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revisable]);

  const cancelar = async () => {
    setOcupado(true);
    try {
      await cancelarMiMembresia(m.id);
      onCambio();
    } catch (err) {
      setError(err.message);
    }
    setOcupado(false);
  };

  return (
    <>
      <p
        className={`cf-alerta ${pago?.estado === "rechazado" ? "cf-alerta--error" : "cf-alerta--warning"}`}
        role="status"
      >
        <span className="cf-icon" aria-hidden="true">!</span>
        {pago?.estado === "rechazado"
          ? "El pago no se aprobó. Puedes intentarlo de nuevo o elegir otro método."
          : pago?.enLinea
            ? "Tu membresía se activa en cuanto se apruebe el pago."
            : pago?.metodo === "transferencia"
              ? "Haz tu transferencia con estos datos; la activamos al ver el depósito."
              : "Paga en caja con tu referencia y la activamos al momento."}
      </p>

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}

      {!pago?.enLinea && pago?.instrucciones?.length > 0 && (
        <section className="cf-panel cf-instrucciones" aria-label="Datos para pagar">
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

      <section className="cf-panel" aria-label="Opciones de pago">
        {revisable && (
          <p className="cf-ayuda" style={{ marginTop: 0 }}>
            ¿Ya pagaste en {pago.metodoNombre}?{" "}
            <button className="cf-link" onClick={revisarPago} disabled={ocupado}>
              Revisar mi pago
            </button>
          </p>
        )}
        <div className="cf-acciones cf-acciones--envolver">
          {pago?.enLinea && (
            <button className="cf-btn" onClick={() => pagar()} disabled={ocupado}>
              Pagar {pesos(m.precio)} con {pago.metodoNombre}
            </button>
          )}
          {metodos.length > 0 && (
            <div className="cf-cambiar-metodo">
              <label className="cf-label" htmlFor="memb-otro">Pagar con otro método</label>
              <div className="cf-acciones">
                <select id="memb-otro" className="cf-input" value={otro} onChange={(e) => setOtro(e.target.value)}>
                  <option value="">Elige…</option>
                  {metodos.map((x) => (
                    <option key={x.clave} value={x.clave}>
                      {x.clave === "efectivo" ? "Efectivo en el local" : x.nombre}
                    </option>
                  ))}
                </select>
                <button className="cf-btn cf-btn--secundario" disabled={!otro || ocupado} onClick={() => pagar(otro)}>
                  Cambiar
                </button>
              </div>
            </div>
          )}
        </div>
        <div className="cf-cancelar">
          {!confirmar ? (
            <button className="cf-link" onClick={() => setConfirmar(true)} disabled={ocupado}>
              Cancelar esta membresía
            </button>
          ) : (
            <div className="cf-acciones cf-acciones--envolver" role="group" aria-label="Confirmar cancelación">
              <span>¿Seguro que quieres cancelarla?</span>
              <button className="cf-btn cf-btn--peligro" onClick={cancelar} disabled={ocupado}>Sí, cancelar</button>
              <button className="cf-btn cf-btn--secundario" onClick={() => setConfirmar(false)}>No</button>
            </div>
          )}
        </div>
      </section>
    </>
  );
}

/**
 * MiMembresia — /mi-membresia. Código del día (en vivo: se marca como
 * usado en cuanto la caja registra el canje), beneficios, días que quedan,
 * historial de canjes y, si falta pagar, las opciones de pago.
 */
export default function MiMembresia() {
  const sesion = useStore((s) => s.sesion);
  const [recarga, setRecarga] = useState(0);
  const { data, loading, error } = useGraphQLQuery(QUERY_MI_MEMBRESIA, {}, { omitir: !sesion, recarga });

  const base = data?.miMembresia;
  // Subscription: la versión en vivo de la membresía reemplaza a la de la consulta
  const vivo = useSuscripcion(SUB_SEGUIR_MEMBRESIA, { id: base?.id }, { omitir: !base?.id });
  const m = vivo.dato?.seguirMembresia ?? base;
  const historial = data?.misMembresias ?? [];

  if (!sesion) {
    return (
      <>
        <h1>Mi membresía</h1>
        <p className="cf-vacio">Inicia sesión para ver tu membresía y tu código del día.</p>
        <a className="cf-btn" href={RUTAS.login(RUTAS.miMembresia)}>Iniciar sesión</a>
      </>
    );
  }

  if (loading && !data) {
    return (
      <>
        <h1>Mi membresía</h1>
        <div className="cf-panel"><Skeleton alto="120px" /></div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <h1>Mi membresía</h1>
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      </>
    );
  }

  if (!m || m.estado === "cancelada" || m.estado === "vencida") {
    return (
      <>
        <h1>Mi membresía</h1>
        {m && (
          <p className="cf-alerta" role="status">
            <span className="cf-icon" aria-hidden="true">i</span>
            Tu membresía {m.plan?.nombre} {m.estado === "vencida" ? `venció el ${fechaLarga(m.fin)}` : "fue cancelada"}.
          </p>
        )}
        <p className="cf-vacio">
          Con una membresía tienes tu café (o café con comida) todos los días en el local.
        </p>
        <a className="cf-btn" href={RUTAS.membresias}>Ver planes</a>
      </>
    );
  }

  const progreso = m.estado === "activa" ? Math.max(0, Math.min(100, ((30 - m.diasRestantes) / 30) * 100)) : 0;
  const programada = historial.find((x) => x.estado === "programada" && x.id !== m.id);

  return (
    <>
      <div className="cf-resumen" style={{ marginTop: 0 }}>
        <div>
          <h1 style={{ margin: 0 }}>Mi membresía</h1>
          <p className="cf-caption" style={{ margin: 0 }}>
            {m.plan?.nombre} · {m.referencia}
          </p>
        </div>
        <EstadoMembresia estado={m.estado} />
      </div>

      {m.estado === "pendiente" && (
        <PagoPendiente m={m} onCambio={() => setRecarga((n) => n + 1)} />
      )}

      {m.estado === "activa" && m.codigoHoy && <CodigoDelDia m={m} estadoVivo={vivo.estado} />}

      <div className="cf-admin__dos">
        <section className="cf-panel" aria-labelledby="titulo-plan">
          <h2 id="titulo-plan" className="cf-panel__titulo">Tu plan: {m.plan?.nombre}</h2>
          <ul className="cf-plan__incluye">
            {m.plan?.incluye.map((x) => <li key={x}>{x}</li>)}
          </ul>
          <dl className="cf-detalle__datos">
            <div>
              <dt className="cf-caption">Precio</dt>
              <dd>{pesos(m.precio)} / 30 días</dd>
            </div>
            <div>
              <dt className="cf-caption">Pago</dt>
              <dd>{m.pago?.metodoNombre} · <EstadoPago estado={m.pago?.estado} /></dd>
            </div>
            {m.inicio && (
              <div>
                <dt className="cf-caption">Vigencia</dt>
                <dd>{fechaLarga(m.inicio)} – {fechaLarga(m.fin)}</dd>
              </div>
            )}
          </dl>
          {m.estado === "activa" && (
            <>
              <div
                className="cf-progreso"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={30}
                aria-valuenow={30 - m.diasRestantes}
                aria-label="Días usados de la membresía"
              >
                <span style={{ width: `${progreso}%` }} />
              </div>
              <p className="cf-caption">
                Te quedan <strong>{m.diasRestantes}</strong> día{m.diasRestantes === 1 ? "" : "s"} ·{" "}
                {m.canjesTotal} canje{m.canjesTotal === 1 ? "" : "s"} usados
              </p>
              {programada ? (
                <p className="cf-caption">
                  Renovación pagada: {programada.plan?.nombre} empieza el {fechaLarga(programada.inicio)}.
                </p>
              ) : (
                <a className="cf-link" href={RUTAS.membresias}>Renovar o cambiar de plan</a>
              )}
            </>
          )}
        </section>

        <section className="cf-panel" aria-labelledby="titulo-canjes">
          <h2 id="titulo-canjes" className="cf-panel__titulo">Tus canjes</h2>
          {m.canjes.length === 0 ? (
            <p className="cf-caption">Todavía no has canjeado tu beneficio.</p>
          ) : (
            <table className="cf-tabla">
              <thead>
                <tr>
                  <th>Día</th>
                  <th>Hora</th>
                  <th>Canjeaste</th>
                </tr>
              </thead>
              <tbody>
                {m.canjes.map((c) => (
                  <tr key={c.dia}>
                    <td className="cf-nowrap">{fechaLarga(c.fecha)}</td>
                    <td>{hora(c.fecha)}</td>
                    <td>
                      {c.opcion}
                      {c.nota && <span className="cf-caption cf-bloque">{c.nota}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      {historial.length > 1 && (
        <section className="cf-panel" aria-labelledby="titulo-historial">
          <h2 id="titulo-historial" className="cf-panel__titulo">Historial</h2>
          <div className="cf-tabla-scroll">
            <table className="cf-tabla">
              <thead>
                <tr>
                  <th>Referencia</th>
                  <th>Plan</th>
                  <th>Estado</th>
                  <th>Contratada</th>
                  <th className="cf-num">Precio</th>
                </tr>
              </thead>
              <tbody>
                {historial.map((h) => (
                  <tr key={h.id}>
                    <td>{h.referencia}</td>
                    <td>{h.plan?.nombre}</td>
                    <td><EstadoMembresia estado={h.estado} /></td>
                    <td className="cf-nowrap">{fechaCorta(h.creada)}</td>
                    <td className="cf-num">{pesos(h.precio)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
