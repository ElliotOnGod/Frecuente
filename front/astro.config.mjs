// @ts-check
import { defineConfig } from "astro/config";
import react from "@astrojs/react";

// Frecuente — e-commerce. Astro genera páginas estáticas y React se usa
// solo en las "islas" que necesitan interactividad (catálogo, carrito, modal…).
export default defineConfig({
  integrations: [react()],
  server: { port: 4321, open: true },
});
