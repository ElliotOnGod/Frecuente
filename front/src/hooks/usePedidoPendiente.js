import { useEffect } from "react";
import { useGraphQLQuery } from "./useGraphQLQuery";
import { useStore } from "../store/useStore";

const QUERY = `
  query PedidoPendiente($id: Int!) {
    pedido(id: $id) { id estado total referencia piezas pago { estado metodo metodoNombre enLinea } }
  }
`;

/** ¿El pedido ya quedó pagado? (o ya avanzó a enviado/entregado) */
export const estaPagado = (p) =>
  p?.pago?.estado === "aprobado" || ["pagado", "enviado", "entregado"].includes(p?.estado);

/**
 * usePedidoPendiente — el pedido que se registró con el carrito actual y
 * todavía no se paga.
 *
 * Le pregunta al servidor cómo va y sincroniza el carrito:
 *  - si ya se pagó (por ejemplo, la tienda confirmó la transferencia) → vacía el carrito
 *  - si se canceló o ya no existe → lo olvida y el carrito queda libre
 *
 * Regresa { pendiente, cargando }: `pendiente` es el pedido solo si sigue
 * esperando pago.
 */
export function usePedidoPendiente() {
  const sesion = useStore((s) => s.sesion);
  const guardado = useStore((s) => s.pedidoPendiente);
  const duenio = useStore((s) => s.pendienteUsuario);
  const pagoConfirmado = useStore((s) => s.pagoConfirmado);
  const liberarPedido = useStore((s) => s.liberarPedido);

  // Solo cuenta si es de la cuenta con la que estás ahora. Si entró otra
  // persona en esta compu, se ignora (pero no se borra: es de la otra cuenta).
  const id = sesion && (duenio == null || duenio === sesion.usuario?.id) ? guardado : null;

  const { data, loading, error } = useGraphQLQuery(QUERY, { id }, { omitir: !id });
  const pedido = data?.pedido;

  useEffect(() => {
    if (!id || loading) return;
    if (pedido && pedido.id !== id) return; // respuesta de otro pedido: esperar la buena
    if (error) {
      // Solo se olvida si el servidor dice que ese pedido no existe. Si el
      // backend está apagado o falla la red, se conserva para no duplicarlo.
      if (/No encontramos el pedido/i.test(error)) liberarPedido(id);
    } else if (data && !pedido) {
      liberarPedido(id); // ya no existe
    } else if (estaPagado(pedido)) {
      pagoConfirmado(id);
    } else if (pedido?.estado === "cancelado") {
      liberarPedido(id);
    }
  }, [id, loading, error, data, pedido, pagoConfirmado, liberarPedido]);

  // Solo cuenta si es el pedido que sigue guardado (no una respuesta vieja)
  const sigue =
    id && pedido && pedido.id === id && pedido.estado === "registrado" && !estaPagado(pedido);
  return { pendiente: sigue ? pedido : null, cargando: Boolean(id && loading) };
}
