import { useState } from "react";
import { useGraphQLQuery } from "../../../hooks/useGraphQLQuery";
import { useRecargaEnVivo } from "../../../hooks/useRecargaEnVivo";
import { TIPOS } from "../../../store/enVivo";
import { RUTAS, fechaCorta, fechaLarga, pesos } from "../../../lib/formato";
import { EstadoMembresia } from "../Insignia";
import { Skeleton } from "../Skeleton";
import SoloAdmin from "./SoloAdmin";

const QUERY_CLIENTES = `
  query Clientes($buscar: String, $limite: Int!, $salto: Int!) {
    clientesAdmin(buscar: $buscar, limite: $limite, salto: $salto) {
      total
      clientes {
        id nombre email telefono creado pedidos totalGastado ultimaCompra
        membresia { id estado fin plan { nombre } }
      }
    }
  }
`;

const POR_PAGINA = 15;

function Contenido() {
  const [texto, setTexto] = useState("");
  const [buscar, setBuscar] = useState("");
  const [pagina, setPagina] = useState(0);

  const recarga = useRecargaEnVivo([...TIPOS.pedidos, ...TIPOS.membresias], 1200);
  const { data, loading, error } = useGraphQLQuery(
    QUERY_CLIENTES,
    { buscar: buscar || null, limite: POR_PAGINA, salto: pagina * POR_PAGINA },
    { recarga }
  );

  const total = data?.clientesAdmin.total ?? 0;
  const clientes = data?.clientesAdmin.clientes ?? [];
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  return (
    <>
      <div className="cf-admin__encabezado">
        <div>
          <h1>Clientes</h1>
          <p className="cf-caption" style={{ margin: 0 }}>
            Ordenados por lo que han gastado (solo pedidos pagados). {total} cliente{total === 1 ? "" : "s"}.
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
            </tr>
          </thead>
          <tbody>
            {loading && !data &&
              [1, 2, 3].map((n) => (
                <tr key={n}><td colSpan={6}><Skeleton alto="20px" /></td></tr>
              ))}
            {!loading && clientes.length === 0 && (
              <tr><td colSpan={6} className="cf-vacio" style={{ textAlign: "center" }}>Sin resultados.</td></tr>
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
