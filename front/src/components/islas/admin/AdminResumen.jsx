import { useState } from "react";
import { useGraphQLQuery } from "../../../hooks/useGraphQLQuery";
import { useRecargaEnVivo } from "../../../hooks/useRecargaEnVivo";
import { useEnVivo, TIPOS } from "../../../store/enVivo";
import { hora, pesos, RUTAS } from "../../../lib/formato";
import { EstadoPedido } from "../Insignia";
import { Skeleton } from "../Skeleton";
import SoloAdmin from "./SoloAdmin";
import { BarrasHorizontales, GraficaVentas } from "./Graficas";
import { ESTILO_EVENTO } from "./AvisosEnVivo";

const QUERY_RESUMEN = `
  query Resumen($dias: Int!) {
    resumenAdmin(dias: $dias) {
      dias ventasTotal ventasPeriodoAnterior pedidosPagados ticketPromedio
      porCobrar pedidosPorCobrar pedidosPorEnviar pedidosPorReembolsar
      clientesTotal clientesConCompra
      ventasPorDia { fecha total pedidos }
      porMetodo { metodo nombre total pedidos }
      porEstado { estado pedidos }
      topProductos { productoId nombre piezas total }
      stockBajo { id nombre stock }
    }
    resumenMembresias {
      activas pendientes vencen7Dias ingresoMensual canjesHoy canjes7Dias
      porPlan { planId nombre activas ingresoMensual }
    }
  }
`;

const PERIODOS = [
  { dias: 7, texto: "7 días" },
  { dias: 30, texto: "30 días" },
  { dias: 90, texto: "90 días" },
];

/** Cambio contra el periodo anterior, con flecha y palabra (no solo color). */
function Variacion({ actual, anterior }) {
  if (!anterior) return <span className="cf-caption">Sin periodo anterior para comparar</span>;
  const cambio = ((actual - anterior) / anterior) * 100;
  const sube = cambio >= 0;
  return (
    <span className={`cf-variacion cf-variacion--${sube ? "sube" : "baja"}`}>
      <span aria-hidden="true">{sube ? "▲" : "▼"}</span>
      {Math.abs(cambio).toFixed(0)}% {sube ? "más" : "menos"} que el periodo anterior
    </span>
  );
}

function Tarjeta({ titulo, valor, children }) {
  return (
    <div className="cf-kpi">
      <span className="cf-caption">{titulo}</span>
      <strong className="cf-kpi__valor">{valor}</strong>
      {children}
    </div>
  );
}

