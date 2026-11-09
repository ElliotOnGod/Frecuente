import { useGraphQLQuery } from "../../../hooks/useGraphQLQuery";
import { RUTAS, fechaCorta } from "../../../lib/formato";
import { EstadoCorreo, Insignia } from "../Insignia";
import { Skeleton } from "../Skeleton";
import SoloAdmin from "./SoloAdmin";

const QUERY = `
  query Integraciones {
    integraciones { clave nombre paraQue modo activa }
    correosAdmin(limite: 40) { id destinatario asunto plantilla estado detalle pedidoId fecha }
  }
`;

const API_URL = import.meta.env.PUBLIC_API_URL || "http://localhost:8000/graphql";
const MCP_URL = API_URL.replace(/\/graphql\/?$/, "/mcp");

const TONO_MODO = { real: "ok", sandbox: "info", brevo: "ok", simulado: "aviso" };
const TEXTO_MODO = {
  real: "Conectada",
  sandbox: "Sandbox (pruebas reales)",
  brevo: "Conectada",
  simulado: "Simulada (falta la llave)",
};

const PLANTILLAS = {
  bienvenida: "Bienvenida",
  pedido_nuevo_tienda: "Aviso a la tienda",
  pedido_confirmado: "Pago confirmado",
  pedido_enviado: "Pedido enviado",
  membresia_activada: "Membresía activada",
  recompra_lista: "Recompra lista",
  recompra_sin_stock: "Recompra sin stock",
};

function Contenido() {
  const { data, loading, error } = useGraphQLQuery(QUERY);
  const integraciones = data?.integraciones ?? [];
  const correos = data?.correosAdmin ?? [];

  return (
    <>
      <div className="cf-admin__encabezado">
        <div>
          <h1>Integraciones</h1>
          <p className="cf-caption" style={{ margin: 0 }}>
            APIs de terceros que usa la tienda. Las llaves viven en las variables de entorno del backend (Render),
            nunca en el código. Sin llave, cada una trabaja en modo simulado.
          </p>
        </div>
      </div>

      {error && <p className="cf-alerta cf-alerta--error" role="alert">{error}</p>}

      <div className="cf-integraciones">
        {loading && [1, 2, 3].map((n) => <Skeleton key={n} alto="96px" />)}
        {integraciones.map((i) => (
          <article key={i.clave} className="cf-panel cf-integracion">
            <strong>{i.nombre}</strong>
            <span className="cf-caption">{i.paraQue}</span>
            <span>
              <Insignia tono={TONO_MODO[i.modo] ?? "neutro"}>{TEXTO_MODO[i.modo] ?? i.modo}</Insignia>
            </span>
          </article>
        ))}
        {!loading && (
          <article className="cf-panel cf-integracion">
            <strong>Servidor MCP (para agentes de IA)</strong>
            <span className="cf-caption">
              Un asistente de IA puede consultar el catálogo, cotizar envíos y, con token de admin, ver
              ventas y pedidos.
            </span>
            <code className="cf-caption" style={{ wordBreak: "break-all" }}>{MCP_URL}</code>
          </article>
        )}
      </div>

      <h2>Correos enviados</h2>
      <p className="cf-caption">Los últimos 40 correos automáticos (Brevo). En modo simulado solo se anotan aquí.</p>
      <div className="cf-panel cf-tabla-scroll" aria-busy={loading}>
        <table className="cf-tabla cf-tabla--filas">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Para</th>
              <th>Correo</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {!loading && correos.length === 0 && (
              <tr><td colSpan={4} className="cf-vacio" style={{ textAlign: "center" }}>Todavía no se manda ningún correo.</td></tr>
            )}
            {correos.map((c) => (
              <tr key={c.id}>
                <td className="cf-nowrap">{fechaCorta(c.fecha)}</td>
                <td>{c.destinatario}</td>
                <td>
                  {c.asunto}
                  <span className="cf-caption cf-bloque">
                    {PLANTILLAS[c.plantilla] ?? c.plantilla}
                    {c.pedidoId && (
                      <>
                        {" · "}
                        <a className="cf-link" href={`${RUTAS.adminPedidos}?buscar=${c.pedidoId}`}>pedido #{c.pedidoId}</a>
                      </>
                    )}
                  </span>
                </td>
                <td>
                  <EstadoCorreo estado={c.estado} />
                  {c.detalle && <span className="cf-caption cf-bloque">{c.detalle}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** AdminIntegraciones — /admin/integraciones: estado de las APIs y bitácora de correos. */
export default function AdminIntegraciones() {
  return (
    <SoloAdmin>
      <Contenido />
    </SoloAdmin>
  );
}
