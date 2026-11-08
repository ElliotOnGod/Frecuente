import { useState } from "react";
import { graphqlRequest } from "../../lib/graphql";
import { QUERY_RASTREO } from "../../lib/envios";
import { LOCAL } from "../../lib/local";
import { pesos } from "../../lib/formato";

/**
 * EntregaPedido — a dónde va el pedido y, si ya salió, su número de guía
 * con el rastreo de la paquetería (Envia.com). Lo usan la página del
 * pedido y el panel de administración.
 */
export default function EntregaPedido({ pedido, conRastreo = true }) {
  const e = pedido.entrega;
  const [rastreo, setRastreo] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);

  if (!e || e.tipo === "recoger") {
    return (
      <section className="cf-panel" aria-label="Entrega">
        <span className="cf-caption">Entrega</span>
        <p style={{ margin: 0 }}>
          <strong>Recoges en el local</strong> · {LOCAL.calle}, {LOCAL.colonia}, {LOCAL.ciudad}
        </p>
      </section>
    );
  }

  const verRastreo = async () => {
    setCargando(true);
    setError(null);
    try {
      setRastreo((await graphqlRequest(QUERY_RASTREO, { id: pedido.id })).rastrearPedido);
    } catch (err) {
      setError(err.message);
    }
    setCargando(false);
  };

  return (
    <section className="cf-panel" aria-label="Envío a domicilio">
      <div className="cf-datos">
        <div>
          <span className="cf-caption">Envío a</span>
          <p>
            {e.nombre} · {e.telefono}
            <br />
            {e.calle} {e.numero}, {e.colonia}
            <br />
            {e.ciudad}, {e.estado} · CP {e.cp}
            {e.referencias && (
              <>
                <br />
                <span className="cf-caption">{e.referencias}</span>
              </>
            )}
          </p>
        </div>
        <div>
          <span className="cf-caption">Paquetería</span>
          <p>
            {e.descripcion} · {e.dias}
            <br />
            {pesos(e.costo)}
            {e.modo === "simulado" && <span className="cf-estado cf-estado--info" style={{ marginLeft: 8 }}>Prueba</span>}
          </p>
        </div>
        <div>
          <span className="cf-caption">Número de guía</span>
          <p>{e.guia || "Se genera cuando sale de la tienda"}</p>
        </div>
      </div>

      {conRastreo && e.guia && (
        <div style={{ marginTop: "var(--espacio-sm)" }}>
          <div className="cf-acciones cf-acciones--envolver">
            <button className="cf-btn cf-btn--secundario" onClick={verRastreo} disabled={cargando}>
              {cargando ? "Consultando…" : rastreo ? "Actualizar rastreo" : "Rastrear mi paquete"}
            </button>
            {e.rastreoUrl && (
              <a className="cf-link" href={e.rastreoUrl} target="_blank" rel="noopener noreferrer">
                Ver en la paquetería
              </a>
            )}
          </div>
          {error && <p className="cf-alerta cf-alerta--error" role="alert">{error}</p>}
          {rastreo && (
            <ol className="cf-rastreo" aria-label="Historial del envío">
              {rastreo.eventos.map((ev, i) => (
                <li key={i} aria-current={i === 0 ? "step" : undefined}>
                  <strong>{ev.descripcion}</strong>
                  {(ev.fecha || ev.lugar) && (
                    <span className="cf-caption cf-bloque">{[ev.fecha, ev.lugar].filter(Boolean).join(" · ")}</span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </section>
  );
}
