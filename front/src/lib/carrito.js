/**
 * carrito.js — reglas del carrito como funciones puras (sin React ni Zustand),
 * para poder probarlas con Vitest y reutilizarlas en el store.
 *
 * Un renglón del carrito es un producto EN UNA VARIANTE: "Blend de Casa ·
 * Grano entero" y "Blend de Casa · Molido para espresso" son dos renglones
 * distintos del mismo producto. Su identificador es la `clave`.
 */

export const claveDe = (item) => item.clave ?? `${item.id}|${item.variante ?? ""}`;

/** Piezas de un producto en el carrito sumando todas sus variantes. */
export const piezasDeProducto = (carrito, productoId) =>
  carrito.filter((i) => i.id === productoId).reduce((acc, i) => acc + i.cantidad, 0);

/**
 * Agrega `cantidad` piezas. Nunca deja pasar más piezas del producto que
 * su stock (contando todas las variantes juntas, porque comparten stock).
 */
export function agregarItem(carrito, producto, cantidad = 1, variante = "") {
  const clave = `${producto.id}|${variante}`;
  const libres = Math.max(0, producto.stock - piezasDeProducto(carrito, producto.id));
  const suma = Math.min(cantidad, libres);
  if (suma <= 0) return carrito;
  const existente = carrito.find((i) => claveDe(i) === clave);
  if (existente) {
    return carrito.map((i) => (claveDe(i) === clave ? { ...i, cantidad: i.cantidad + suma } : i));
  }
  return [
    ...carrito,
    {
      clave,
      id: producto.id,
      variante,
      nombre: producto.nombre,
      precio: producto.precio,
      stock: producto.stock,
      categoriaId: producto.categoriaId,
      imagenUrl: producto.imagenUrl || "",
      pesoKg: producto.pesoKg ?? 0.5,
      cantidad: suma,
    },
  ];
}

/** Cambia la cantidad de un renglón respetando el stock del producto. */
export function cambiarCantidad(carrito, clave, cantidad) {
  const item = carrito.find((i) => claveDe(i) === clave);
  if (!item) return carrito;
  const otras = piezasDeProducto(carrito, item.id) - item.cantidad;
  const maximo = Math.max(1, item.stock - otras);
  return carrito.map((i) =>
    claveDe(i) === clave ? { ...i, cantidad: Math.max(1, Math.min(Math.floor(cantidad) || 1, maximo)) } : i
  );
}

/** Saca del carrito lo que ya se pagó en un pedido; lo que agregaste después se queda. */
export function restarPedido(carrito, pendientes) {
  if (!pendientes) return [];
  const pedidas = new Map(pendientes.map((p) => [p.clave ?? `${p.id}|`, p.cantidad]));
  return carrito
    .map((i) => ({ ...i, cantidad: i.cantidad - (pedidas.get(claveDe(i)) ?? 0) }))
    .filter((i) => i.cantidad > 0);
}

/** Renglones para la mutation registrarPedido / cotizarEnvio. */
export const itemsParaApi = (carrito) =>
  carrito.map((i) => ({ productoId: i.id, cantidad: i.cantidad, variante: i.variante ?? "" }));

export const subtotalDe = (carrito) =>
  Math.round(carrito.reduce((acc, i) => acc + i.precio * i.cantidad, 0) * 100) / 100;
