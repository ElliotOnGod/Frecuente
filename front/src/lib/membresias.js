/**
 * membresias.js — consultas y acciones de membresía que comparten la
 * página de planes, "Mi membresía", la pasarela y el resultado del pago.
 */
import { graphqlRequest } from "./graphql";
import { RUTAS } from "./formato";

export const CAMPOS_PLAN = "id nombre descripcion precio incluye opciones activo orden";

export const CAMPOS_MEMBRESIA = `
  id estado precio referencia creada inicio fin diasRestantes canjesTotal codigoHoy
  plan { ${CAMPOS_PLAN} }
  canjeHoy { dia fecha opcion nota }
  canjes(limite: 31) { dia fecha opcion nota }
  pago {
    metodo metodoNombre estado modo enLinea referencia pagoId detalle fechaPago
    instrucciones { etiqueta valor }
  }
`;

export const QUERY_PLANES = `query Planes { planes { ${CAMPOS_PLAN} } }`;

export const QUERY_MI_MEMBRESIA = `
  query MiMembresia {
    miMembresia { ${CAMPOS_MEMBRESIA} }
    misMembresias { id estado precio referencia creada inicio fin plan { nombre } pago { metodoNombre estado } }
  }
`;

export const QUERY_MEMBRESIA = `
  query Membresia($id: Int!) { membresia(id: $id) { ${CAMPOS_MEMBRESIA} } }
`;

/** Subscription: la membresía cambia en vivo (canje en caja, pago aprobado…). */
export const SUB_SEGUIR_MEMBRESIA = `
  subscription SeguirMembresia($id: Int!) { seguirMembresia(id: $id) { ${CAMPOS_MEMBRESIA} } }
`;

const MUTATION_CONTRATAR = `
  mutation Contratar($planId: Int!, $metodoPago: String!) {
    contratarMembresia(planId: $planId, metodoPago: $metodoPago) { id }
  }
`;

const MUTATION_INICIAR = `
  mutation IniciarPagoMembresia($membresiaId: Int!, $metodo: String) {
    iniciarPagoMembresia(membresiaId: $membresiaId, metodo: $metodo) { url membresia { id } }
  }
`;

const MUTATION_CONFIRMAR = `
  mutation ConfirmarPagoMembresia($input: ConfirmarPagoMembresiaInput!) {
    confirmarPagoMembresia(input: $input) { ${CAMPOS_MEMBRESIA} }
  }
`;

const MUTATION_CANCELAR = `
  mutation CancelarMiMembresia($id: Int!) { cancelarMiMembresia(id: $id) { ${CAMPOS_MEMBRESIA} } }
`;

/**
 * Prepara el cobro de una membresía y lleva al cliente a la pasarela
 * (Mercado Pago / PayPal) o a "Mi membresía" con las instrucciones
 * (transferencia / efectivo en el local).
 */
export async function irAPagarMembresia(membresiaId, metodo = null) {
  const data = await graphqlRequest(MUTATION_INICIAR, { membresiaId, metodo });
  window.location.href = data.iniciarPagoMembresia.url || RUTAS.miMembresia;
}

/** Contrata el plan y en seguida inicia el pago. */
export async function contratarYPagar(planId, metodoPago) {
  const data = await graphqlRequest(MUTATION_CONTRATAR, { planId, metodoPago });
  const id = data.contratarMembresia.id;
  try {
    await irAPagarMembresia(id, metodoPago);
  } catch {
    // Si la pasarela falló, en "Mi membresía" se puede reintentar
    window.location.href = RUTAS.miMembresia;
  }
}

export async function confirmarPagoMembresia(input) {
  const data = await graphqlRequest(MUTATION_CONFIRMAR, { input });
  return data.confirmarPagoMembresia;
}

export async function cancelarMiMembresia(id) {
  const data = await graphqlRequest(MUTATION_CANCELAR, { id });
  return data.cancelarMiMembresia;
}
