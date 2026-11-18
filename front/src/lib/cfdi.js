/**
 * cfdi.js — prefactura CFDI en el front: validación de los datos fiscales
 * (RQF90, RQNF111), consultas de GraphQL y descarga del XML y del PDF
 * (RQF92 a RQF96).
 *
 * La descarga usa fetch con la credencial en el encabezado
 * Authorization: Bearer <token>, nunca en la dirección, y guarda el archivo
 * con un enlace temporal. El backend responde 403 si el pedido no es de
 * quien descarga y no es administrador (RQNF119).
 */
import { useStore } from "../store/useStore";

const API_URL = import.meta.env.PUBLIC_API_URL || "http://localhost:8000/graphql";
// http://localhost:8000/graphql → http://localhost:8000
const ORIGEN_BACKEND = new URL(API_URL).origin;

// RQNF111: 3 letras (persona moral) o 4 (persona física), fecha AAMMDD y 3 de homoclave
const RFC_RE = /^([A-ZÑ]{3,4})(\d{2})(\d{2})(\d{2})([A-Z0-9]{3})$/;
const CP_RE = /^\d{5}$/;

export const RFC_PUBLICO_GENERAL = "XAXX010101000";

/** ¿El RFC cumple la estructura del RQNF111 (con una fecha que existe)? */
export function rfcValido(rfc) {
  const m = RFC_RE.exec((rfc || "").trim().toUpperCase());
  if (!m) return false;
  const [, , aa, mm, dd] = m;
  const fecha = new Date(Date.UTC(2000 + Number(aa), Number(mm) - 1, Number(dd)));
  return fecha.getUTCMonth() === Number(mm) - 1 && fecha.getUTCDate() === Number(dd);
}

export const DATOS_FISCALES_VACIOS = { rfc: "", nombre: "", regimenFiscal: "", cpFiscal: "", usoCfdi: "" };

/** Revisa los datos fiscales del formulario; regresa { campo: mensaje }. */
export function validarDatosFiscales(datos) {
  const errores = {};
  if (!rfcValido(datos.rfc))
    errores.rfc = "El RFC debe tener 3 letras (persona moral) o 4 (persona física), 6 dígitos de fecha AAMMDD y 3 caracteres de homoclave.";
  if (!datos.nombre.trim()) errores.nombre = "Escribe el nombre o razón social como aparece en tu constancia fiscal.";
  if (!datos.regimenFiscal) errores.regimenFiscal = "Elige tu régimen fiscal.";
  if (!CP_RE.test(datos.cpFiscal.trim())) errores.cpFiscal = "El código postal fiscal debe tener 5 dígitos.";
  if (!datos.usoCfdi) errores.usoCfdi = "Elige el uso del CFDI.";
  return errores;
}

/** Datos listos para registrarPedido (RFC y nombre en mayúsculas). */
export function normalizarDatosFiscales(datos) {
  return {
    rfc: datos.rfc.trim().toUpperCase(),
    nombre: datos.nombre.trim().replace(/\s+/g, " ").toUpperCase(),
    regimenFiscal: datos.regimenFiscal,
    cpFiscal: datos.cpFiscal.trim(),
    usoCfdi: datos.usoCfdi,
  };
}

export const QUERY_CATALOGOS_CFDI = `
  query CatalogosCfdi {
    catalogosCfdi {
      regimenesFiscales { clave descripcion }
      usosCfdi { clave descripcion }
      clavesProdServ { clave descripcion }
      clavesUnidad { clave descripcion }
      tasasIva
    }
  }
`;

export const QUERY_PREFACTURA = `
  query Prefactura($pedidoId: Int!) {
    prefactura(pedidoId: $pedidoId) {
      id serie folio estado disponible creada
      rfcReceptor nombreReceptor regimenFiscalReceptor regimenDescripcion
      cpFiscalReceptor usoCfdi usoDescripcion
      subtotal iva total errores
    }
  }
`;

/** Descarga la prefactura del pedido: formato "xml" o "pdf". */
export async function descargarPrefactura(pedidoId, formato) {
  const token = useStore.getState().sesion?.token;
  const res = await fetch(`${ORIGEN_BACKEND}/prefacturas/${pedidoId}.${formato}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    let mensaje = `No se pudo descargar la prefactura (${res.status}).`;
    try {
      mensaje = (await res.json()).detail || mensaje;
    } catch {
      // la respuesta no era JSON: se queda el mensaje genérico
    }
    throw new Error(mensaje);
  }
  const archivo = await res.blob();
  const url = URL.createObjectURL(archivo);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = `prefactura-FREC-${pedidoId}.${formato}`;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(url);
}
