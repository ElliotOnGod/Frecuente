// @ts-check
import { defineConfig } from "astro/config";
import react from "@astrojs/react";

// Frecuente — e-commerce. Astro genera páginas estáticas y React se usa
// solo en las "islas" que necesitan interactividad (catálogo, carrito, modal…).
export default defineConfig({
  integrations: [react()],
  server: { port: 4321, open: true },
  vite: {
    build: {
      // maplibre-gl (el mapa de "Visítanos") pesa ~1 MB sin comprimir. No
      // frena la página: se descarga aparte y solo con client:visible, así
      // que se sube el límite del aviso para que no salga en cada build.
      chunkSizeWarningLimit: 1100,
    },
  },
});
