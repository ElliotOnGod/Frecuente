import { useRef, useState } from "react";
import { graphqlRequest } from "../../../lib/graphql";
import { useGraphQLQuery } from "../../../hooks/useGraphQLQuery";
import { useRecargaEnVivo } from "../../../hooks/useRecargaEnVivo";
import { TIPOS } from "../../../store/enVivo";
import { fechaLarga, hora } from "../../../lib/formato";
import { EstadoMembresia } from "../Insignia";
import SoloAdmin from "./SoloAdmin";

const CAMPOS = `
  id estado referencia fin diasRestantes canjesTotal
  usuario { nombre email }
  plan { nombre opciones incluye }
  canjeHoy { opcion fecha nota }
`;

const QUERY_POR_CODIGO = `
  query PorCodigo($codigo: String!) { membresiaPorCodigo(codigo: $codigo) { ${CAMPOS} } }
`;
const QUERY_BUSCAR = `
  query BuscarMiembro($buscar: String) {
    membresiasAdmin(estado: "activa", buscar: $buscar, limite: 8, salto: 0) { membresias { ${CAMPOS} } }
  }
`;
const MUTATION_CANJEAR = `
  mutation Canjear($codigo: String, $membresiaId: Int, $opcion: String!, $nota: String!) {
    canjearMembresia(codigo: $codigo, membresiaId: $membresiaId, opcion: $opcion, nota: $nota) { ${CAMPOS} }
  }
`;
const QUERY_CANJES_HOY = `
  query CanjesHoy { canjesHoy { membresiaId cliente plan opcion nota fecha } }
`;

/** Tarjeta del miembro encontrado, con las opciones del plan como botones. */
function Miembro({ m, codigo, onCanjeado, onLimpiar }) {
  const [opcion, setOpcion] = useState(m.plan?.opciones?.[0] ?? "");
  const [nota, setNota] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  const puede = m.estado === "activa" && !m.canjeHoy;

  const canjear = async () => {
    setEnviando(true);
    setError(null);
    try {
      const data = await graphqlRequest(MUTATION_CANJEAR, {
        codigo: codigo || null,
        membresiaId: codigo ? null : m.id,
        opcion,
        nota,
      });
      onCanjeado(data.canjearMembresia);
    } catch (err) {
      setError(err.message);
    }
    setEnviando(false);
  };

  return (
    <section className="cf-panel cf-miembro" aria-labelledby="miembro-nombre">
      <div className="cf-resumen" style={{ marginTop: 0 }}>
        <div>
          <h2 id="miembro-nombre" className="cf-panel__titulo">{m.usuario?.nombre}</h2>
          <span className="cf-caption">{m.plan?.nombre} · {m.referencia} · {m.usuario?.email}</span>
        </div>
        <EstadoMembresia estado={m.estado} />
      </div>

      {m.estado === "activa" && (
        <p className="cf-caption">
          Vigente hasta el {fechaLarga(m.fin)} ({m.diasRestantes} días) · {m.canjesTotal} canjes usados
        </p>
      )}

      {m.canjeHoy ? (
        <p className="cf-alerta cf-alerta--warning" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span>
          Ya canjeó hoy: <strong>&nbsp;{m.canjeHoy.opcion}</strong>&nbsp;a las {hora(m.canjeHoy.fecha)} — no se puede canjear otra vez.
        </p>
      ) : m.estado !== "activa" ? (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span>
          Esta membresía no está activa, no se puede canjear.
        </p>
      ) : (
        <>
          <fieldset className="cf-opciones-canje">
            <legend className="cf-label">¿Qué se lleva hoy?</legend>
            {m.plan?.opciones.map((o) => (
              <button
                key={o}
                type="button"
                className="cf-opcion-canje"
                aria-pressed={opcion === o}
                onClick={() => setOpcion(o)}
              >
                {o}
              </button>
            ))}
          </fieldset>
          <div className="cf-campo">
            <label className="cf-label" htmlFor="canje-nota">Nota (opcional)</label>
            <input
              id="canje-nota"
              className="cf-input"
              maxLength={120}
              placeholder="Ej. leche de avena, sin azúcar"
              value={nota}
              onChange={(e) => setNota(e.target.value)}
            />
          </div>
        </>
      )}

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}

      <div className="cf-acciones cf-acciones--envolver">
        {puede && (
          <button className="cf-btn" onClick={canjear} disabled={enviando || !opcion}>
            {enviando ? "Registrando…" : `Registrar canje: ${opcion}`}
          </button>
        )}
        <button className="cf-btn cf-btn--secundario" onClick={onLimpiar}>Siguiente cliente</button>
      </div>
    </section>
  );
}

