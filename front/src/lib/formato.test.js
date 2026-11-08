import { describe, expect, it } from "vitest";
import { RUTAS, destinoSeguro, pesos } from "./formato";
import { entregaParaApi, faltantes } from "./envios";
import { urlImagen } from "./imagenes";

describe("destinoSeguro (login → ?siguiente=)", () => {
  it("acepta rutas internas", () => {
    expect(destinoSeguro("/checkout")).toBe("/checkout");
    expect(destinoSeguro("/pedido?id=12")).toBe("/pedido?id=12");
  });

  it.each([
    "//evil.com",
    "/\\evil.com",
    "https://evil.com",
    "javascript:alert(1)",
    "/\tevil",
    "",
    null,
  ])("rechaza %s y manda a /cuenta", (valor) => {
    expect(destinoSeguro(valor)).toBe("/cuenta");
  });
});

describe("formato", () => {
  it("pesos mexicanos", () => {
    expect(pesos(185).replace(/\s/g, " ")).toMatch(/\$185\.00/);
  });

  it("rutas de la tienda con filtro por método", () => {
    expect(RUTAS.tiendaMetodo("prensa")).toBe("/tienda?metodo=prensa");
  });
});

describe("envíos", () => {
  const completa = {
    nombre: "Ana", telefono: "3312345678", calle: "Justo Sierra", numero: "2665",
    colonia: "Arcos Vallarta", ciudad: "Guadalajara", estado: "JA", cp: "44650", referencias: "",
  };

  it("una dirección completa no tiene faltantes", () => {
    expect(faltantes(completa)).toEqual([]);
  });

  it("avisa qué falta (CP de 5 dígitos y teléfono de 10)", () => {
    expect(faltantes({ ...completa, cp: "446", telefono: "33" })).toEqual(["código postal", "teléfono de 10 dígitos"]);
  });

  it("recoger no manda dirección; domicilio manda el token de la cotización", () => {
    expect(entregaParaApi("recoger", completa, null)).toEqual({ tipo: "recoger" });
    expect(entregaParaApi("domicilio", completa, { token: "abc.def" })).toMatchObject({
      tipo: "domicilio", cp: "44650", opcionToken: "abc.def",
    });
  });
});

describe("imágenes", () => {
  it("las fotos subidas se piden al backend y las de Unsplash con el ancho justo", () => {
    expect(urlImagen("/imagenes/" + "a".repeat(32), 480)).toMatch(/^https?:\/\/.+\/imagenes\/a{32}$/);
    expect(urlImagen("https://images.unsplash.com/photo-1?auto=format", 480)).toContain("w=480");
    expect(urlImagen("", 480)).toBe("");
  });
});
