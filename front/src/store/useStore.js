import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import * as reglas from "../lib/carrito";

/**
 * Store global (Zustand): sesión, carrito, último pedido y producto abierto
 * en el modal.
 *
 * Con Astro cada vista es una página real (/, /categoria, /carrito,
 * /checkout, /pedido), así que la navegación ya no vive en el store: se hace
 * con enlaces. Lo que sí tiene que sobrevivir al cambio de página (carrito y
 * último pedido) se guarda en localStorage con el middleware `persist`.
 *
 * Todas las islas de React de una misma página comparten esta instancia,
 * por eso ProductCard puede abrir el modal aunque estén en islas distintas.
 */
export const useStore = create(
  persist(
    (set, get) => ({
      // ---- sesión ----
      // { token, usuario: { id, nombre, email, telefono, rol } } o null
      sesion: null,
      iniciarSesion: ({ token, usuario }) => set({ sesion: { token, usuario } }),
      // Al salir se olvida el último pedido (es info de esa cuenta);
      // el carrito se conserva para no perder lo que ya habías elegido.
      // El pedido pendiente TAMBIÉN se conserva (sabe de quién es): si la
      // sesión expira y vuelves a entrar, no se crea un pedido repetido.
      cerrarSesion: () => set({ sesion: null, pedido: null }),

      // ---- modal de detalle (no se persiste) ----
      selectedProductId: null,
      openProduct: (id) => set({ selectedProductId: id }),
      closeProduct: () => set({ selectedProductId: null }),

      // ---- pedido registrado ----
      // El carrito NO se vacía al registrar el pedido: se conserva hasta que
      // el pago se aprueba. Mientras tanto se recuerda:
      //   pedidoPendiente   id del pedido que espera pago (para no crear otro igual)
      //   pendienteUsuario  de qué cuenta es ese pedido
      //   pendienteItems    qué renglones se pidieron [{ clave, id, cantidad }]
      pedido: null,
      pedidoPendiente: null,
      pendienteUsuario: null,
      pendienteItems: null,
      completeCheckout: (pedido) =>
        set((s) => ({
          pedido,
          pedidoPendiente: pedido.id,
          pendienteUsuario: s.sesion?.usuario?.id ?? null,
          pendienteItems: s.carrito.map((i) => ({ clave: reglas.claveDe(i), id: i.id, cantidad: i.cantidad })),
          selectedProductId: null,
        })),

      // El pago del pedido se aprobó: ahora sí salen del carrito los
      // productos de ESE pedido. Si después agregaste otros, se quedan.
      pagoConfirmado: (pedidoId) =>
        set((s) => {
          if (s.pedidoPendiente !== pedidoId) return {};
          const libre = { pedidoPendiente: null, pendienteUsuario: null, pendienteItems: null };
          return { ...libre, carrito: reglas.restarPedido(s.carrito, s.pendienteItems) };
        }),

      // El pedido pendiente se canceló: el carrito se queda para volver a intentar
      liberarPedido: (pedidoId) =>
        set((s) =>
          s.pedidoPendiente === pedidoId
            ? { pedidoPendiente: null, pendienteUsuario: null, pendienteItems: null }
            : {}
        ),

      // ---- carrito ----
      // [{ clave, id, variante, nombre, precio, cantidad, stock, categoriaId, imagenUrl, pesoKg }]
      // Las reglas (stock compartido entre variantes, etc.) están en lib/carrito.js
      carrito: [],

      agregarAlCarrito: (producto, cantidad = 1, variante = "") =>
        set((state) => ({ carrito: reglas.agregarItem(state.carrito, producto, cantidad, variante) })),

      cambiarCantidad: (clave, cantidad) =>
        set((state) => ({ carrito: reglas.cambiarCantidad(state.carrito, clave, cantidad) })),

      quitarDelCarrito: (clave) =>
        set((state) => ({ carrito: state.carrito.filter((i) => reglas.claveDe(i) !== clave) })),

      vaciarCarrito: () =>
        set({ carrito: [], pedidoPendiente: null, pendienteUsuario: null, pendienteItems: null }),

      // ---- derivados ----
      totalPiezas: () => get().carrito.reduce((acc, i) => acc + i.cantidad, 0),
      subtotal: () => reglas.subtotalDe(get().carrito),
    }),
    {
      name: "frecuente-carrito",
      // v1: los renglones guardados antes de las variantes reciben su clave
      version: 1,
      migrate: (guardado) => ({
        ...guardado,
        carrito: (guardado?.carrito ?? []).map((i) => ({ variante: "", ...i, clave: reglas.claveDe(i) })),
      }),
      // En el servidor (build de Astro) no existe localStorage: se usa un
      // almacenamiento vacío para que no truene el render estático.
      storage: createJSONStorage(() =>
        typeof window !== "undefined"
          ? window.localStorage
          : { getItem: () => null, setItem: () => {}, removeItem: () => {} }
      ),
      partialize: (s) => ({
        carrito: s.carrito,
        pedido: s.pedido,
        pedidoPendiente: s.pedidoPendiente,
        pendienteUsuario: s.pendienteUsuario,
        pendienteItems: s.pendienteItems,
        sesion: s.sesion,
      }),
    }
  )
);
