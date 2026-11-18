/**
 * cfdi.test.js — pruebas (Vitest) de la validación de datos fiscales del
 * front: estructura del RFC (RQNF111) y formulario completo (RQF90).
 */
import { describe, expect, it, vi } from "vitest";

vi.mock("../store/useStore", () => ({ useStore: { getState: () => ({ sesion: null }) } }));

const { rfcValido, validarDatosFiscales, normalizarDatosFiscales } = await import("./cfdi.js");

describe("rfcValido (RQNF111)", () => {
  it("acepta persona moral (3 letras), física (4 letras) y el genérico", () => {
    expect(rfcValido("ABC991231AB1")).toBe(true);
    expect(rfcValido("GODE561231GR8")).toBe(true);
    expect(rfcValido("XAXX010101000")).toBe(true);
    expect(rfcValido(" gode561231gr8 ")).toBe(true);
  });

  it("rechaza letras de más o de menos, fechas imposibles y homoclaves mal formadas", () => {
    for (const malo of ["AB991231AB1", "ABCDE991231AB1", "GODE561331GR8", "GODE560230GR8", "ABC991231AB", "ABC991231-B1", ""]) {
      expect(rfcValido(malo)).toBe(false);
    }
  });
});

describe("validarDatosFiscales (RQF90)", () => {
  const completos = { rfc: "GODE561231GR8", nombre: "Empresa Demo", regimenFiscal: "612", cpFiscal: "44160", usoCfdi: "G03" };

  it("sin errores cuando los cinco datos son válidos", () => {
    expect(validarDatosFiscales(completos)).toEqual({});
  });

  it("marca cada campo que falta o no es válido", () => {
    const errores = validarDatosFiscales({ rfc: "X", nombre: " ", regimenFiscal: "", cpFiscal: "441", usoCfdi: "" });
    expect(Object.keys(errores).sort()).toEqual(["cpFiscal", "nombre", "regimenFiscal", "rfc", "usoCfdi"]);
  });

  it("normaliza RFC y nombre en mayúsculas", () => {
    expect(normalizarDatosFiscales({ ...completos, rfc: " gode561231gr8", nombre: " empresa   demo " })).toMatchObject({
      rfc: "GODE561231GR8",
      nombre: "EMPRESA DEMO",
    });
  });
});
