import { useState } from "react";
import { useGraphQLQuery } from "../../../hooks/useGraphQLQuery";
import { graphqlRequest } from "../../../lib/graphql";
import { useStore } from "../../../store/useStore";
import { useRecargaEnVivo } from "../../../hooks/useRecargaEnVivo";
import { TIPOS } from "../../../store/enVivo";
import { RUTAS, fechaCorta, fechaLarga, pesos } from "../../../lib/formato";
import { EstadoMembresia, Insignia } from "../Insignia";
import { Skeleton } from "../Skeleton";
import SoloAdmin from "./SoloAdmin";

const QUERY_CLIENTES = `
  query Clientes($buscar: String, $limite: Int!, $salto: Int!, $admins: Boolean!) {
    clientesAdmin(buscar: $buscar, limite: $limite, salto: $salto, incluirAdmins: $admins) {
      total
      clientes {
        id nombre email telefono rol activo creado pedidos totalGastado ultimaCompra
        membresia { id estado fin plan { nombre } }
      }
    }
  }
`;

const POR_PAGINA = 15;

const MUTATION_ROL = `mutation Rol($id: Int!, $rol: String!) { cambiarRolUsuario(id: $id, rol: $rol) { id rol activo } }`;
const MUTATION_ACTIVO = `mutation Activo($id: Int!, $activo: Boolean!) { cambiarActivoUsuario(id: $id, activo: $activo) { id rol activo } }`;

/** Rol y estado de la cuenta, con sus acciones (no se puede tocar la propia). */
function AccionesUsuario({ c, cambios, onCambio }) {
  const yo = useStore((s) => s.sesion?.usuario?.id);
  const actual = { rol: c.rol, activo: c.activo, ...cambios };
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);

  const ejecutar = async (mutation, variables, campo) => {
    setOcupado(true);
    setError(null);
    try {
      const r = await graphqlRequest(mutation, { id: c.id, ...variables });
      onCambio(c.id, r[campo]);
    } catch (err) {
      setError(err.message);
    }
    setOcupado(false);
  };

  return (
    <div className="cf-acciones cf-acciones--envolver">
      <Insignia tono={actual.activo ? "ok" : "error"}>{actual.activo ? "Activa" : "Desactivada"}</Insignia>
      {c.id === yo ? (
        <span className="cf-caption">Tu cuenta ({actual.rol})</span>
      ) : (
        <>
          <label className="cf-sr" htmlFor={`rol-${c.id}`}>Rol de {c.nombre}</label>
          <select
            id={`rol-${c.id}`}
            className="cf-input"
            style={{ width: "auto" }}
            value={actual.rol}
            disabled={ocupado}
            onChange={(e) => ejecutar(MUTATION_ROL, { rol: e.target.value }, "cambiarRolUsuario")}
          >
            <option value="cliente">Cliente</option>
            <option value="admin">Admin</option>
          </select>
          <button
            className={`cf-btn cf-btn--secundario${actual.activo ? " cf-btn--texto-peligro" : ""}`}
            disabled={ocupado}
            onClick={() => ejecutar(MUTATION_ACTIVO, { activo: !actual.activo }, "cambiarActivoUsuario")}
          >
            {actual.activo ? "Desactivar" : "Reactivar"}
          </button>
        </>
      )}
      {error && <span className="cf-caption" role="alert" style={{ color: "var(--color-error)" }}>{error}</span>}
    </div>
  );
}

