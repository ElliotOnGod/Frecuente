import { useState } from "react";
import { useGraphQLQuery } from "../../../hooks/useGraphQLQuery";
import { graphqlRequest } from "../../../lib/graphql";
import { NOMBRE_METODO, RUTAS, fechaLarga, pesos } from "../../../lib/formato";
import { EstadoSuscripcion } from "../Insignia";
import { Skeleton } from "../Skeleton";
import SoloAdmin from "./SoloAdmin";

const QUERY = `
  query Recompras($estado: String) {
    suscripcionesAdmin(estado: $estado) {
      id estado cadaDias proxima metodoPago creada totalEstimado
      usuario { nombre email }
      items { productoId variante cantidad producto { nombre } }
      entrega { tipo descripcion ciudad }
      pedidos { id }
    }
  }
`;
const PROCESAR = `mutation { procesarRecompras }`;

function Contenido() {
  const [estado, setEstado] = useState("activa");
  const [recarga, setRecarga] = useState(0);
  const [aviso, setAviso] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const { data, loading, error } = useGraphQLQuery(QUERY, { estado: estado || null }, { recarga });
  const lista = data?.suscripcionesAdmin ?? [];
  const hoy = new Date().toISOString().slice(0, 10);

  const procesar = async () => {
    setOcupado(true);
    setAviso(null);
    try {
      const n = (await graphqlRequest(PROCESAR)).procesarRecompras;
      setAviso({ tipo: "success", texto: n ? `Se generaron ${n} pedidos de recompra.` : "Hoy no le toca a ninguna recompra." });
      setRecarga((r) => r + 1);
    } catch (err) {
      setAviso({ tipo: "error", texto: err.message });
    }
    setOcupado(false);
  };

  return (
    <>
      <div className="cf-admin__encabezado">
        <div>
          <h1>Recompras</h1>
          <p className="cf-caption" style={{ margin: 0 }}>
            Suscripciones de clientes que repiten su pedido. El backend las revisa cada hora y, cuando a una le
            toca, crea el pedido y le manda al cliente el enlace para pagarlo (Brevo).
          </p>
        </div>
        <button className="cf-btn" onClick={procesar} disabled={ocupado}>
          {ocupado ? "Procesando…" : "Procesar ahora"}
        </button>
      </div>

      {aviso && (
        <p className={`cf-alerta cf-alerta--${aviso.tipo}`} role="status">{aviso.texto}</p>
      )}

      <div className="cf-filtros__fila" role="group" aria-label="Filtrar por estado">
        <label className="cf-sr" htmlFor="estado-recompra">Estado</label>
        <select id="estado-recompra" className="cf-input" value={estado} onChange={(e) => setEstado(e.target.value)}>
          <option value="activa">Activas</option>
          <option value="pausada">Pausadas</option>
          <option value="cancelada">Canceladas</option>
          <option value="">Todas</option>
        </select>
      </div>

      {error && <p className="cf-alerta cf-alerta--error" role="alert">{error}</p>}

      <div className="cf-panel cf-tabla-scroll" aria-busy={loading}>
        <table className="cf-tabla cf-tabla--filas">
          <thead>
            <tr>
              <th>Cliente</th>
              <th>Productos</th>
              <th>Frecuencia</th>
              <th>Próximo pedido</th>
              <th>Entrega y pago</th>
              <th className="cf-num">Estimado</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data && <tr><td colSpan={6}><Skeleton alto="20px" /></td></tr>}
            {!loading && lista.length === 0 && (
              <tr><td colSpan={6} className="cf-vacio" style={{ textAlign: "center" }}>Sin recompras con ese estado.</td></tr>
            )}
            {lista.map((s) => (
              <tr key={s.id}>
                <td>
                  {s.usuario?.nombre}
                  <span className="cf-caption cf-bloque">{s.usuario?.email}</span>
                  <EstadoSuscripcion estado={s.estado} />
                </td>
                <td>
                  {s.items.map((i) => (
                    <span key={`${i.productoId}|${i.variante}`} className="cf-bloque">
                      {i.cantidad} × {i.producto?.nombre}
                      {i.variante && <span className="cf-caption"> · {i.variante}</span>}
                    </span>
                  ))}
                </td>
                <td>Cada {s.cadaDias} días</td>
                <td className="cf-nowrap">
                  {fechaLarga(s.proxima)}
                  {s.estado === "activa" && s.proxima <= hoy && <span className="cf-caption cf-bloque">Le toca hoy</span>}
                  {s.pedidos.length > 0 && (
                    <a className="cf-link cf-bloque" href={`${RUTAS.adminPedidos}?estado=recompra&buscar=${encodeURIComponent(s.usuario?.email ?? "")}`}>
                      {s.pedidos.length} pedido{s.pedidos.length === 1 ? "" : "s"}
                    </a>
                  )}
                </td>
                <td>
                  {s.entrega?.tipo === "domicilio" ? `${s.entrega.descripcion} · ${s.entrega.ciudad}` : "Recoge en el local"}
                  <span className="cf-caption cf-bloque">{NOMBRE_METODO[s.metodoPago]}</span>
                </td>
                <td className="cf-num">{pesos(s.totalEstimado)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** AdminRecompras — /admin/recompras: suscripciones de recompra mensual. */
export default function AdminRecompras() {
  return (
    <SoloAdmin>
      <Contenido />
    </SoloAdmin>
  );
}
