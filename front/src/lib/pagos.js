/**
 * pagos.js — consultas y acciones de cobro que comparten Checkout,
 * la página del pedido, la pasarela simulada y la cuenta.
 */
import { graphqlRequest } from "./graphql";
import { RUTAS } from "./formato";

/** Campos del pedido que necesitan las pantallas de pago. */
export const CAMPOS_PEDIDO = `
  id fecha estado total referencia piezas
  items { cantidad precioUnit subtotal producto { id nombre } }
  pago {
    metodo metodoNombre estado modo enLinea referencia pagoId detalle fechaPago
    instrucciones { etiqueta valor }
  }
`;

export const QUERY_METODOS = `
  query MetodosPago {
    metodosPago { clave nombre descripcion enLinea modo }
  }
`;

/** Subscription: el pedido cambia en vivo (pago aprobado, enviado…). */
export const SUB_SEGUIR_PEDIDO = `
  subscription SeguirPedido($id: Int!) { seguirPedido(id: $id) { ${CAMPOS_PEDIDO} } }
`;

export const QUERY_PEDIDO = `
  query Pedido($id: Int!) { pedido(id: $id) { ${CAMPOS_PEDIDO} } }
`;

const MUTATION_INICIAR = `
  mutation IniciarPago($pedidoId: Int!, $metodo: String) {
    iniciarPago(pedidoId: $pedidoId, metodo: $metodo) {
      url
      pedido { ${CAMPOS_PEDIDO} }
    }
  }
`;

const MUTATION_CONFIRMAR = `
  mutation ConfirmarPago($input: ConfirmarPagoInput!) {
    confirmarPago(input: $input) { ${CAMPOS_PEDIDO} }
  }
`;

const MUTATION_CANCELAR = `
  mutation CancelarMiPedido($id: Int!) {
    cancelarMiPedido(id: $id) { ${CAMPOS_PEDIDO} }
  }
`;

/**
 * Prepara el cobro y lleva al cliente a donde toca:
 *  - Mercado Pago / PayPal → la pasarela (sandbox real o simulada)
 *  - Transferencia / efectivo → la página del pedido con las instrucciones
 */
export async function irAPagar(pedidoId, metodo = null) {
  const data = await graphqlRequest(MUTATION_INICIAR, { pedidoId, metodo });
  const { url } = data.iniciarPago;
  window.location.href = url || RUTAS.pedidoDetalle(pedidoId);
}

export async function confirmarPago(input) {
  const data = await graphqlRequest(MUTATION_CONFIRMAR, { input });
  return data.confirmarPago;
}

export async function cancelarMiPedido(id) {
  const data = await graphqlRequest(MUTATION_CANCELAR, { id });
  return data.cancelarMiPedido;
}
