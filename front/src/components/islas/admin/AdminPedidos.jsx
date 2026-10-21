import { useEffect, useState } from "react";
import { graphqlRequest } from "../../../lib/graphql";
import { useGraphQLQuery } from "../../../hooks/useGraphQLQuery";
import { useRecargaEnVivo } from "../../../hooks/useRecargaEnVivo";
import { TIPOS, useEnVivo } from "../../../store/enVivo";
import { NOMBRE_METODO, fechaCorta, pesos } from "../../../lib/formato";
import { EstadoPago, EstadoPedido } from "../Insignia";
import { Skeleton } from "../Skeleton";
import SoloAdmin from "./SoloAdmin";

const CAMPOS = `
  id fecha estado total referencia piezas
  usuario { nombre email telefono }
  items { cantidad precioUnit subtotal producto { nombre } }
  pago { metodo metodoNombre estado modo referencia pagoId detalle fechaPago }
`;

const QUERY_PEDIDOS = `
  query PedidosAdmin($estado: String, $metodo: String, $buscar: String, $limite: Int!, $salto: Int!) {
    pedidosAdmin(estado: $estado, metodo: $metodo, buscar: $buscar, limite: $limite, salto: $salto) {
      total
      pedidos { ${CAMPOS} }
    }
  }
`;

const MUTATION_ESTADO = `
  mutation CambiarEstado($id: Int!, $estado: String!) {
    cambiarEstadoPedido(id: $id, estado: $estado) { ${CAMPOS} }
  }
`;

const MUTATION_REEMBOLSO = `
  mutation Reembolsado($id: Int!) { marcarReembolsado(id: $id) { ${CAMPOS} } }
`;

const FILTROS = [
  { valor: "", texto: "Todos" },
  { valor: "por_cobrar", texto: "Por cobrar" },
  { valor: "pagado", texto: "Por enviar" },
  { valor: "enviado", texto: "Enviados" },
  { valor: "entregado", texto: "Entregados" },
  { valor: "cancelado", texto: "Cancelados" },
  { valor: "por_reembolsar", texto: "Por reembolsar" },
];

const POR_PAGINA = 15;

/** Acciones posibles según el estado (igual que TRANSICIONES en el backend). */
function accionesDe(p) {
  const efectivo = p.pago?.metodo === "efectivo";
  switch (p.estado) {
    case "registrado":
      return [
        efectivo
          ? { estado: "entregado", texto: "Entregado y cobrado en el local" }
          : { estado: "pagado", texto: "Confirmar pago recibido" },
        { estado: "cancelado", texto: "Cancelar pedido", peligro: true },
      ];
    case "pagado":
      return [
        { estado: "enviado", texto: "Marcar como enviado" },
        { estado: "entregado", texto: "Entregado en el local" },
        { estado: "cancelado", texto: "Cancelar y reembolsar", peligro: true },
      ];
    case "enviado":
      return [{ estado: "entregado", texto: "Marcar como entregado" }];
    default:
      return [];
  }
}