/** Lo último que pasó en la tienda, en vivo (Subscription eventosAdmin). */
function FeedEnVivo() {
  const eventos = useEnVivo((s) => s.eventos).filter((e) => e.tipo !== "conectado");
  const estado = useEnVivo((s) => s.estado);
  return (
    <section className="cf-panel" aria-labelledby="titulo-feed">
      <h2 id="titulo-feed" className="cf-panel__titulo">Actividad en vivo</h2>
      <span className="cf-caption">
        {estado === "en_vivo"
          ? "Aparece aquí en cuanto pasa, sin recargar."
          : "Conectando con el servidor…"}
      </span>
      {eventos.length === 0 ? (
        <p className="cf-vacio" style={{ paddingBottom: 0 }}>
          Todavía no pasa nada desde que abriste el panel. Haz un pedido o un canje en otra ventana.
        </p>
      ) : (
        <ol className="cf-feed" aria-live="polite">
          {eventos.slice(0, 12).map((e) => {
            const est = ESTILO_EVENTO[e.tipo] || ESTILO_EVENTO.pedido_estado;
            const href = e.pedidoId
              ? `${RUTAS.adminPedidos}?buscar=${e.pedidoId}`
              : e.membresiaId
                ? `${RUTAS.adminMembresias}?buscar=${e.membresiaId}`
                : null;
            return (
              <li key={e.id} className="cf-feed__item">
                <span className="cf-feed__icono" aria-hidden="true">{est.icono}</span>
                <span>
                  {href ? <a href={href}>{e.mensaje}</a> : e.mensaje}
                  <span className="cf-caption cf-bloque">{est.titulo} · {hora(e.fecha)}</span>
                </span>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function Contenido() {
  const [dias, setDias] = useState(30);
  // Se recarga sola cuando llega un aviso en vivo que cambia los números
  const recarga = useRecargaEnVivo([...TIPOS.pedidos, ...TIPOS.membresias, "stock_bajo"], 1000);
  const { data, loading, error } = useGraphQLQuery(QUERY_RESUMEN, { dias }, { recarga });
  const r = data?.resumenAdmin;
  const rm = data?.resumenMembresias;

  return (
    <>
      <div className="cf-admin__encabezado">
        <h1>Resumen</h1>
        <div className="cf-segmentos" role="group" aria-label="Periodo">
          {PERIODOS.map((p) => (
            <button
              key={p.dias}
              className="cf-segmentos__btn"
              aria-pressed={dias === p.dias}
              onClick={() => setDias(p.dias)}
            >
              {p.texto}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span>
          No se pudo cargar el resumen: {error}
        </p>
      )}

      {loading && !r && (
        <div className="cf-kpis">
          {[1, 2, 3, 4].map((n) => (
            <div className="cf-kpi" key={n}>
              <Skeleton alto="14px" ancho="50%" />
              <Skeleton alto="32px" ancho="70%" />
            </div>
          ))}
        </div>
      )}

      {r && (
        <div style={{ opacity: loading ? 0.6 : 1 }} aria-busy={loading}>
          {/* Lo que requiere acción, arriba de todo */}
          {(r.pedidosPorCobrar > 0 || r.pedidosPorEnviar > 0 || r.pedidosPorReembolsar > 0 || r.stockBajo.length > 0) && (
            <ul className="cf-pendientes" aria-label="Pendientes">
              {r.pedidosPorEnviar > 0 && (
                <li>
                  <a href={`${RUTAS.adminPedidos}?estado=pagado`}>
                    <strong>{r.pedidosPorEnviar}</strong> pagado{r.pedidosPorEnviar === 1 ? "" : "s"} por enviar
                  </a>
                </li>
              )}
              {r.pedidosPorCobrar > 0 && (
                <li>
                  <a href={`${RUTAS.adminPedidos}?estado=por_cobrar`}>
                    <strong>{r.pedidosPorCobrar}</strong> por cobrar ({pesos(r.porCobrar)})
                  </a>
                </li>
              )}
              {r.pedidosPorReembolsar > 0 && (
                <li data-tono="error">
                  <a href={`${RUTAS.adminPedidos}?estado=por_reembolsar`}>
                    <strong>{r.pedidosPorReembolsar}</strong> por reembolsar
                  </a>
                </li>
              )}
              {rm?.pendientes > 0 && (
                <li>
                  <a href={`${RUTAS.adminMembresias}?estado=pendiente`}>
                    <strong>{rm.pendientes}</strong> membresía{rm.pendientes === 1 ? "" : "s"} por cobrar
                  </a>
                </li>
              )}
              {rm?.vencen7Dias > 0 && (
                <li>
                  <a href={`${RUTAS.adminMembresias}?estado=activa`}>
                    <strong>{rm.vencen7Dias}</strong> membresía{rm.vencen7Dias === 1 ? "" : "s"} vence{rm.vencen7Dias === 1 ? "" : "n"} esta semana
                  </a>
                </li>
              )}
              {r.stockBajo.length > 0 && (
                <li>
                  <a href={RUTAS.adminProductos}>
                    <strong>{r.stockBajo.length}</strong> producto{r.stockBajo.length === 1 ? "" : "s"} con stock bajo
                  </a>
                </li>
              )}
            </ul>
          )}

          <div className="cf-kpis">
            <Tarjeta titulo={`Ventas · últimos ${r.dias} días`} valor={pesos(r.ventasTotal)}>
              <Variacion actual={r.ventasTotal} anterior={r.ventasPeriodoAnterior} />
            </Tarjeta>
            <Tarjeta titulo="Pedidos pagados" valor={r.pedidosPagados}>
              <span className="cf-caption">
                de {r.clientesConCompra} cliente{r.clientesConCompra === 1 ? "" : "s"} ·{" "}
                {r.clientesTotal} registrados
              </span>
            </Tarjeta>
            <Tarjeta titulo="Ticket promedio" valor={pesos(r.ticketPromedio)}>
              <span className="cf-caption">Por pedido pagado</span>
            </Tarjeta>
            <Tarjeta titulo="Por cobrar" valor={pesos(r.porCobrar)}>
              <span className="cf-caption">
                {r.pedidosPorCobrar} pedido{r.pedidosPorCobrar === 1 ? "" : "s"} esperando pago
              </span>
            </Tarjeta>
          </div>

          <section className="cf-panel">
            <GraficaVentas puntos={r.ventasPorDia} />
          </section>

          {rm && (
            <div className="cf-admin__dos">
              <section className="cf-panel" aria-labelledby="titulo-memb">
                <div className="cf-grafica__barra">
                  <div>
                    <h2 id="titulo-memb" className="cf-panel__titulo">Membresías</h2>
                    <span className="cf-caption">Ingreso recurrente: lo que pagan los miembros activos cada 30 días</span>
                  </div>
                  <a className="cf-link" href={RUTAS.adminMembresias}>Ver todas</a>
                </div>
                <div className="cf-kpis cf-kpis--dos">
                  <Tarjeta titulo="Miembros activos" valor={rm.activas}>
                    <span className="cf-caption">{rm.pendientes} por pagar</span>
                  </Tarjeta>
                  <Tarjeta titulo="Ingreso recurrente" valor={pesos(rm.ingresoMensual)}>
                    <span className="cf-caption">cada 30 días</span>
                  </Tarjeta>
                  <Tarjeta titulo="Canjes hoy" valor={rm.canjesHoy}>
                    <span className="cf-caption">de {rm.activas} posibles</span>
                  </Tarjeta>
                  <Tarjeta titulo="Canjes 7 días" valor={rm.canjes7Dias}>
                    <a className="cf-link cf-caption" href={RUTAS.adminCaja}>Ir a caja</a>
                  </Tarjeta>
                </div>
                <BarrasHorizontales
                  titulo="Miembros por plan"
                  filas={rm.porPlan.map((p) => ({
                    clave: p.planId,
                    nombre: p.nombre,
                    valor: p.activas,
                    ingreso: p.ingresoMensual,
                  }))}
                  formato={(n) => `${n} activo${n === 1 ? "" : "s"}`}
                  detalle={(f) => pesos(f.ingreso)}
                />
              </section>

              <FeedEnVivo />
            </div>
          )}

          <div className="cf-admin__dos">
            <section className="cf-panel">
              <BarrasHorizontales
                titulo="Ventas por método de pago"
                subtitulo={`Últimos ${r.dias} días`}
                filas={r.porMetodo.map((m) => ({ clave: m.metodo, nombre: m.nombre, valor: m.total, pedidos: m.pedidos }))}
                detalle={(f) => `${f.pedidos} pedido${f.pedidos === 1 ? "" : "s"}`}
              />
            </section>

            <section className="cf-panel">
              <h2 className="cf-panel__titulo">Pedidos por estado</h2>
              <span className="cf-caption">Registrados en los últimos {r.dias} días</span>
              <ul className="cf-conteos">
                {r.porEstado.map((e) => (
                  <li key={e.estado}>
                    <a href={`${RUTAS.adminPedidos}?estado=${e.estado}`}>
                      <EstadoPedido estado={e.estado} />
                      <strong>{e.pedidos}</strong>
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <div className="cf-admin__dos">
            <section className="cf-panel">
              <h2 className="cf-panel__titulo">Más vendidos</h2>
              {r.topProductos.length === 0 ? (
                <p className="cf-caption">Sin ventas en este periodo.</p>
              ) : (
                <table className="cf-tabla">
                  <thead>
                    <tr>
                      <th>Producto</th>
                      <th className="cf-num">Piezas</th>
                      <th className="cf-num">Ventas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.topProductos.map((p) => (
                      <tr key={p.productoId}>
                        <td>{p.nombre}</td>
                        <td className="cf-num">{p.piezas}</td>
                        <td className="cf-num">{pesos(p.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>

            <section className="cf-panel">
              <h2 className="cf-panel__titulo">Stock bajo</h2>
              {r.stockBajo.length === 0 ? (
                <p className="cf-caption">Todo el inventario está arriba de 10 piezas.</p>
              ) : (
                <table className="cf-tabla">
                  <thead>
                    <tr>
                      <th>Producto</th>
                      <th className="cf-num">Quedan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.stockBajo.map((p) => (
                      <tr key={p.id}>
                        <td>{p.nombre}</td>
                        <td className="cf-num">
                          {p.stock === 0 ? (
                            <span className="cf-estado cf-estado--error">Agotado</span>
                          ) : (
                            p.stock
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <a className="cf-link" href={RUTAS.adminProductos}>Administrar inventario</a>
            </section>
          </div>
        </div>
      )}
    </>
  );
}

/** AdminResumen — /admin: indicadores, gráficas y pendientes del negocio. */
export default function AdminResumen() {
  return (
    <SoloAdmin>
      <Contenido />
    </SoloAdmin>
  );
}
