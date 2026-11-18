/**
 * DatosFiscalesForm — datos fiscales opcionales del checkout para la
 * prefactura (RQF90): RFC, nombre o razón social, régimen fiscal, código
 * postal fiscal y uso del CFDI. Los catálogos vienen de catalogosCfdi.
 *
 * Sin datos, la prefactura sale a público en general con el RFC genérico
 * XAXX010101000 (RQNF112). El RFC se revisa aquí y otra vez en el servidor
 * (RQNF111).
 */
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { QUERY_CATALOGOS_CFDI, RFC_PUBLICO_GENERAL } from "../../lib/cfdi";

export default function DatosFiscalesForm({ valor, onCambio, errores = {} }) {
  const { data } = useGraphQLQuery(QUERY_CATALOGOS_CFDI, {}, { omitir: !valor.activa });
  const catalogos = data?.catalogosCfdi;
  const datos = valor.datos;

  const cambiar = (campo) => (e) => onCambio({ ...valor, datos: { ...datos, [campo]: e.target.value } });

  const campo = (id, etiqueta, nombre, props = {}) => (
    <div className="cf-campo">
      <label className="cf-label" htmlFor={id}>{etiqueta}</label>
      <input
        id={id}
        className="cf-input"
        value={datos[nombre]}
        onChange={cambiar(nombre)}
        aria-invalid={errores[nombre] ? "true" : undefined}
        aria-describedby={errores[nombre] ? `${id}-error` : undefined}
        {...props}
      />
      {errores[nombre] && <span id={`${id}-error`} className="cf-ayuda cf-ayuda--error">{errores[nombre]}</span>}
    </div>
  );

  const seleccion = (id, etiqueta, nombre, opciones) => (
    <div className="cf-campo">
      <label className="cf-label" htmlFor={id}>{etiqueta}</label>
      <select
        id={id}
        className="cf-input"
        value={datos[nombre]}
        onChange={cambiar(nombre)}
        aria-invalid={errores[nombre] ? "true" : undefined}
        aria-describedby={errores[nombre] ? `${id}-error` : undefined}
      >
        <option value="">Elige…</option>
        {(opciones ?? []).map((o) => (
          <option key={o.clave} value={o.clave}>{o.clave} · {o.descripcion}</option>
        ))}
      </select>
      {errores[nombre] && <span id={`${id}-error`} className="cf-ayuda cf-ayuda--error">{errores[nombre]}</span>}
    </div>
  );

  return (
    <section className="cf-panel" aria-labelledby="titulo-fiscales">
      <h2 id="titulo-fiscales" className="cf-panel__titulo">Prefactura</h2>
      <label className="cf-check">
        <input
          type="checkbox"
          checked={valor.activa}
          onChange={(e) => onCambio({ ...valor, activa: e.target.checked })}
        />
        <span>Quiero la prefactura con mis datos fiscales</span>
      </label>
      {!valor.activa && (
        <p className="cf-ayuda">
          Si no capturas tus datos, la prefactura sale a público en general (RFC {RFC_PUBLICO_GENERAL}).
          La descargas en XML y PDF desde tu pedido cuando se apruebe el pago.
        </p>
      )}
      {valor.activa && (
        <div style={{ marginTop: "var(--espacio-sm)" }}>
          {campo("fiscal-rfc", "RFC", "rfc", {
            autoComplete: "off",
            maxLength: 13,
            placeholder: "ABC991231AB1",
            style: { textTransform: "uppercase" },
          })}
          {campo("fiscal-nombre", "Nombre o razón social", "nombre", { autoComplete: "organization" })}
          {seleccion("fiscal-regimen", "Régimen fiscal", "regimenFiscal", catalogos?.regimenesFiscales)}
          {campo("fiscal-cp", "Código postal fiscal", "cpFiscal", {
            inputMode: "numeric",
            maxLength: 5,
            autoComplete: "postal-code",
          })}
          {seleccion("fiscal-uso", "Uso del CFDI", "usoCfdi", catalogos?.usosCfdi)}
          <p className="cf-ayuda">Escribe los datos como aparecen en tu constancia de situación fiscal.</p>
        </div>
      )}
    </section>
  );
}
