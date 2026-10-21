import { useEffect, useState } from "react";
import { graphqlRequest } from "../../../lib/graphql";
import { useGraphQLQuery } from "../../../hooks/useGraphQLQuery";
import { useRecargaEnVivo } from "../../../hooks/useRecargaEnVivo";
import { TIPOS } from "../../../store/enVivo";
import { fechaCorta, fechaLarga, hora, pesos } from "../../../lib/formato";
import { EstadoMembresia, EstadoPago } from "../Insignia";
import { Skeleton } from "../Skeleton";
import SoloAdmin from "./SoloAdmin";

const CAMPOS = `
  id estado precio referencia creada inicio fin diasRestantes canjesTotal
  usuario { nombre email telefono }
  plan { id nombre }
  canjeHoy { opcion fecha }
  canjes(limite: 10) { dia fecha opcion nota }
  pago { metodo metodoNombre estado modo pagoId detalle fechaPago }
`;

const QUERY_MIEMBROS = `
  query Miembros($estado: String, $planId: Int, $buscar: String, $limite: Int!, $salto: Int!) {
    membresiasAdmin(estado: $estado, planId: $planId, buscar: $buscar, limite: $limite, salto: $salto) {
      total
      membresias { ${CAMPOS} }
    }
    planes(incluirInactivos: true) { id nombre }
  }
`;

const QUERY_PLANES = `
  query PlanesAdmin {
    planes(incluirInactivos: true) { id nombre descripcion precio incluye opciones activo miembrosActivos }
  }
`;

const MUTATION_CONFIRMAR = `
  mutation Confirmar($id: Int!) { confirmarPagoMembresiaManual(id: $id) { ${CAMPOS} } }
`;
const MUTATION_CANCELAR = `
  mutation Cancelar($id: Int!) { cancelarMembresia(id: $id) { ${CAMPOS} } }
`;
const CAMPOS_PLAN = "id nombre descripcion precio incluye opciones activo miembrosActivos";
const MUTATION_CREAR_PLAN = `
  mutation CrearPlan($input: PlanInput!) { crearPlan(input: $input) { ${CAMPOS_PLAN} } }
`;
const MUTATION_ACTUALIZAR_PLAN = `
  mutation ActualizarPlan($id: Int!, $input: PlanUpdateInput!) {
    actualizarPlan(id: $id, input: $input) { ${CAMPOS_PLAN} }
  }
`;

const FILTROS = [
  { valor: "", texto: "Todas" },
  { valor: "activa", texto: "Activas" },
  { valor: "pendiente", texto: "Por pagar" },
  { valor: "programada", texto: "Programadas" },
  { valor: "vencida", texto: "Vencidas" },
  { valor: "cancelada", texto: "Canceladas" },
];

const POR_PAGINA = 15;

