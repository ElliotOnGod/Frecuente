import { create } from "zustand";

/**
 * Store del backoffice en vivo (no se guarda en localStorage).
 *
 * La isla AvisosEnVivo abre UNA sola Subscription (eventosAdmin) y deja
 * aquí cada aviso. Las demás islas del panel (resumen, pedidos,
 * membresías, caja) leen este store para mostrar el feed o para saber
 * cuándo recargar sus datos, sin abrir más WebSockets.
 */
export const useEnVivo = create((set) => ({
  estado: "cerrado", // conectando | en_vivo | reconectando | cerrado
  eventos: [], // más reciente primero (máximo 30)
  ultimo: null, // último evento recibido (para reaccionar a él)

  setEstado: (estado) => set({ estado }),
  agregar: (evento) =>
    set((s) => ({
      ultimo: evento,
      eventos: [evento, ...s.eventos.filter((e) => e.id !== evento.id)].slice(0, 30),
    })),
}));

/** Tipos de evento que afectan a cada sección (para saber cuándo recargar). */
export const TIPOS = {
  pedidos: ["pedido_nuevo", "pago_actualizado", "pedido_estado"],
  membresias: ["membresia_nueva", "membresia_actualizada", "canje"],
  canjes: ["canje"],
  inventario: ["stock_bajo", "pedido_nuevo", "pedido_estado"],
};
