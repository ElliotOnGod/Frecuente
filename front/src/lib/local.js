/**
 * local.js — datos del local físico de Frecuente, en un solo lugar.
 * Los usan la sección "Visítanos" del inicio (Ubicacion.astro), la isla del
 * mapa (MapaLocal.jsx) y el pie de página.
 *
 * Coordenadas: se sacaron de OpenStreetMap interpolando los números de casa
 * de C. Justo Sierra (el 2665 está en la acera sur, antes de la esquina con
 * Severo Díaz). Los botones de "Cómo llegar" buscan el lugar por nombre y
 * dirección, así que la ruta llega a la puerta aunque el pin varíe unos metros.
 */
export const LOCAL = {
  nombre: "Frecuente Café Bar GDL",
  calle: "C. Justo Sierra 2665",
  colonia: "Arcos Vallarta",
  ciudad: "44650 Guadalajara, Jal.",
  lat: 20.67752,
  lng: -103.38385,
};

export const DIRECCION_COMPLETA = `${LOCAL.calle}, ${LOCAL.colonia}, ${LOCAL.ciudad}`;

const destino = encodeURIComponent(`${LOCAL.nombre}, ${DIRECCION_COMPLETA}`);

/** Enlaces gratuitos (no necesitan API key): abren la app de mapas del usuario. */
export const ENLACES_LOCAL = {
  googleMaps: `https://www.google.com/maps/dir/?api=1&destination=${destino}`,
  waze: `https://waze.com/ul?ll=${LOCAL.lat},${LOCAL.lng}&navigate=yes`,
  openStreetMap: `https://www.openstreetmap.org/?mlat=${LOCAL.lat}&mlon=${LOCAL.lng}#map=18/${LOCAL.lat}/${LOCAL.lng}`,
};