/** Detalle de una membresía con sus acciones. */
function Detalle({ m, onCerrar, onActualizada }) {
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const [confirmarCancelar, setConfirmarCancelar] = useState(false);

  useEffect(() => {
    const esc = (e) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onCerrar]);

  const ejecutar = async (query) => {
    setOcupado(true);
    setError(null);
    try {
      const data = await graphqlRequest(query, { id: m.id });
      onActualizada(Object.values(data)[0]);
      setConfirmarCancelar(false);
    } catch (err) {
      setError(err.message);
    }
    setOcupado(false);
  };

  return (
    <div className="cf-modal-fondo" onClick={onCerrar}>
      <aside
        className="cf-modal cf-detalle"
        role="dialog"
        aria-modal="true"
        aria-labelledby="memb-titulo"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="cf-modal__barra">
          <div>
            <h2 id="memb-titulo" style={{ margin: 0 }}>{m.plan?.nombre}</h2>
            <span className="cf-caption">{m.referencia} · contratada {fechaCorta(m.creada)}</span>
          </div>
          <button className="cf-btn cf-btn--icono" aria-label="Cerrar" onClick={onCerrar} autoFocus>✕</button>
        </div>

        <div className="cf-detalle__estados">
          <EstadoMembresia estado={m.estado} />
          <EstadoPago estado={m.pago?.estado} />
        </div>

        {error && (
          <p className="cf-alerta cf-alerta--error" role="alert">
            <span className="cf-icon" aria-hidden="true">!</span> {error}
          </p>
        )}

        <dl className="cf-detalle__datos">
          <div>
            <dt className="cf-caption">Cliente</dt>
            <dd>{m.usuario?.nombre}</dd>
            <dd className="cf-caption">{m.usuario?.email}</dd>
            {m.usuario?.telefono && <dd className="cf-caption">{m.usuario.telefono}</dd>}
          </div>
          <div>
            <dt className="cf-caption">Pago</dt>
            <dd>{m.pago?.metodoNombre} · {pesos(m.precio)}</dd>
            {m.pago?.pagoId && <dd className="cf-caption">Folio: {m.pago.pagoId}</dd>}
            {m.pago?.detalle && <dd className="cf-caption">{m.pago.detalle}</dd>}
          </div>
          <div>
            <dt className="cf-caption">Vigencia</dt>
            <dd>{m.inicio ? `${fechaLarga(m.inicio)} – ${fechaLarga(m.fin)}` : "Empieza al pagar"}</dd>
            {m.estado === "activa" && <dd className="cf-caption">{m.diasRestantes} días restantes</dd>}
          </div>
          <div>
            <dt className="cf-caption">Canjes</dt>
            <dd>{m.canjesTotal} en total</dd>
            <dd className="cf-caption">
              {m.canjeHoy ? `Hoy: ${m.canjeHoy.opcion} a las ${hora(m.canjeHoy.fecha)}` : "Hoy: sin canjear"}
            </dd>
          </div>
        </dl>

        {m.canjes.length > 0 && (
          <table className="cf-tabla">
            <thead>
              <tr><th>Día</th><th>Hora</th><th>Canje</th></tr>
            </thead>
            <tbody>
              {m.canjes.map((c) => (
                <tr key={c.dia}>
                  <td>{fechaLarga(c.fecha)}</td>
                  <td>{hora(c.fecha)}</td>
                  <td>{c.opcion}{c.nota && <span className="cf-caption cf-bloque">{c.nota}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {m.estado !== "cancelada" && (
          <div className="cf-detalle__acciones">
            {confirmarCancelar ? (
              <div role="group" aria-label="Confirmar cancelación">
                <p style={{ marginTop: 0 }}>
                  Se cancela la membresía.
                  {m.pago?.estado === "aprobado" && " Como ya estaba pagada, quedará marcada para reembolsar."}
                </p>
                <div className="cf-acciones">
                  <button className="cf-btn cf-btn--peligro" disabled={ocupado} onClick={() => ejecutar(MUTATION_CANCELAR)}>
                    Sí, cancelar
                  </button>
                  <button className="cf-btn cf-btn--secundario" onClick={() => setConfirmarCancelar(false)}>Volver</button>
                </div>
              </div>
            ) : (
              <div className="cf-acciones cf-acciones--envolver">
                {m.estado === "pendiente" && (
                  <button className="cf-btn" disabled={ocupado} onClick={() => ejecutar(MUTATION_CONFIRMAR)}>
                    {m.pago?.metodo === "efectivo" ? "Cobrado en el local: activar" : "Confirmar pago recibido"}
                  </button>
                )}
                <button
                  className="cf-btn cf-btn--secundario cf-btn--texto-peligro"
                  disabled={ocupado}
                  onClick={() => setConfirmarCancelar(true)}
                >
                  Cancelar membresía
                </button>
              </div>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}

function Miembros() {
  const inicial = new URLSearchParams(window.location.search);
  const [estado, setEstado] = useState(inicial.get("estado") || "");
  const [planId, setPlanId] = useState("");
  const [texto, setTexto] = useState(inicial.get("buscar") || "");
  const [buscar, setBuscar] = useState(inicial.get("buscar") || "");
  const [pagina, setPagina] = useState(0);
  const [abierta, setAbierta] = useState(null);

  const recarga = useRecargaEnVivo(TIPOS.membresias);
  const { data, loading, error } = useGraphQLQuery(
    QUERY_MIEMBROS,
    {
      estado: estado || null,
      planId: planId ? Number(planId) : null,
      buscar: buscar || null,
      limite: POR_PAGINA,
      salto: pagina * POR_PAGINA,
    },
    { recarga }
  );

  const total = data?.membresiasAdmin.total ?? 0;
  const lista = data?.membresiasAdmin.membresias ?? [];
  const planes = data?.planes ?? [];
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  const filtrar = (fn) => (v) => {
    fn(v);
    setPagina(0);
  };

  return (
    <>
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
          <label className="cf-sr" htmlFor="filtro-plan">Plan</label>
          <select id="filtro-plan" className="cf-input" value={planId} onChange={(e) => filtrar(setPlanId)(e.target.value)}>
            <option value="">Todos los planes</option>
            {planes.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
          <form
            className="cf-buscar"
            role="search"
            onSubmit={(e) => {
              e.preventDefault();
              filtrar(setBuscar)(texto.trim());
            }}
          >
            <label className="cf-sr" htmlFor="buscar-memb">Buscar</label>
            <input
              id="buscar-memb"
              className="cf-input"
              type="search"
              placeholder="Cliente, correo o MEMB-000012"
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
              <th>Membresía</th>
              <th>Cliente</th>
              <th>Plan</th>
              <th>Estado</th>
              <th>Vence</th>
              <th>Hoy</th>
              <th className="cf-num">Precio</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data &&
              [1, 2, 3, 4].map((n) => (
                <tr key={n}><td colSpan={7}><Skeleton alto="20px" /></td></tr>
              ))}
            {!loading && lista.length === 0 && (
              <tr><td colSpan={7} className="cf-vacio" style={{ textAlign: "center" }}>No hay membresías con estos filtros.</td></tr>
            )}
            {lista.map((m) => (
              <tr key={m.id} style={{ opacity: loading ? 0.6 : 1 }}>
                <td>
                  <button className="cf-link" onClick={() => setAbierta(m)}>{m.referencia}</button>
                </td>
                <td>
                  {m.usuario?.nombre}
                  <span className="cf-caption cf-bloque">{m.usuario?.email}</span>
                </td>
                <td>{m.plan?.nombre}</td>
                <td>
                  <span className="cf-celda-pago">
                    <EstadoMembresia estado={m.estado} />
                    {m.estado === "pendiente" && <span className="cf-caption">{m.pago?.metodoNombre}</span>}
                  </span>
                </td>
                <td className="cf-nowrap">
                  {m.fin ? fechaLarga(m.fin) : "—"}
                  {m.estado === "activa" && <span className="cf-caption cf-bloque">{m.diasRestantes} días</span>}
                </td>
                <td>
                  {m.estado === "activa" ? (
                    m.canjeHoy ? (
                      <span className="cf-estado cf-estado--ok">Canjeó</span>
                    ) : (
                      <span className="cf-caption">Disponible</span>
                    )
                  ) : (
                    <span className="cf-caption">—</span>
                  )}
                </td>
                <td className="cf-num">{pesos(m.precio)}</td>
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
          <span className="cf-caption">Página {pagina + 1} de {paginas} · {total} membresías</span>
          <button className="cf-btn cf-btn--secundario" disabled={pagina + 1 >= paginas} onClick={() => setPagina((n) => n + 1)}>
            Siguientes →
          </button>
        </nav>
      )}

      {abierta && (
        <Detalle m={abierta} onCerrar={() => setAbierta(null)} onActualizada={setAbierta} />
      )}
    </>
  );
}

/** Formulario de un plan (crear o editar). */
function FormPlan({ plan, onGuardado, onCancelar }) {
  const [f, setF] = useState({
    nombre: plan?.nombre ?? "",
    precio: plan ? String(plan.precio) : "",
    descripcion: plan?.descripcion ?? "",
    incluye: (plan?.incluye ?? []).join("\n"),
    opciones: (plan?.opciones ?? []).join("\n"),
    activo: plan?.activo ?? true,
  });
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const campo = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const lineas = (t) => t.split("\n").map((x) => x.trim()).filter(Boolean);
  const pre = `plan-${plan?.id ?? "nuevo"}`;

  const guardar = async (e) => {
    e.preventDefault();
    if (!f.nombre.trim()) return setError("Escribe el nombre del plan.");
    if (!(Number(f.precio) > 0)) return setError("El precio debe ser mayor a cero.");
    if (lineas(f.opciones).length === 0) return setError("Agrega al menos una opción para canjear.");
    setEnviando(true);
    setError(null);
    const input = {
      nombre: f.nombre.trim(),
      precio: Number(f.precio),
      descripcion: f.descripcion.trim(),
      incluye: lineas(f.incluye),
      opciones: lineas(f.opciones),
      activo: f.activo,
    };
    try {
      const data = plan
        ? await graphqlRequest(MUTATION_ACTUALIZAR_PLAN, { id: plan.id, input })
        : await graphqlRequest(MUTATION_CREAR_PLAN, { input });
      onGuardado(plan ? data.actualizarPlan : data.crearPlan);
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <form className="cf-plan cf-plan--form" onSubmit={guardar} noValidate>
      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}
      <div className="cf-form-fila">
        <div className="cf-campo">
          <label className="cf-label" htmlFor={`${pre}-nombre`}>Nombre</label>
          <input id={`${pre}-nombre`} className="cf-input" value={f.nombre} onChange={campo("nombre")} />
        </div>
        <div className="cf-campo">
          <label className="cf-label" htmlFor={`${pre}-precio`}>Precio (30 días)</label>
          <input id={`${pre}-precio`} className="cf-input" type="number" min="1" step="1" inputMode="decimal" value={f.precio} onChange={campo("precio")} />
        </div>
      </div>
      <div className="cf-campo">
        <label className="cf-label" htmlFor={`${pre}-desc`}>Descripción</label>
        <input id={`${pre}-desc`} className="cf-input" value={f.descripcion} onChange={campo("descripcion")} />
      </div>
      <div className="cf-campo">
        <label className="cf-label" htmlFor={`${pre}-incluye`}>Qué incluye (uno por renglón, lo ve el cliente)</label>
        <textarea id={`${pre}-incluye`} className="cf-input cf-textarea" rows={3} value={f.incluye} onChange={campo("incluye")} />
      </div>
      <div className="cf-campo">
        <label className="cf-label" htmlFor={`${pre}-opciones`}>Opciones para canjear en caja (una por renglón)</label>
        <textarea id={`${pre}-opciones`} className="cf-input cf-textarea" rows={3} value={f.opciones} onChange={campo("opciones")} />
      </div>
      <label className="cf-check">
        <input type="checkbox" checked={f.activo} onChange={campo("activo")} />
        A la venta (si lo desactivas, los miembros actuales lo conservan)
      </label>
      {plan && (
        <p className="cf-ayuda" style={{ marginTop: 0 }}>
          Cambiar el precio no afecta a quien ya pagó: cada membresía guarda su precio.
        </p>
      )}
      <div className="cf-acciones">
        <button className="cf-btn" type="submit" disabled={enviando}>
          {enviando ? "Guardando…" : plan ? "Guardar cambios" : "Crear plan"}
        </button>
        <button className="cf-btn cf-btn--secundario" type="button" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  );
}

function PlanesAdmin() {
  const [recarga, setRecarga] = useState(0);
  const enVivo = useRecargaEnVivo(TIPOS.membresias);
  const { data, loading, error } = useGraphQLQuery(QUERY_PLANES, {}, { recarga: recarga + enVivo });
  const [editando, setEditando] = useState(null); // id del plan, "nuevo" o null
  const [aviso, setAviso] = useState(null);
  const planes = data?.planes ?? [];

  const guardado = (p) => {
    setEditando(null);
    setAviso(`Se guardó el plan ${p.nombre}.`);
    setRecarga((n) => n + 1);
  };

  return (
    <>
      <div className="cf-admin__encabezado" style={{ marginBottom: "var(--espacio-md)" }}>
        <p className="cf-caption" style={{ margin: 0 }}>
          Los planes activos aparecen en /membresias. Las "opciones para canjear" son los botones que ve la caja.
        </p>
        {editando !== "nuevo" && (
          <button className="cf-btn" onClick={() => setEditando("nuevo")}>+ Nuevo plan</button>
        )}
      </div>

      {aviso && (
        <p className="cf-alerta cf-alerta--success" role="status">
          <span className="cf-icon" aria-hidden="true">✓</span> {aviso}
        </p>
      )}
      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}

      <div className="cf-planes">
        {editando === "nuevo" && <FormPlan onGuardado={guardado} onCancelar={() => setEditando(null)} />}
        {loading && !data && [1, 2, 3].map((n) => <div className="cf-plan" key={n}><Skeleton alto="160px" /></div>)}
        {planes.map((p) =>
          editando === p.id ? (
            <FormPlan key={p.id} plan={p} onGuardado={guardado} onCancelar={() => setEditando(null)} />
          ) : (
            <article key={p.id} className="cf-plan" data-inactivo={p.activo ? undefined : "true"}>
              <div className="cf-resumen" style={{ marginTop: 0 }}>
                <h2 className="cf-plan__nombre">{p.nombre}</h2>
                {p.activo ? (
                  <span className="cf-estado cf-estado--ok">A la venta</span>
                ) : (
                  <span className="cf-estado">Pausado</span>
                )}
              </div>
              <p className="cf-plan__precio"><strong>{pesos(p.precio)}</strong> <span className="cf-caption">/ 30 días</span></p>
              <p className="cf-caption" style={{ marginTop: 0 }}>{p.descripcion}</p>
              <ul className="cf-plan__incluye">
                {p.incluye.map((x) => <li key={x}>{x}</li>)}
              </ul>
              <p className="cf-caption">
                <strong>{p.miembrosActivos}</strong> miembro{p.miembrosActivos === 1 ? "" : "s"} activo
                {p.miembrosActivos === 1 ? "" : "s"} · Opciones: {p.opciones.join(", ") || "—"}
              </p>
              <button className="cf-btn cf-btn--secundario cf-btn--bloque" onClick={() => setEditando(p.id)}>
                Editar
              </button>
            </article>
          )
        )}
      </div>
    </>
  );
}

function Contenido() {
  const [vista, setVista] = useState("miembros");
  return (
    <>
      <div className="cf-admin__encabezado">
        <h1>Membresías</h1>
        <div className="cf-segmentos" role="group" aria-label="Sección">
          <button className="cf-segmentos__btn" aria-pressed={vista === "miembros"} onClick={() => setVista("miembros")}>
            Miembros
          </button>
          <button className="cf-segmentos__btn" aria-pressed={vista === "planes"} onClick={() => setVista("planes")}>
            Planes
          </button>
        </div>
      </div>
      {vista === "miembros" ? <Miembros /> : <PlanesAdmin />}
    </>
  );
}

/** AdminMembresias — /admin/membresias: miembros (en vivo) y planes. */
export default function AdminMembresias() {
  return (
    <SoloAdmin>
      <Contenido />
    </SoloAdmin>
  );
}
