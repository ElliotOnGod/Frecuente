import { useState } from "react";
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { useStore } from "../../store/useStore";
import { RUTAS, fechaLarga, pesos } from "../../lib/formato";
import { QUERY_METODOS } from "../../lib/pagos";
import { QUERY_PLANES, contratarYPagar } from "../../lib/membresias";
import { Skeleton } from "./Skeleton";

const QUERY_ACTUAL = `
  query MembresiaActual {
    miMembresia { id estado fin plan { id nombre } }
  }
`;

/** Tarjeta de un plan con su botón de contratar. */
function TarjetaPlan({ plan, destacado, actual, metodos, sesion }) {
  const [abierto, setAbierto] = useState(false);
  const [metodo, setMetodo] = useState("mercadopago");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  const esActual = actual?.estado === "activa" && actual.plan?.id === plan.id;
  const tieneVigente = actual?.estado === "activa";
  const tienePendiente = actual?.estado === "pendiente";

  const contratar = async () => {
    setEnviando(true);
    setError(null);
    try {
      await contratarYPagar(plan.id, metodo);
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  const textoBoton = esActual ? "Renovar este plan" : tieneVigente ? "Cambiar a este plan" : "Contratar";

  return (
    <article className="cf-plan" data-destacado={destacado ? "true" : undefined} aria-labelledby={`plan-${plan.id}`}>
      {destacado && <span className="cf-plan__cinta">El más pedido</span>}
      <h2 id={`plan-${plan.id}`} className="cf-plan__nombre">{plan.nombre}</h2>
      <p className="cf-caption" style={{ marginTop: 0 }}>{plan.descripcion}</p>
      <p className="cf-plan__precio">
        <strong>{pesos(plan.precio)}</strong> <span className="cf-caption">/ 30 días</span>
      </p>
      <p className="cf-caption cf-plan__diario">≈ {pesos(plan.precio / 30)} al día</p>

      <ul className="cf-plan__incluye">
        {plan.incluye.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ul>

      {esActual && <p className="cf-estado cf-estado--ok">Tu plan actual</p>}

      {!sesion ? (
        <a className="cf-btn cf-btn--bloque" href={RUTAS.login(RUTAS.membresias)}>
          Inicia sesión para contratar
        </a>
      ) : tienePendiente ? (
        <a className="cf-btn cf-btn--secundario cf-btn--bloque" href={RUTAS.miMembresia}>
          Tienes una membresía por pagar
        </a>
      ) : !abierto ? (
        <button className="cf-btn cf-btn--bloque" onClick={() => setAbierto(true)}>
          {textoBoton}
        </button>
      ) : (
        <div className="cf-plan__pago">
          <label className="cf-label" htmlFor={`metodo-${plan.id}`}>¿Cómo quieres pagar?</label>
          <select
            id={`metodo-${plan.id}`}
            className="cf-input"
            value={metodo}
            onChange={(e) => setMetodo(e.target.value)}
          >
            {metodos.map((m) => (
              <option key={m.clave} value={m.clave}>
                {m.clave === "efectivo" ? "Efectivo en el local" : m.nombre}
              </option>
            ))}
          </select>
          {tieneVigente && (
            <p className="cf-ayuda" style={{ margin: 0 }}>
              Empieza cuando termine tu membresía actual ({fechaLarga(actual.fin)}); no pierdes días.
            </p>
          )}
          {error && (
            <p className="cf-alerta cf-alerta--error" role="alert">
              <span className="cf-icon" aria-hidden="true">!</span> {error}
            </p>
          )}
          <div className="cf-acciones">
            <button className="cf-btn" onClick={contratar} disabled={enviando}>
              {enviando ? "Procesando…" : `Pagar ${pesos(plan.precio)}`}
            </button>
            <button className="cf-btn cf-btn--secundario" onClick={() => setAbierto(false)} disabled={enviando}>
              Cancelar
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

/**
 * Planes — /membresias. Los planes mensuales: un café al día, café con
 * comida o el combo completo, para canjear en el local.
 */
export default function Planes() {
  const sesion = useStore((s) => s.sesion);
  const { data, loading, error } = useGraphQLQuery(QUERY_PLANES);
  const { data: dataMetodos } = useGraphQLQuery(QUERY_METODOS);
  const { data: dataActual } = useGraphQLQuery(QUERY_ACTUAL, {}, { omitir: !sesion });

  const planes = data?.planes ?? [];
  const metodos = dataMetodos?.metodosPago ?? [];
  const actual = dataActual?.miMembresia;

  return (
    <>
      <section className="cf-hero cf-hero--membresia">
        <h1 className="cf-display">Tu café de cada día, ya pagado</h1>
        <p>
          Elige un plan de 30 días y canjea tu beneficio en el local una vez al día:
          solo enseña tu código en caja. Sin filas para pagar, sin pensar en la cuenta.
        </p>
      </section>

      {actual?.estado === "activa" && (
        <p className="cf-alerta cf-alerta--success" role="status">
          <span className="cf-icon" aria-hidden="true">✓</span>
          Tienes {actual.plan?.nombre} activa hasta el {fechaLarga(actual.fin)}.{" "}
          <a href={RUTAS.miMembresia}>Ver mi código de hoy</a>
        </p>
      )}

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> No se pudieron cargar los planes: {error}
        </p>
      )}

      <div className="cf-planes">
        {loading &&
          [1, 2, 3].map((n) => (
            <div className="cf-plan" key={n}>
              <Skeleton alto="28px" ancho="60%" />
              <Skeleton alto="40px" ancho="50%" />
              <Skeleton alto="80px" />
            </div>
          ))}
        {planes.map((p, i) => (
          <TarjetaPlan
            key={p.id}
            plan={p}
            destacado={planes.length >= 3 && i === 1}
            actual={actual}
            metodos={metodos}
            sesion={sesion}
          />
        ))}
      </div>

      <section className="cf-contexto" aria-label="Cómo funciona">
        <div>
          <h3>1. Elige tu plan</h3>
          <p>Paga con tarjeta, OXXO, PayPal, transferencia o en el local.</p>
        </div>
        <div>
          <h3>2. Enseña tu código</h3>
          <p>En "Mi membresía" aparece tu código del día. Cambia cada día y es solo tuyo.</p>
        </div>
        <div>
          <h3>3. Disfruta</h3>
          <p>Un canje al día durante 30 días. Puedes renovar antes y no pierdes días.</p>
        </div>
      </section>
    </>
  );
}
