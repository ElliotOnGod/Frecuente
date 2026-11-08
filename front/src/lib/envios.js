/**
 * envios.js — consultas de envío a domicilio (Envia.com a través del backend).
 *
 * El navegador nunca habla directo con Envia: el backend cotiza, firma cada
 * opción y luego verifica esa firma al registrar el pedido. Así el precio
 * del envío no se puede alterar desde aquí.
 */
import { graphqlRequest } from "./graphql";

export const ESTADOS_MX = [
  ["AG", "Aguascalientes"], ["BC", "Baja California"], ["BS", "Baja California Sur"], ["CM", "Campeche"],
  ["CS", "Chiapas"], ["CH", "Chihuahua"], ["CX", "Ciudad de México"], ["CO", "Coahuila"], ["CL", "Colima"],
  ["DG", "Durango"], ["EM", "Estado de México"], ["GT", "Guanajuato"], ["GR", "Guerrero"], ["HG", "Hidalgo"],
  ["JA", "Jalisco"], ["MI", "Michoacán"], ["MO", "Morelos"], ["NA", "Nayarit"], ["NL", "Nuevo León"],
  ["OA", "Oaxaca"], ["PU", "Puebla"], ["QT", "Querétaro"], ["QR", "Quintana Roo"], ["SL", "San Luis Potosí"],
  ["SI", "Sinaloa"], ["SO", "Sonora"], ["TB", "Tabasco"], ["TM", "Tamaulipas"], ["TL", "Tlaxcala"],
  ["VE", "Veracruz"], ["YU", "Yucatán"], ["ZA", "Zacatecas"],
];

export const DIRECCION_VACIA = {
  nombre: "", telefono: "", calle: "", numero: "", colonia: "", ciudad: "", estado: "", cp: "", referencias: "",
};

const QUERY_CP = `
  query CodigoPostal($cp: String!) {
    buscarCodigoPostal(cp: $cp) { cp estado estadoNombre ciudad colonias }
  }
`;

const QUERY_COTIZAR = `
  query CotizarEnvio($input: CotizarEnvioInput!) {
    cotizarEnvio(input: $input) { token paqueteria servicio descripcion dias costo modo }
  }
`;

export const QUERY_RASTREO = `
  query Rastreo($id: Int!) {
    rastrearPedido(id: $id) { guia paqueteria estado rastreoUrl eventos { fecha descripcion lugar } }
  }
`;

export const cpValido = (cp) => /^\d{5}$/.test(cp ?? "");
export const telefonoValido = (t) => /^\d{10}$/.test(t ?? "");

/** Campos que faltan para poder registrar el envío (vacío = completa). */
export function faltantes(d) {
  const nombres = { nombre: "nombre", calle: "calle", numero: "número", colonia: "colonia", ciudad: "ciudad" };
  const faltan = Object.entries(nombres).filter(([k]) => !String(d[k] ?? "").trim()).map(([, v]) => v);
  if (!cpValido(d.cp)) faltan.push("código postal");
  if (!d.estado) faltan.push("estado");
  if (!telefonoValido(d.telefono)) faltan.push("teléfono de 10 dígitos");
  return faltan;
}

export async function buscarCodigoPostal(cp) {
  const data = await graphqlRequest(QUERY_CP, { cp });
  return data.buscarCodigoPostal;
}

export async function cotizarEnvio(direccion, items) {
  const data = await graphqlRequest(QUERY_COTIZAR, {
    input: { cp: direccion.cp, estado: direccion.estado, ciudad: direccion.ciudad, items },
  });
  return data.cotizarEnvio;
}

/** Lo que va en PedidoInput.entrega */
export function entregaParaApi(tipo, direccion, opcion) {
  if (tipo !== "domicilio") return { tipo: "recoger" };
  return { tipo: "domicilio", ...direccion, opcionToken: opcion?.token ?? "" };
}
