import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { useStore } from "../../store/useStore";
import { RUTAS, fechaCorta, fechaLarga, pesos } from "../../lib/formato";
import { Skeleton } from "./Skeleton";
import { EstadoMembresia, EstadoPago, EstadoPedido } from "./Insignia";

const QUERY_MIS_PEDIDOS = `
  query MisPedidos {
    misPedidos {
      id fecha estado total piezas
      pago { metodoNombre estado }
    }
  }
`;

const QUERY_MEMBRESIA_CUENTA = `
  query MembresiaCuenta {
    miMembresia { id estado fin diasRestantes plan { nombre } canjeHoy { opcion } }
  }
`;

/** Resumen de la membresía con acceso al código del día. */
function TarjetaMembresia({ omitir }) {
  const { data, loading } = useGraphQLQuery(QUERY_MEMBRESIA_CUENTA, {}, { omitir });
  const m = data?.miMembresia;
  if (loading) return null;

  if (!m || m.estado === "vencida" || m.estado === "cancelada") {
    return (
      <div className="cf-panel cf-membresia-cuenta">
        <div>
          <strong>Tu café de cada día, ya pagado</strong>
          <p className="cf-caption" style={{ margin: 0 }}>
            Con una membresía canjeas un café (o café con comida) al día en el local.
          </p>
        </div>
        <a className="cf-btn" href={RUTAS.membresias}>Ver planes</a>
      </div>
    );
  }

  return (
    <div className="cf-panel cf-membresia-cuenta">
      <div>
        <span className="cf-caption">Tu membresía</span>
        <p style={{ margin: 0 }}>
          <strong>{m.plan?.nombre}</strong> <EstadoMembresia estado={m.estado} />
        </p>
        <p className="cf-caption" style={{ margin: 0 }}>
          {m.estado === "activa"
            ? `${m.diasRestantes} días restantes, hasta el ${fechaLarga(m.fin)} · ${
                m.canjeHoy ? `hoy ya canjeaste ${m.canjeHoy.opcion}` : "tu beneficio de hoy está disponible"
              }`
            : "Falta completar el pago para activarla"}
        </p>
      </div>
      <a className="cf-btn" href={RUTAS.miMembresia}>
        {m.estado === "activa" ? "Ver mi código de hoy" : "Completar pago"}
      </a>
    </div>
  );
}

/** Cuenta — datos del usuario, membresía, historial de pedidos y cerrar sesión. */
export default function Cuenta() {
  const sesion = useStore((s) => s.sesion);
  const cerrarSesion = useStore((s) => s.cerrarSesion);

  const { data, loading, error } = useGraphQLQuery(
    QUERY_MIS_PEDIDOS,
    {},
    { omitir: !sesion }
  );

  if (!sesion) {
    return (
      <>
        <h1>Tu cuenta</h1>
        <p className="cf-vacio">Inicia sesión para ver tus datos y tus pedidos.</p>
        <div className="cf-acciones">
          <a className="cf-btn" href={RUTAS.login(RUTAS.cuenta)}>Iniciar sesión</a>
          <a className="cf-btn cf-btn--secundario" href={RUTAS.registro(RUTAS.cuenta)}>
            Crear cuenta
          </a>
        </div>
      </>
    );
  }

  const { usuario } = sesion;
  const pedidos = data?.misPedidos ?? [];

  const salir = () => {
    cerrarSesion();
    window.location.href = RUTAS.inicio;
  };

  return (
    <>
      <div className="cf-resumen" style={{ marginTop: 0 }}>
        <h1 style={{ margin: 0 }}>Hola, {usuario.nombre}</h1>
        <button className="cf-btn cf-btn--secundario" onClick={salir}>
          Cerrar sesión
        </button>
      </div>

      <div className="cf-panel cf-datos">
        <div>
          <span className="cf-caption">Correo</span>
          <p>{usuario.email}</p>
        </div>
        <div>
          <span className="cf-caption">Teléfono</span>
          <p>{usuario.telefono || "Sin registrar"}</p>
        </div>
        {usuario.rol === "admin" && (
          <div>
            <span className="cf-caption">Rol</span>
            <p>
              Administrador · <a className="cf-link" href={RUTAS.admin}>Ir al panel</a>
            </p>
          </div>
        )}
      </div>

      <TarjetaMembresia omitir={!sesion} />

      <h2>Tus pedidos</h2>

      {loading && (
        <div className="cf-panel">
          <Skeleton alto="20px" />
          <div style={{ height: "var(--espacio-md)" }} />
          <Skeleton alto="20px" ancho="80%" />
        </div>
      )}

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span>
          No se pudieron cargar tus pedidos: {error}
        </p>
      )}

      {!loading && !error && pedidos.length === 0 && (
        <p className="cf-vacio">
          Todavía no tienes pedidos. <a className="cf-link" href={RUTAS.inicio}>Ve al catálogo</a>.
        </p>
      )}

      {!loading && pedidos.length > 0 && (
        <div className="cf-panel cf-tabla-scroll">
          <table className="cf-tabla">
            <thead>
              <tr>
                <th>Pedido</th>
                <th>Fecha</th>
                <th>Estado</th>
                <th>Pago</th>
                <th className="cf-num">Piezas</th>
                <th className="cf-num">Total</th>
              </tr>
            </thead>
            <tbody>
              {pedidos.map((p) => (
                <tr key={p.id}>
                  <td>
                    <a className="cf-link" href={RUTAS.pedidoDetalle(p.id)}>#{p.id}</a>
                  </td>
                  <td>{fechaCorta(p.fecha)}</td>
                  <td><EstadoPedido estado={p.estado} /></td>
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
                  <td className="cf-num">{p.piezas}</td>
                  <td className="cf-num">{pesos(p.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
