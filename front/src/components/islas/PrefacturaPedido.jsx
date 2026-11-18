/**
 * PrefacturaPedido — prefactura CFDI de un pedido pagado.
 *
 * Cliente (detalle del pedido): descarga el XML (RQF92) y el PDF (RQF93)
 * cuando la prefactura está validada; una con error no se muestra (RQNF118).
 * Administrador (panel de pedidos, `admin`): ve los datos de la prefactura
 * de cualquier pedido (RQF95), su estado y, si falló, los errores de la
 * validación; descarga el XML (RQF94) y el PDF para imprimirla (RQF96).
 */
import { useState } from "react";
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { QUERY_PREFACTURA, descargarPrefactura } from "../../lib/cfdi";
import { fechaCorta, pesos } from "../../lib/formato";

const ESTADOS = {
  generada: "Generada",
  validada: "Validada",
  timbrada: "Timbrada",
  error: "Con error",
};

export default function PrefacturaPedido({ pedidoId, admin = false }) {
  const { data, loading, error } = useGraphQLQuery(QUERY_PREFACTURA, { pedidoId });
  const [descargando, setDescargando] = useState(null);
  const [errorDescarga, setErrorDescarga] = useState(null);
  const prefactura = data?.prefactura;

  const descargar = async (formato) => {
    setDescargando(formato);
    setErrorDescarga(null);
    try {
      await descargarPrefactura(pedidoId, formato);
    } catch (err) {
      setErrorDescarga(err.message);
    }
    setDescargando(null);
  };

  if (loading) return <p className="cf-caption">Buscando la prefactura…</p>;
  if (error) return <p className="cf-alerta cf-alerta--error" role="alert">{error}</p>;
  if (!prefactura) {
    return (
      <section className="cf-panel" aria-label="Prefactura">
        <h2 className="cf-panel__titulo">Prefactura</h2>
        <p className="cf-caption">
          {admin
            ? "Este pedido todavía no tiene prefactura: se genera cuando se aprueba el pago."
            : "Tu prefactura todavía no está disponible. Si el problema sigue, escríbenos."}
        </p>
      </section>
    );
  }

  return (
    <section className="cf-panel" aria-labelledby={`prefactura-${pedidoId}`}>
      <h2 id={`prefactura-${pedidoId}`} className="cf-panel__titulo">
        Prefactura {prefactura.serie}-{prefactura.folio}
      </h2>
      <p className="cf-caption">
        Comprobante con la estructura del CFDI, sin timbre fiscal del SAT.
        {admin && <> Estado: <strong>{ESTADOS[prefactura.estado] ?? prefactura.estado}</strong>.</>}
      </p>

      <dl className="cf-datos">
        <div><dt className="cf-caption">RFC del receptor</dt><dd>{prefactura.rfcReceptor}</dd></div>
        <div><dt className="cf-caption">Nombre o razón social</dt><dd>{prefactura.nombreReceptor}</dd></div>
        <div>
          <dt className="cf-caption">Régimen fiscal</dt>
          <dd>{prefactura.regimenFiscalReceptor} {prefactura.regimenDescripcion}</dd>
        </div>
        <div><dt className="cf-caption">Código postal fiscal</dt><dd>{prefactura.cpFiscalReceptor}</dd></div>
        <div><dt className="cf-caption">Uso del CFDI</dt><dd>{prefactura.usoCfdi} {prefactura.usoDescripcion}</dd></div>
        <div><dt className="cf-caption">Fecha</dt><dd>{fechaCorta(prefactura.creada)}</dd></div>
        <div><dt className="cf-caption">Subtotal</dt><dd>{pesos(prefactura.subtotal)}</dd></div>
        <div><dt className="cf-caption">IVA trasladado</dt><dd>{pesos(prefactura.iva)}</dd></div>
        <div><dt className="cf-caption">Total</dt><dd>{pesos(prefactura.total)}</dd></div>
      </dl>

      {admin && prefactura.errores.length > 0 && (
        <div className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> La prefactura no pasó la validación y el cliente no la ve:
          <ul>
            {prefactura.errores.map((e) => <li key={e}>{e}</li>)}
          </ul>
        </div>
      )}

      {errorDescarga && <p className="cf-alerta cf-alerta--error" role="alert">{errorDescarga}</p>}

      {prefactura.disponible && (
        <div className="cf-acciones cf-acciones--envolver">
          <button className="cf-btn cf-btn--secundario" onClick={() => descargar("xml")} disabled={!!descargando}>
            {descargando === "xml" ? "Descargando…" : "Descargar XML"}
          </button>
          <button className="cf-btn cf-btn--secundario" onClick={() => descargar("pdf")} disabled={!!descargando}>
            {descargando === "pdf" ? "Descargando…" : admin ? "Descargar PDF para imprimir" : "Descargar PDF"}
          </button>
        </div>
      )}
    </section>
  );
}
