import { useEffect, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";
import { LOCAL, DIRECCION_COMPLETA, ENLACES_LOCAL } from "../../lib/local";

/**
 * MapaLocal — mapa interactivo con la ubicación del local.
 *
 * API gratuita y sin llave:
 *  - MapLibre GL JS (código abierto) dibuja el mapa en la tarjeta de video.
 *  - OpenFreeMap da los mapas vectoriales (datos de OpenStreetMap): gratis,
 *    sin registro, sin API key y sin límite de visitas.
 *
 * Como los mapas son VECTORIALES (no imágenes), se pueden pintar con la
 * paleta del Manual de Identidad: fondo Crema, calles blancas, parques Hoja,
 * avenidas Tostado y edificios en 3D. En modo oscuro se usa la variante
 * oscura de la misma paleta y cambia en vivo si el sistema cambia de modo.
 *
 * Detalles:
 *  - MapLibre usa `window`, así que se importa dentro del useEffect (solo en
 *    el navegador). En la página se monta con client:visible: el JavaScript
 *    del mapa no se descarga hasta que el usuario llega a esa sección.
 *  - "Gestos cooperativos": con la rueda sola la página sigue haciendo
 *    scroll; para hacer zoom se usa Ctrl + rueda (o dos dedos en el celular).
 *  - Si el usuario pidió reducir animaciones, no hay vuelo inicial ni pulso.
 */

const ESTILO = "https://tiles.openfreemap.org/styles/positron";

/** Paleta del manual para el mapa (claro / oscuro). */
const PALETA = {
  claro: {
    fondo: "#F3E5D4", // Crema
    zona: "#EFDDC8",
    parque: "#D5E0CB", // Hoja muy clara
    agua: "#C9D9D6",
    edificio: "#E7D2BA",
    edificio3d: "#E3CBB0",
    calle: "#FFFFFF",
    borde: "#E2CDB5",
    avenida: "#F0D3AE", // Tostado claro
    texto: "#6B625C", // Gris Humo
    halo: "#F3E5D4",
  },
  oscuro: {
    fondo: "#1F1B18", // Carbón
    zona: "#241F1C",
    parque: "#26302A",
    agua: "#22302F",
    edificio: "#2E2622",
    edificio3d: "#3A302A",
    calle: "#3A322D",
    borde: "#2A2320",
    avenida: "#5A4433",
    texto: "#B3A79E",
    halo: "#1F1B18",
  },
};

/** Qué color de la paleta le toca a cada capa del estilo de OpenFreeMap. */
function colorDeCapa(capa, p) {
  const id = capa.id;
  if (capa.type === "background") return { "background-color": p.fondo };
  if (capa.type === "fill") {
    if (id.includes("water")) return { "fill-color": p.agua };
    if (id.includes("park") || id.includes("wood")) return { "fill-color": p.parque, "fill-opacity": 0.9 };
    if (id === "building") return { "fill-color": p.edificio };
    if (id.includes("landuse") || id.includes("aeroway") || id.includes("pier")) return { "fill-color": p.zona };
    return null;
  }
  if (capa.type === "line") {
    if (id.includes("waterway")) return { "line-color": p.agua };
    if (id.includes("boundary")) return { "line-color": p.texto, "line-opacity": 0.3 };
    if (id.includes("rail")) return { "line-color": p.borde };
    if (id.includes("casing")) return { "line-color": p.borde };
    if (id.includes("motorway") || id.includes("major")) return { "line-color": p.avenida };
    if (id.includes("highway") || id.includes("road") || id.includes("aeroway")) return { "line-color": p.calle };
    return null;
  }
  if (capa.type === "symbol") return { "text-color": p.texto, "text-halo-color": p.halo, "text-halo-width": 1.4 };
  return null;
}

function pintarMapa(mapa, oscuro) {
  const p = oscuro ? PALETA.oscuro : PALETA.claro;
  for (const capa of mapa.getStyle().layers) {
    const pintura = colorDeCapa(capa, p);
    if (!pintura) continue;
    for (const [prop, valor] of Object.entries(pintura)) {
      try {
        mapa.setPaintProperty(capa.id, prop, valor);
      } catch {
        /* la propiedad no aplica a esa capa: se deja como viene */
      }
    }
  }
  if (mapa.getLayer("edificios-3d")) mapa.setPaintProperty("edificios-3d", "fill-extrusion-color", p.edificio3d);
}

/** Edificios en 3D (aparecen al acercarse, con la altura de OpenStreetMap). */
function agregarEdificios3d(mapa) {
  const etiquetas = mapa.getStyle().layers.find((c) => c.type === "symbol")?.id;
  mapa.addLayer(
    {
      id: "edificios-3d",
      type: "fill-extrusion",
      source: "openmaptiles",
      "source-layer": "building",
      minzoom: 15,
      paint: {
        "fill-extrusion-color": PALETA.claro.edificio3d,
        "fill-extrusion-height": ["coalesce", ["get", "render_height"], 6],
        "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
        "fill-extrusion-opacity": 0.85,
      },
    },
    etiquetas // debajo de los nombres de calles
  );
}

/** Pin propio: gota Espresso con la taza "coffee" de Lucide (el set del manual). */
function crearPin() {
  const pin = document.createElement("div");
  pin.className = "cf-pin";
  pin.setAttribute("role", "img");
  pin.setAttribute("aria-label", LOCAL.nombre);
  pin.innerHTML = `
    <span class="cf-pin__pulso" aria-hidden="true"></span>
    <span class="cf-pin__gota" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 2v2"/><path d="M14 2v2"/><path d="M6 2v2"/>
        <path d="M16 8a1 1 0 0 1 1 1v8a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1h14a4 4 0 1 1 0 8h-1"/>
      </svg>
    </span>`;
  return pin;
}

const TEXTOS_ES = {
  "NavigationControl.ZoomIn": "Acercar",
  "NavigationControl.ZoomOut": "Alejar",
  "NavigationControl.ResetBearing": "Orientar al norte",
  "CooperativeGesturesHandler.WindowsHelpText": "Usa Ctrl + rueda del mouse para hacer zoom",
  "CooperativeGesturesHandler.MacHelpText": "Usa ⌘ + rueda del mouse para hacer zoom",
  "CooperativeGesturesHandler.MobileHelpText": "Usa dos dedos para mover el mapa",
};

export default function MapaLocal() {
  const contenedor = useRef(null);
  const [listo, setListo] = useState(false);
  const [fallo, setFallo] = useState(false);

  useEffect(() => {
    let mapa = null;
    let cancelado = false;
    const temaOscuro = window.matchMedia?.("(prefers-color-scheme: dark)");
    const sinAnimacion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const alCambiarTema = () => mapa?.isStyleLoaded() && pintarMapa(mapa, temaOscuro.matches);

    import("maplibre-gl")
      .then(({ default: maplibregl }) => {
        if (cancelado || !contenedor.current) return;

        const destino = { center: [LOCAL.lng, LOCAL.lat], zoom: 17, pitch: 50, bearing: -20 };
        mapa = new maplibregl.Map({
          container: contenedor.current,
          style: ESTILO,
          // Arranca más lejos y "vuela" hasta el local (salvo movimiento reducido)
          ...(sinAnimacion ? destino : { center: destino.center, zoom: 13.5, pitch: 0, bearing: 0 }),
          minZoom: 11,
          maxZoom: 19,
          cooperativeGestures: true,
          attributionControl: { compact: true },
          locale: TEXTOS_ES,
        });
        mapa.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");

        const popup = new maplibregl.Popup({ offset: 46, closeButton: false, className: "cf-popup" }).setHTML(
          `<strong>${LOCAL.nombre}</strong><br>${DIRECCION_COMPLETA}<br>` +
            `<a href="${ENLACES_LOCAL.googleMaps}" target="_blank" rel="noopener">Cómo llegar →</a>`
        );
        new maplibregl.Marker({ element: crearPin(), anchor: "bottom" })
          .setLngLat(destino.center)
          .setPopup(popup)
          .addTo(mapa);

        mapa.on("load", () => {
          if (cancelado) return;
          agregarEdificios3d(mapa);
          pintarMapa(mapa, temaOscuro?.matches);
          setListo(true);
          if (!sinAnimacion) mapa.flyTo({ ...destino, duration: 2600, essential: false });
        });
        mapa.on("error", (e) => {
          // Un tile que falla no rompe el mapa; solo se avisa si no cargó el estilo
          if (!mapa.isStyleLoaded() && !listo) setFallo(Boolean(e?.error));
        });
        temaOscuro?.addEventListener?.("change", alCambiarTema);
      })
      .catch(() => setFallo(true));

    return () => {
      cancelado = true;
      temaOscuro?.removeEventListener?.("change", alCambiarTema);
      mapa?.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="cf-mapa">
      <div
        ref={contenedor}
        className="cf-mapa__lienzo"
        role="region"
        aria-label={`Mapa: ${LOCAL.nombre}, ${DIRECCION_COMPLETA}`}
      />
      {!listo && !fallo && <div className="cf-mapa__cargando cf-skeleton" aria-hidden="true" />}
      {fallo && (
        <p className="cf-mapa__fallo">
          No se pudo cargar el mapa.{" "}
          <a href={ENLACES_LOCAL.openStreetMap} target="_blank" rel="noopener">Ver en OpenStreetMap</a>
        </p>
      )}
    </div>
  );
}