function Contenido() {
  const [texto, setTexto] = useState("");
  const [buscar, setBuscar] = useState("");
  const [pagina, setPagina] = useState(0);
  const [admins, setAdmins] = useState(false);
  const [cambios, setCambios] = useState({});
  const anotar = (id, u) => setCambios((c) => ({ ...c, [id]: { rol: u.rol, activo: u.activo } }));

  const recarga = useRecargaEnVivo([...TIPOS.pedidos, ...TIPOS.membresias], 1200);
  const { data, loading, error } = useGraphQLQuery(
    QUERY_CLIENTES,
    { buscar: buscar || null, limite: POR_PAGINA, salto: pagina * POR_PAGINA, admins },
    { recarga }
  );

  const total = data?.clientesAdmin.total ?? 0;
  const clientes = data?.clientesAdmin.clientes ?? [];
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  return (
    <>
      <div className="cf-admin__encabezado">
        <div>
          <h1>Clientes y usuarios</h1>
          <p className="cf-caption" style={{ margin: 0 }}>
            Ordenados por lo que han gastado (solo pedidos pagados). {total} cuenta{total === 1 ? "" : "s"}.
            Desactivar una cuenta le cierra la sesión sin borrar su historial.
          </p>
        </div>
      </div>

      <form
        className="cf-buscar cf-filtros__fila"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          setBuscar(texto.trim());
          setPagina(0);
        }}
      >
        <label className="cf-sr" htmlFor="buscar-cliente">Buscar cliente</label>
        <input
          id="buscar-cliente"
          className="cf-input"
          type="search"
          placeholder="Nombre, correo o teléfono"
          value={texto}
          onChange={(e) => {
            setTexto(e.target.value);
            if (!e.target.value) {
              setBuscar("");
              setPagina(0);
            }
          }}
        />
        <button className="cf-btn cf-btn--secundario" type="submit">Buscar</button>
        <label className="cf-check">
          <input
            type="checkbox"
            checked={admins}
            onChange={(e) => {
              setAdmins(e.target.checked);
              setPagina(0);
            }}
          />
          Incluir administradores
        </label>
      </form>

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}

      <div className="cf-panel cf-tabla-scroll" aria-busy={loading}>
        <table className="cf-tabla cf-tabla--filas">
          <thead>
            <tr>
              <th>Cliente</th>
              <th>Teléfono</th>
              <th className="cf-num">Pedidos</th>
              <th className="cf-num">Gastado</th>
              <th>Última compra</th>
              <th>Membresía</th>
              <th>Cuenta</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data &&
              [1, 2, 3].map((n) => (
                <tr key={n}><td colSpan={7}><Skeleton alto="20px" /></td></tr>
              ))}
            {!loading && clientes.length === 0 && (
              <tr><td colSpan={7} className="cf-vacio" style={{ textAlign: "center" }}>Sin resultados.</td></tr>
            )}
            {clientes.map((c) => (
              <tr key={c.id} style={{ opacity: loading ? 0.6 : 1 }}>
                <td>
                  {c.nombre}
                  <span className="cf-caption cf-bloque">{c.email}</span>
                  {c.creado && <span className="cf-caption cf-bloque">Desde {fechaLarga(c.creado)}</span>}
                </td>
                <td className="cf-nowrap">{c.telefono || <span className="cf-caption">—</span>}</td>
                <td className="cf-num">
                  {c.pedidos > 0 ? (
                    <a className="cf-link" href={`${RUTAS.adminPedidos}?buscar=${encodeURIComponent(c.email)}`}>
                      {c.pedidos}
                    </a>
                  ) : (
                    0
                  )}
                </td>
                <td className="cf-num">{pesos(c.totalGastado)}</td>
                <td className="cf-nowrap">{c.ultimaCompra ? fechaCorta(c.ultimaCompra) : "—"}</td>
                <td>
                  {c.membresia ? (
                    <a
                      className="cf-celda-pago"
                      href={`${RUTAS.adminMembresias}?buscar=${encodeURIComponent(c.email)}`}
                      style={{ textDecoration: "none", color: "inherit" }}
                    >
                      <EstadoMembresia estado={c.membresia.estado} />
                      <span className="cf-caption">
                        {c.membresia.plan?.nombre} · hasta {fechaLarga(c.membresia.fin)}
                      </span>
                    </a>
                  ) : (
                    <span className="cf-caption">Sin membresía</span>
                  )}
                </td>
                <td>
                  <AccionesUsuario c={c} cambios={cambios[c.id]} onCambio={anotar} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {paginas > 1 && (
        <nav className="cf-paginacion" aria-label="Páginas">
          <button className="cf-btn cf-btn--secundario" disabled={pagina === 0} onClick={() => setPagina((n) => n - 1)}>
            ← Anteriores
          </button>
          <span className="cf-caption">Página {pagina + 1} de {paginas}</span>
          <button className="cf-btn cf-btn--secundario" disabled={pagina + 1 >= paginas} onClick={() => setPagina((n) => n + 1)}>
            Siguientes →
          </button>
        </nav>
      )}
    </>
  );
}

/** AdminClientes — /admin/clientes: compras y membresía de cada cliente. */
export default function AdminClientes() {
  return (
    <SoloAdmin>
      <Contenido />
    </SoloAdmin>
  );
}