function Contenido() {
  const [codigo, setCodigo] = useState("");
  const [buscando, setBuscando] = useState(false);
  const [error, setError] = useState(null);
  const [miembro, setMiembro] = useState(null);
  const [usado, setUsado] = useState(""); // código con el que se encontró
  const [exito, setExito] = useState(null);
  const [nombre, setNombre] = useState("");
  const [resultados, setResultados] = useState(null);
  const input = useRef(null);

  const recarga = useRecargaEnVivo(TIPOS.canjes, 200);
  const { data } = useGraphQLQuery(QUERY_CANJES_HOY, {}, { recarga });
  const canjes = data?.canjesHoy ?? [];

  const limpiar = () => {
    setMiembro(null);
    setCodigo("");
    setUsado("");
    setError(null);
    setResultados(null);
    setNombre("");
    setTimeout(() => input.current?.focus(), 0);
  };

  const buscarCodigo = async (e) => {
    e.preventDefault();
    setBuscando(true);
    setError(null);
    setExito(null);
    try {
      const d = await graphqlRequest(QUERY_POR_CODIGO, { codigo });
      setMiembro(d.membresiaPorCodigo);
      setUsado(codigo);
    } catch (err) {
      setMiembro(null);
      setError(err.message);
    }
    setBuscando(false);
  };

  const buscarNombre = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const d = await graphqlRequest(QUERY_BUSCAR, { buscar: nombre || null });
      setResultados(d.membresiasAdmin.membresias);
    } catch (err) {
      setError(err.message);
    }
  };

  const canjeado = (m) => {
    setExito(`${m.usuario?.nombre}: ${m.canjeHoy?.opcion} registrado a las ${hora(m.canjeHoy?.fecha)}.`);
    limpiar();
  };

  return (
    <>
      <div className="cf-admin__encabezado">
        <div>
          <h1>Caja: canjes de membresía</h1>
          <p className="cf-caption" style={{ margin: 0 }}>
            El cliente enseña su código de hoy (en "Mi membresía"). Un canje por persona al día.
          </p>
        </div>
      </div>

      {exito && (
        <p className="cf-alerta cf-alerta--success" role="status">
          <span className="cf-icon" aria-hidden="true">✓</span> {exito}
        </p>
      )}

      <div className="cf-caja">
        <div>
          <form className="cf-panel cf-caja__codigo" onSubmit={buscarCodigo}>
            <label className="cf-label" htmlFor="caja-codigo">Código del cliente</label>
            <div className="cf-acciones">
              <input
                id="caja-codigo"
                ref={input}
                className="cf-input cf-input--codigo"
                placeholder="FM12-K7QX2P"
                autoComplete="off"
                autoCapitalize="characters"
                spellCheck={false}
                autoFocus
                value={codigo}
                onChange={(e) => setCodigo(e.target.value.toUpperCase())}
                aria-invalid={error ? "true" : undefined}
              />
              <button className="cf-btn" type="submit" disabled={!codigo.trim() || buscando}>
                {buscando ? "Buscando…" : "Validar"}
              </button>
            </div>
            {error && (
              <p className="cf-alerta cf-alerta--error" role="alert" style={{ marginTop: "var(--espacio-md)" }}>
                <span className="cf-icon" aria-hidden="true">!</span> {error}
              </p>
            )}
          </form>

          {miembro ? (
            <Miembro key={miembro.id} m={miembro} codigo={usado} onCanjeado={canjeado} onLimpiar={limpiar} />
          ) : (
            <details className="cf-panel cf-caja__sin-codigo">
              <summary>¿El cliente no tiene su código a la mano? Búscalo por nombre</summary>
              <form className="cf-buscar" onSubmit={buscarNombre} style={{ marginTop: "var(--espacio-md)" }}>
                <label className="cf-sr" htmlFor="caja-nombre">Nombre o correo</label>
                <input
                  id="caja-nombre"
                  className="cf-input"
                  placeholder="Nombre o correo"
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                />
                <button className="cf-btn cf-btn--secundario" type="submit">Buscar</button>
              </form>
              {resultados && (
                <ul className="cf-resultados">
                  {resultados.length === 0 && <li className="cf-caption">Sin miembros activos con ese nombre.</li>}
                  {resultados.map((m) => (
                    <li key={m.id}>
                      <span>
                        <strong>{m.usuario?.nombre}</strong>
                        <span className="cf-caption cf-bloque">{m.plan?.nombre} · {m.usuario?.email}</span>
                      </span>
                      <button className="cf-btn cf-btn--secundario" onClick={() => { setMiembro(m); setUsado(""); }}>
                        Elegir
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <p className="cf-ayuda">Pide una identificación: sin código no hay forma de comprobar que es la persona.</p>
            </details>
          )}
        </div>

        <section className="cf-panel" aria-labelledby="titulo-hoy">
          <h2 id="titulo-hoy" className="cf-panel__titulo">Canjes de hoy ({canjes.length})</h2>
          <span className="cf-caption">Se actualiza solo con los canjes de todas las cajas.</span>
          {canjes.length === 0 ? (
            <p className="cf-vacio" style={{ paddingBottom: 0 }}>Todavía no hay canjes hoy.</p>
          ) : (
            <ol className="cf-feed">
              {canjes.map((c) => (
                <li key={`${c.membresiaId}-${c.fecha}`} className="cf-feed__item">
                  <span className="cf-feed__icono" aria-hidden="true">☕</span>
                  <span>
                    <strong>{c.cliente}</strong>: {c.opcion}
                    <span className="cf-caption cf-bloque">
                      {hora(c.fecha)} · {c.plan}{c.nota ? ` · ${c.nota}` : ""}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </>
  );
}

/** AdminCaja — /admin/caja: validar el código del día y registrar el canje. */
export default function AdminCaja() {
  return (
    <SoloAdmin>
      <Contenido />
    </SoloAdmin>
  );
}
