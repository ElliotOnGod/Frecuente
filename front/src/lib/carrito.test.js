import { describe, expect, it } from "vitest";
import { agregarItem, cambiarCantidad, claveDe, itemsParaApi, restarPedido, subtotalDe } from "./carrito";

const blend = { id: 1, nombre: "Blend de Casa", precio: 185, stock: 5, categoriaId: 1, imagenUrl: "", pesoKg: 0.3 };
const leche = { id: 4, nombre: "Leche entera", precio: 34, stock: 60, categoriaId: 2 };

describe("carrito con variantes", () => {
  it("la misma variante suma; otra variante es otro renglón", () => {
    let c = agregarItem([], blend, 1, "Grano entero");
    c = agregarItem(c, blend, 2, "Grano entero");
    c = agregarItem(c, blend, 1, "Molido para espresso");
    expect(c).toHaveLength(2);
    expect(c.map((i) => [claveDe(i), i.cantidad])).toEqual([
      ["1|Grano entero", 3],
      ["1|Molido para espresso", 1],
    ]);
  });

  it("las variantes comparten el stock del producto", () => {
    let c = agregarItem([], blend, 4, "Grano entero");
    c = agregarItem(c, blend, 4, "Molido para espresso"); // solo queda 1 pieza
    expect(c.find((i) => i.variante === "Molido para espresso").cantidad).toBe(1);
    expect(agregarItem(c, blend, 1, "Molido para V60")).toBe(c); // ya no cabe nada
  });

  it("cambiarCantidad respeta el stock y nunca baja de 1", () => {
    let c = agregarItem([], blend, 2, "Grano entero");
    c = agregarItem(c, blend, 1, "Molido para espresso");
    c = cambiarCantidad(c, "1|Grano entero", 99);
    expect(c.find((i) => i.variante === "Grano entero").cantidad).toBe(4);
    c = cambiarCantidad(c, "1|Grano entero", 0);
    expect(c.find((i) => i.variante === "Grano entero").cantidad).toBe(1);
  });

  it("al pagar solo sale lo que se pidió; lo agregado después se queda", () => {
    let c = agregarItem([], blend, 2, "Grano entero");
    c = agregarItem(c, leche, 3);
    const pedido = c.map((i) => ({ clave: claveDe(i), id: i.id, cantidad: i.cantidad }));
    c = agregarItem(c, leche, 2); // agregó más leche después del pedido
    expect(restarPedido(c, pedido)).toEqual([expect.objectContaining({ id: 4, cantidad: 2 })]);
  });

  it("los carritos viejos (sin clave ni variante) siguen funcionando", () => {
    const viejo = [{ id: 4, nombre: "Leche", precio: 34, stock: 60, cantidad: 2 }];
    expect(claveDe(viejo[0])).toBe("4|");
    expect(restarPedido(viejo, [{ id: 4, cantidad: 2 }])).toEqual([]);
  });

  it("arma los renglones para la API y el subtotal con centavos exactos", () => {
    let c = agregarItem([], { ...leche, precio: 0.1 }, 3);
    c = agregarItem(c, blend, 1, "Grano entero");
    expect(itemsParaApi(c)).toEqual([
      { productoId: 4, cantidad: 3, variante: "" },
      { productoId: 1, cantidad: 1, variante: "Grano entero" },
    ]);
    expect(subtotalDe(c)).toBe(185.3);
  });
});
