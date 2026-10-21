/** Icono por categoría, usado como placeholder mientras no hay fotos reales. */
export const ICONO_CATEGORIA = {
  1: "☕",
  2: "🥛",
  3: "🍵",
  4: "🫖",
};

export const iconoDe = (categoriaId) => ICONO_CATEGORIA[categoriaId] || "☕";

/** Precio en pesos mexicanos. */
export const pesos = (n) =>
  new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(n);

/** Rutas del sitio en un solo lugar, para no escribir URLs sueltas. */
export const RUTAS = {
  inicio: "/",
  categoria: (id) => `/categoria?id=${id}`,
  carrito: "/carrito",
  checkout: "/checkout",
  pedido: "/pedido",
  cuenta: "/cuenta",
  pedidoDetalle: (id) => `/pedido?id=${id}`,
  pagoSimulado: (id) => `/pago/simulado?pedido=${id}`,
  membresias: "/membresias",
  miMembresia: "/mi-membresia",
  admin: "/admin",
  adminPedidos: "/admin/pedidos",
  adminProductos: "/admin/productos",
  adminMembresias: "/admin/membresias",
  adminCaja: "/admin/caja",
  adminClientes: "/admin/clientes",
  login: (siguiente) =>
    siguiente ? `/login?siguiente=${encodeURIComponent(siguiente)}` : "/login",
  registro: (siguiente) =>
    siguiente ? `/registro?siguiente=${encodeURIComponent(siguiente)}` : "/registro",
};

/**
 * A dónde mandar al usuario después de iniciar sesión. Solo se aceptan
 * rutas internas ("/algo"), nunca "//otro-sitio.com" ni URLs completas,
 * para que nadie pueda usar el login para redirigir a una página falsa.
 */
export function destinoSeguro(valor, porDefecto = "/cuenta") {
  if (typeof valor === "string" && valor.startsWith("/") && !valor.startsWith("//")) {
    return valor;
  }
  return porDefecto;
}

/** Fecha "2026-10-02 16:59:16" → "2 oct 2026, 16:59". */
export const fechaCorta = (texto) => {
  const d = new Date(String(texto).replace(" ", "T"));
  return Number.isNaN(d.getTime())
    ? texto
    : new Intl.DateTimeFormat("es-MX", { dateStyle: "medium", timeStyle: "short" }).format(d);
};

/** Fecha "2026-10-08" → "8 oct". */
export const diaCorto = (texto) => {
  const d = new Date(`${texto}T12:00:00`);
  return Number.isNaN(d.getTime())
    ? texto
    : new Intl.DateTimeFormat("es-MX", { day: "numeric", month: "short" }).format(d);
};

/** Pesos sin centavos, para ejes y tarjetas del panel. */
export const pesosCortos = (n) =>
  new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    maximumFractionDigits: 0,
  }).format(n);

/**
 * Textos y tono de cada estado. El tono elige el color de la insignia,
 * pero la insignia siempre lleva la palabra (manual 11.3: nunca solo color).
 */
export const ESTADO_PEDIDO = {
  registrado: { texto: "Por pagar", tono: "aviso" },
  pagado: { texto: "Pagado", tono: "ok" },
  enviado: { texto: "Enviado", tono: "info" },
  entregado: { texto: "Entregado", tono: "neutro" },
  cancelado: { texto: "Cancelado", tono: "error" },
};

export const ESTADO_PAGO = {
  pendiente: { texto: "Pendiente", tono: "aviso" },
  aprobado: { texto: "Aprobado", tono: "ok" },
  rechazado: { texto: "Rechazado", tono: "error" },
  por_reembolsar: { texto: "Por reembolsar", tono: "error" },
  reembolsado: { texto: "Reembolsado", tono: "neutro" },
};

export const NOMBRE_METODO = {
  mercadopago: "Mercado Pago",
  paypal: "PayPal",
  transferencia: "Transferencia SPEI",
  efectivo: "Efectivo al recoger",
};

export const ESTADO_MEMBRESIA = {
  activa: { texto: "Activa", tono: "ok" },
  programada: { texto: "Programada", tono: "info" },
  pendiente: { texto: "Por pagar", tono: "aviso" },
  vencida: { texto: "Vencida", tono: "neutro" },
  cancelada: { texto: "Cancelada", tono: "error" },
};

/** "2026-10-15 08:31:00" → "08:31" */
export const hora = (texto) => {
  const d = new Date(String(texto).replace(" ", "T"));
  return Number.isNaN(d.getTime())
    ? texto
    : new Intl.DateTimeFormat("es-MX", { timeStyle: "short" }).format(d);
};

/** "2026-10-15 08:31:00" → "15 oct 2026" */
export const fechaLarga = (texto) => {
  const d = new Date(String(texto).replace(" ", "T"));
  return Number.isNaN(d.getTime())
    ? texto
    : new Intl.DateTimeFormat("es-MX", { dateStyle: "medium" }).format(d);
};
