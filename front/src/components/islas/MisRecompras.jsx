import { useState } from "react";
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { graphqlRequest } from "../../lib/graphql";
import { ESTADO_SUSCRIPCION, NOMBRE_METODO, RUTAS, fechaLarga, pesos } from "../../lib/formato";
import { Insignia } from "./Insignia";

const CAMPOS = `
  id estado cadaDias proxima metodoPago totalEstimado
  items { productoId variante cantidad producto { nombre } }
  entrega { tipo descripcion ciudad }
  pedidos { id estado }
`;

const QUERY = `query MisRecompras { misSuscripciones { ${CAMPOS} } }`;
const MUTATION = `
  mutation CambiarRecompra($id: Int!, $estado: String, $cadaDias: Int) {
    cambiarMiSuscripcion(id: $id, estado: $estado, cadaDias: $cadaDias) { ${CAMPOS} }
  }
`;

/** Una suscripción con sus acciones: pausar, reanudar, cambiar frecuencia, cancelar. */
function Recompra({ s, onCambio }) {
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const [confirmar, setConfirmar] = useState(false);

  const cambiar = async (variables) => {
    setOcupado(true);
    setError(null);
    try {
      onCambio((await graphqlRequest(MUTATION, { id: s.id, ...variables })).cambiarMiSuscripcion);
      setConfirmar(false);
    } catch (err) {
      setError(err.message);
    }
    setOcupado(false);
  };

  const estado = ESTADO_SUSCRIPCION[s.estado] ?? { texto: s.estado, tono: "neutro" };
  const activa = s.estado === "activa";

  return (
    <article className="cf-panel cf-suscripcion" aria-label={`Recompra ${s.id}`}>
      <div className="cf-resumen" style={{ marginTop: 0 }}>
        <div>
          <strong>Cada {s.cadaDias} días</strong> <Insignia tono={estado.tono}>{estado.texto}</Insignia>
          <p className="cf-caption" style={{ margin: 0 }}>
            {activa ? `Próximo pedido: ${fechaLarga(s.proxima)}` : s.estado === "pausada" ? "En pausa" : "Cancelada"}
            {" · "}{NOMBRE_METODO[s.metodoPago]}
            {" · "}{s.entrega?.tipo === "domicilio" ? `${s.entrega.descripcion} a ${s.entrega.ciudad}` : "recoger en el local"}
          </p>
        </div>
        <span className="cf-total">≈ {pesos(s.totalEstimado)}</span>
      </div>

      <ul className="cf-lista-simple">
        {s.items.map((i) => (
          <li key={`${i.productoId}|${i.variante}`}>
            {i.cantidad} × {i.producto?.nombre ?? `Producto ${i.productoId}`}
            {i.variante && <span className="cf-caption"> · {i.variante}</span>}
          </li>
        ))}
      </ul>

      {s.pedidos.length > 0 && (
        <p className="cf-caption" style={{ margin: 0 }}>
          Pedidos generados:{" "}
          {s.pedidos.map((p, n) => (
            <span key={p.id}>
              {n > 0 && ", "}
              <a className="cf-link" href={RUTAS.pedidoDetalle(p.id)}>#{p.id}</a>
            </span>
          ))}
        </p>
      )}

      {error && <p className="cf-alerta cf-alerta--error" role="alert">{error}</p>}

      {s.estado !== "cancelada" && (
        <div className="cf-acciones cf-acciones--envolver">
          <label className="cf-sr" htmlFor={`frecuencia-${s.id}`}>Frecuencia</label>
          <select
            id={`frecuencia-${s.id}`}
            className="cf-input"
            style={{ width: "auto" }}
            value={s.cadaDias}
            disabled={ocupado}
            onChange={(e) => cambiar({ cadaDias: Number(e.target.value) })}
          >
            <option value={15}>Cada 15 días</option>
            <option value={30}>Cada mes</option>
            <option value={60}>Cada 2 meses</option>
          </select>
          {activa ? (
            <button className="cf-btn cf-btn--secundario" disabled={ocupado} onClick={() => cambiar({ estado: "pausada" })}>
              Pausar
            </button>
          ) : (
            <button className="cf-btn" disabled={ocupado} onClick={() => cambiar({ estado: "activa" })}>
              Reanudar
            </button>
          )}
          {!confirmar ? (
            <button className="cf-link" disabled={ocupado} onClick={() => setConfirmar(true)}>Cancelar recompra</button>
          ) : (
            <span className="cf-acciones" role="group" aria-label="Confirmar cancelación">
              <span>¿Seguro? Ya no se generarán pedidos.</span>
              <button className="cf-btn cf-btn--peligro" disabled={ocupado} onClick={() => cambiar({ estado: "cancelada" })}>
                Sí, cancelar
              </button>
              <button className="cf-btn cf-btn--secundario" onClick={() => setConfirmar(false)}>No</button>
            </span>
          )}
        </div>
      )}
    </article>
  );
}

/** MisRecompras — sección de "Mi cuenta" con las suscripciones de recompra. */
export default function MisRecompras() {
  const { data, loading, error } = useGraphQLQuery(QUERY);
  const [cambios, setCambios] = useState({});
  if (loading || error) return null;

  const lista = (data?.misSuscripciones ?? []).map((s) => cambios[s.id] ?? s);

  return (
    <>
      <h2>Tus recompras</h2>
      {lista.length === 0 ? (
        <p className="cf-vacio">
          ¿Siempre pides lo mismo? Al confirmar tu próximo pedido marca <strong>Repetir este pedido</strong> y te lo
          preparamos cada mes.
        </p>
      ) : (
        lista.map((s) => (
          <Recompra key={s.id} s={s} onCambio={(nuevo) => setCambios((c) => ({ ...c, [nuevo.id]: nuevo }))} />
        ))
      )}
    </>
  );
}
