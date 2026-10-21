import { ESTADO_MEMBRESIA, ESTADO_PAGO, ESTADO_PEDIDO } from "../../lib/formato";

/**
 * Insignia de estado. Lleva siempre la palabra; el color solo refuerza
 * (manual 11.3). tono: ok | aviso | error | info | neutro
 */
export function Insignia({ tono = "neutro", children }) {
  return <span className={`cf-estado cf-estado--${tono}`}>{children}</span>;
}

export function EstadoPedido({ estado }) {
  const e = ESTADO_PEDIDO[estado] || { texto: estado, tono: "neutro" };
  return <Insignia tono={e.tono}>{e.texto}</Insignia>;
}

export function EstadoPago({ estado }) {
  if (!estado) return <span className="cf-caption">—</span>;
  const e = ESTADO_PAGO[estado] || { texto: estado, tono: "neutro" };
  return <Insignia tono={e.tono}>{e.texto}</Insignia>;
}

export function EstadoMembresia({ estado }) {
  const e = ESTADO_MEMBRESIA[estado] || { texto: estado, tono: "neutro" };
  return <Insignia tono={e.tono}>{e.texto}</Insignia>;
}

/** Indicador de conexión en vivo (punto + palabra, nunca solo color). */
export function IndicadorEnVivo({ estado }) {
  const textos = {
    en_vivo: ["ok", "En vivo"],
    conectando: ["aviso", "Conectando…"],
    reconectando: ["aviso", "Reconectando…"],
    cerrado: ["neutro", "Sin conexión en vivo"],
  };
  const [tono, texto] = textos[estado] || textos.cerrado;
  return (
    <span className={`cf-estado cf-estado--${tono} cf-envivo`} role="status" aria-live="polite">
      {texto}
    </span>
  );
}
