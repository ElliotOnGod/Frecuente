/**
 * imagenes.js — fotos de productos y categorías.
 *
 * Una imagen puede ser:
 *  - una URL externa https://… (las fotos de ejemplo vienen de Unsplash)
 *  - una foto subida desde el panel: "/imagenes/<id>", que sirve el backend
 *    (no el front), por eso hay que anteponerle el dominio del backend.
 */
import { graphqlRequest } from "./graphql";

const API_URL = import.meta.env.PUBLIC_API_URL || "http://localhost:8000/graphql";
// http://localhost:8000/graphql → http://localhost:8000
const ORIGEN_BACKEND = new URL(API_URL).origin;

export const MAX_IMAGENES = 6;

/**
 * URL lista para <img src>. `ancho` pide a Unsplash una versión del tamaño
 * justo (una tarjeta no necesita una foto de 4000 px).
 */
export function urlImagen(url, ancho) {
  if (!url) return "";
  if (url.startsWith("/imagenes/")) return ORIGEN_BACKEND + url;
  if (ancho && url.startsWith("https://images.unsplash.com/")) {
    const u = new URL(url);
    u.searchParams.set("w", String(ancho));
    return u.toString();
  }
  return url;
}

/** srcset para pantallas normales y de alta densidad (retina). */
export function srcsetImagen(url, ancho) {
  if (!url || !url.startsWith("https://images.unsplash.com/")) return undefined;
  return `${urlImagen(url, ancho)} 1x, ${urlImagen(url, ancho * 2)} 2x`;
}

const TIPOS = ["image/jpeg", "image/png", "image/webp"];
const LADO_MAX = 1400; // px: suficiente para el modal en pantallas retina
const PESO_ORIGINAL_MAX = 15 * 1024 * 1024;

/**
 * Comprime una foto en el navegador antes de subirla: la reduce a 1400 px
 * por lado y la convierte a WebP (o JPEG si el navegador no sabe WebP).
 * Una foto de celular de 5 MB queda en ~150–300 KB.
 * Regresa el contenido en base64 (sin el prefijo "data:").
 */
export async function comprimirImagen(archivo) {
  if (!TIPOS.includes(archivo.type)) {
    throw new Error(`"${archivo.name}" no es JPG, PNG ni WebP.`);
  }
  if (archivo.size > PESO_ORIGINAL_MAX) {
    throw new Error(`"${archivo.name}" pesa más de 15 MB.`);
  }

  const bitmap = await createImageBitmap(archivo).catch(() => {
    throw new Error(`No se pudo leer "${archivo.name}".`);
  });
  const escala = Math.min(1, LADO_MAX / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * escala);
  canvas.height = Math.round(bitmap.height * escala);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close?.();

  const aBlob = (tipo) => new Promise((ok) => canvas.toBlob(ok, tipo, 0.82));
  let blob = await aBlob("image/webp");
  // Safari viejo no genera WebP: toBlob regresa PNG. Entonces se usa JPEG.
  if (!blob || blob.type !== "image/webp") blob = await aBlob("image/jpeg");

  const dataUrl = await new Promise((ok, falla) => {
    const lector = new FileReader();
    lector.onload = () => ok(lector.result);
    lector.onerror = falla;
    lector.readAsDataURL(blob);
  });
  return String(dataUrl).split(",", 2)[1];
}

const MUTATION_SUBIR = `mutation SubirImagen($datos: String!) { subirImagen(datos: $datos) }`;

/** Comprime y sube una foto. Regresa su ruta ("/imagenes/<id>"). */
export async function subirImagen(archivo) {
  const datos = await comprimirImagen(archivo);
  const res = await graphqlRequest(MUTATION_SUBIR, { datos });
  return res.subirImagen;
}
