import { useEffect, useRef, useState } from "react";
import { useStore } from "../../../store/useStore";
import { useEnVivo } from "../../../store/enVivo";
import { suscribir } from "../../../lib/subscripciones";
import { hora } from "../../../lib/formato";
import { IndicadorEnVivo } from "../Insignia";

const SUB_EVENTOS = `
  subscription EventosAdmin {
    eventosAdmin { id tipo mensaje fecha pedidoId membresiaId monto }
  }
`;

/** Icono y tono de cada tipo de aviso (el texto siempre acompaña). */
export const ESTILO_EVENTO = {
  pedido_nuevo: { icono: "🛒", tono: "info", titulo: "Pedido nuevo" },
  pago_actualizado: { icono: "💳", tono: "ok", titulo: "Pago" },
  pedido_estado: { icono: "📦", tono: "neutro", titulo: "Pedido" },
  stock_bajo: { icono: "⚠️", tono: "aviso", titulo: "Stock bajo" },
  membresia_nueva: { icono: "⭐", tono: "info", titulo: "Membresía nueva" },
  membresia_actualizada: { icono: "⭐", tono: "ok", titulo: "Membresía" },
  canje: { icono: "☕", tono: "ok", titulo: "Canje" },
  conectado: { icono: "🟢", tono: "ok", titulo: "En vivo" },
};

const DURACION_AVISO = 6000;

/**
 * AvisosEnVivo — vive en el menú del panel (AdminLayout). Abre UNA
 * Subscription eventosAdmin por pestaña, guarda cada aviso en el store
 * enVivo (para que las otras islas se actualicen) y muestra notificaciones
 * flotantes que se quitan solas.
 */
export default function AvisosEnVivo() {
  const sesion = useStore((s) => s.sesion);
  const estado = useEnVivo((s) => s.estado);
  const setEstado = useEnVivo((s) => s.setEstado);
  const agregar = useEnVivo((s) => s.agregar);
  const [avisos, setAvisos] = useState([]);
  const timers = useRef([]);

  const esAdmin = sesion?.usuario?.rol === "admin";

  useEffect(() => {
    if (!esAdmin) return undefined;
    const cancelar = suscribir(SUB_EVENTOS, {}, {
      onEstado: setEstado,
      onError: () => setEstado("cerrado"),
      onDato: (d) => {
        const e = d?.eventosAdmin;
        if (!e) return;
        agregar(e);
        if (e.tipo === "conectado") return;
        setAvisos((a) => [e, ...a].slice(0, 3));
        timers.current.push(
          setTimeout(() => setAvisos((a) => a.filter((x) => x.id !== e.id)), DURACION_AVISO)
        );
      },
    });
    return () => {
      cancelar();
      timers.current.forEach(clearTimeout);
    };
  }, [esAdmin, setEstado, agregar]);

  if (!esAdmin) return null;

  return (
    <>
      <div className="cf-envivo-menu">
        <IndicadorEnVivo estado={estado} />
      </div>

      <div className="cf-avisos" aria-live="polite" aria-label="Avisos en vivo">
        {avisos.map((a) => {
          const est = ESTILO_EVENTO[a.tipo] || ESTILO_EVENTO.pedido_estado;
          return (
            <div key={a.id} className={`cf-aviso cf-aviso--${est.tono}`} role="status">
              <span aria-hidden="true">{est.icono}</span>
              <div>
                <strong>{est.titulo}</strong>
                <span className="cf-caption cf-bloque">{hora(a.fecha)}</span>
                <p>{a.mensaje}</p>
              </div>
              <button
                className="cf-btn cf-btn--icono"
                aria-label="Cerrar aviso"
                onClick={() => setAvisos((x) => x.filter((y) => y.id !== a.id))}
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </>
  );
}