/** Panel lateral con el detalle del pedido y sus acciones. */
function Detalle({ pedido, onCerrar, onActualizado }) {
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const [porConfirmar, setPorConfirmar] = useState(null);

  useEffect(() => {
    const esc = (e) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onCerrar]);

  const ejecutar = async (query, variables) => {
    setOcupado(true);
    setError(null);
    try {
      const data = await graphqlRequest(query, variables);
      onActualizado(Object.values(data)[0]);
      setPorConfirmar(null);
    } catch (err) {
      setError(err.message);
    }
    setOcupado(false);
  };

  const pago = pedido.pago;
  const acciones = accionesDe(pedido);

  return (
    <div className="cf-modal-fondo" onClick={onCerrar}>
      <aside
        className="cf-modal cf-detalle"
        role="dialog"
        aria-modal="true"
        aria-labelledby="detalle-titulo"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="cf-modal__barra">
          <div>
            <h2 id="detalle-titulo" style={{ margin: 0 }}>Pedido #{pedido.id}</h2>
            <span className="cf-caption">{fechaCorta(pedido.fecha)} · {pedido.referencia}</span>
          </div>
          <button className="cf-btn cf-btn--icono" aria-label="Cerrar" onClick={onCerrar} autoFocus>
            ✕
          </button>
        </div>

        <div className="cf-detalle__estados">
          <EstadoPedido estado={pedido.estado} />
          {pago && <EstadoPago estado={pago.estado} />}
        </div>

        {error && (
          <p className="cf-alerta cf-alerta--error" role="alert">
            <span className="cf-icon" aria-hidden="true">!</span> {error}
          </p>
        )}

        <dl className="cf-detalle__datos">
          <div>
            <dt className="cf-caption">Cliente</dt>
            <dd>{pedido.usuario?.nombre}</dd>
            <dd className="cf-caption">{pedido.usuario?.email}</dd>
            {pedido.usuario?.telefono && <dd className="cf-caption">{pedido.usuario.telefono}</dd>}
          </div>
          <div>
            <dt className="cf-caption">Pago</dt>
            {pago ? (
              <>
                <dd>{pago.metodoNombre}{pago.modo !== "manual" && ` (${pago.modo})`}</dd>
                {pago.pagoId && <dd className="cf-caption">Folio: {pago.pagoId}</dd>}
                {pago.fechaPago && <dd className="cf-caption">Pagado: {fechaCorta(pago.fechaPago)}</dd>}
                {pago.detalle && <dd className="cf-caption">{pago.detalle}</dd>}
              </>
            ) : (
              <dd className="cf-caption">Pedido anterior a los pagos en línea</dd>
            )}
          </div>
        </dl>

        <table className="cf-tabla">
          <thead>
            <tr>
              <th>Producto</th>
              <th className="cf-num">Cant.</th>
              <th className="cf-num">Subtotal</th>
            </tr>
          </thead>
          <tbody>
            {pedido.items.map((it, i) => (
              <tr key={i}>
                <td>{it.producto?.nombre}</td>
                <td className="cf-num">{it.cantidad}</td>
                <td className="cf-num">{pesos(it.subtotal)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="cf-total" style={{ textAlign: "right" }}>Total: {pesos(pedido.total)}</p>

        {(acciones.length > 0 || pago?.estado === "por_reembolsar") && (
          <div className="cf-detalle__acciones">
            {porConfirmar ? (
              <div role="group" aria-label="Confirmar acción">
                <p style={{ marginTop: 0 }}>
                  {porConfirmar.estado === "cancelado"
                    ? "Se cancela el pedido y los productos regresan al inventario."
                    : "¿Confirmas este cambio?"}
                  {porConfirmar.estado === "cancelado" && pago?.estado === "aprobado" &&
                    " Como ya estaba pagado, quedará marcado para reembolsar."}
                </p>
                <div className="cf-acciones">
                  <button
                    className={`cf-btn ${porConfirmar.peligro ? "cf-btn--peligro" : ""}`}
                    disabled={ocupado}
                    onClick={() => ejecutar(MUTATION_ESTADO, { id: pedido.id, estado: porConfirmar.estado })}
                  >
                    {ocupado ? "Guardando…" : `Sí, ${porConfirmar.texto.toLowerCase()}`}
                  </button>
                  <button className="cf-btn cf-btn--secundario" onClick={() => setPorConfirmar(null)}>
                    Volver
                  </button>
                </div>
              </div>
            ) : (
              <div className="cf-acciones cf-acciones--envolver">
                {acciones.map((a) => (
                  <button
                    key={a.estado}
                    className={`cf-btn ${a.peligro ? "cf-btn--secundario cf-btn--texto-peligro" : ""}`}
                    disabled={ocupado}
                    onClick={() =>
                      a.peligro ? setPorConfirmar(a) : ejecutar(MUTATION_ESTADO, { id: pedido.id, estado: a.estado })
                    }
                  >
                    {a.texto}
                  </button>
                ))}
                {pago?.estado === "por_reembolsar" && (
                  <button
                    className="cf-btn"
                    disabled={ocupado}
                    onClick={() => ejecutar(MUTATION_REEMBOLSO, { id: pedido.id })}
                  >
                    Marcar como reembolsado
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}

function Contenido() {
  const inicial = new URLSearchParams(window.location.search);
  const [estado, setEstado] = useState(inicial.get("estado") || "");
  const [metodo, setMetodo] = useState(inicial.get("metodo") || "");
  const [texto, setTexto] = useState(inicial.get("buscar") || "");
  const [buscar, setBuscar] = useState(inicial.get("buscar") || "");
  const [pagina, setPagina] = useState(0);
  const [abierto, setAbierto] = useState(null);
  const [cambios, setCambios] = useState({}); // pedidos editados en esta vista

  // El filtro queda en la URL: se puede recargar o compartir
  useEffect(() => {
    const p = new URLSearchParams();
    if (estado) p.set("estado", estado);
    if (metodo) p.set("metodo", metodo);
    const qs = p.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [estado, metodo]);

  // En vivo: la lista se recarga sola con pedidos nuevos o cambios de pago
  const recarga = useRecargaEnVivo(TIPOS.pedidos);
  const eventos = useEnVivo((s) => s.eventos);
  const nuevos = new Set(eventos.filter((e) => e.tipo === "pedido_nuevo").map((e) => e.pedidoId));

  const { data, loading, error } = useGraphQLQuery(
    QUERY_PEDIDOS,
    {
      estado: estado || null,
      metodo: metodo || null,
      buscar: buscar || null,
      limite: POR_PAGINA,
      salto: pagina * POR_PAGINA,
    },
    { recarga }
  );

  const total = data?.pedidosAdmin.total ?? 0;
  // Lo que llega del servidor es lo más nuevo; `cambios` solo cubre el
  // momento entre que el admin actúa y llega la recarga.
  const pedidos = (data?.pedidosAdmin.pedidos ?? []).map((p) =>
    cambios[p.id] && recarga === cambios[p.id].__recarga ? cambios[p.id] : p
  );
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  const filtrar = (fn) => (v) => {
    fn(v);
    setPagina(0);
  };

  const actualizado = (p) => {
    setCambios((c) => ({ ...c, [p.id]: { ...p, __recarga: recarga } }));
    setAbierto(p);
  };

  return (
    <>
      <div className="cf-admin__encabezado">
        <h1>Pedidos</h1>
        <span className="cf-caption">{total} pedido{total === 1 ? "" : "s"}</span>
      </div>

      <div className="cf-filtros">
        <div className="cf-segmentos cf-segmentos--scroll" role="group" aria-label="Estado">
          {FILTROS.map((f) => (
            <button
              key={f.valor}
              className="cf-segmentos__btn"
              aria-pressed={estado === f.valor}
              onClick={() => filtrar(setEstado)(f.valor)}
            >
              {f.texto}
            </button>
          ))}
        </div>

        <div className="cf-filtros__fila">
          <label className="cf-sr" htmlFor="filtro-metodo">Método de pago</label>
          <select
            id="filtro-metodo"
            className="cf-input"
            value={metodo}
            onChange={(e) => filtrar(setMetodo)(e.target.value)}
          >
            <option value="">Todos los métodos</option>
            {Object.entries(NOMBRE_METODO).map(([clave, nombre]) => (
              <option key={clave} value={clave}>{nombre}</option>
            ))}
          </select>

          <form
            className="cf-buscar"
            role="search"
            onSubmit={(e) => {
              e.preventDefault();
              filtrar(setBuscar)(texto.trim());
            }}
          >
            <label className="cf-sr" htmlFor="buscar-pedido">Buscar</label>
            <input
              id="buscar-pedido"
              className="cf-input"
              type="search"
              placeholder="Número, FREC-000012, cliente o correo"
              value={texto}
              onChange={(e) => {
                setTexto(e.target.value);
                if (!e.target.value) filtrar(setBuscar)("");
              }}
            />
            <button className="cf-btn cf-btn--secundario" type="submit">Buscar</button>
          </form>
        </div>
      </div>

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}

      <div className="cf-panel cf-tabla-scroll" aria-busy={loading}>
        <table className="cf-tabla cf-tabla--filas">
          <thead>
            <tr>
              <th>Pedido</th>
              <th>Fecha</th>
              <th>Cliente</th>
              <th>Pago</th>
              <th>Estado</th>
              <th className="cf-num">Total</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data &&
              [1, 2, 3, 4, 5].map((n) => (
                <tr key={n}>
                  <td colSpan={6}><Skeleton alto="20px" /></td>
                </tr>
              ))}

            {!loading && pedidos.length === 0 && (
              <tr>
                <td colSpan={6} className="cf-vacio" style={{ textAlign: "center" }}>
                  No hay pedidos con estos filtros.
                </td>
              </tr>
            )}

            {pedidos.map((p) => (
              <tr key={p.id} style={{ opacity: loading ? 0.6 : 1 }}>
                <td>
                  <button className="cf-link" onClick={() => setAbierto(p)}>
                    #{p.id}
                  </button>
                  {nuevos.has(p.id) && <span className="cf-estado cf-estado--info cf-nuevo">Nuevo</span>}
                </td>
                <td className="cf-nowrap">{fechaCorta(p.fecha)}</td>
                <td>
                  {p.usuario?.nombre}
                  <span className="cf-caption cf-bloque">{p.usuario?.email}</span>
                </td>
                <td>
                  {p.pago ? (
                    <span className="cf-celda-pago">
                      <EstadoPago estado={p.pago.estado} />
                      <span className="cf-caption">{p.pago.metodoNombre}</span>
                    </span>
                  ) : (
                    <span className="cf-caption">—</span>
                  )}
                </td>
                <td><EstadoPedido estado={p.estado} /></td>
                <td className="cf-num">{pesos(p.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {paginas > 1 && (
        <nav className="cf-paginacion" aria-label="Páginas">
          <button
            className="cf-btn cf-btn--secundario"
            disabled={pagina === 0}
            onClick={() => setPagina((n) => n - 1)}
          >
            ← Anteriores
          </button>
          <span className="cf-caption">Página {pagina + 1} de {paginas}</span>
          <button
            className="cf-btn cf-btn--secundario"
            disabled={pagina + 1 >= paginas}
            onClick={() => setPagina((n) => n + 1)}
          >
            Siguientes →
          </button>
        </nav>
      )}

      {abierto && (
        <Detalle pedido={abierto} onCerrar={() => setAbierto(null)} onActualizado={actualizado} />
      )}
    </>
  );
}

/** AdminPedidos — /admin/pedidos: lista con filtros y cambio de estado. */
export default function AdminPedidos() {
  return (
    <SoloAdmin>
      <Contenido />
    </SoloAdmin>
  );
}
