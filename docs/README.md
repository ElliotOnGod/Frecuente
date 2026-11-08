# Documentación del Producto Integrador — Frecuente

E-commerce de café de especialidad para **Frecuente Café Bar** (Guadalajara).
Equipo: Jehu Uribe Bermúdez (23100139), José Fernando León López (23100146),
Elliot García López (22300923) · Grupo 8C1 · CETI Colomos.

| Entregable del PI | Documento |
|---|---|
| Propuesta formal del proyecto | `FRECUENTE_Propuesta_Producto_Integrador.docx` (entregada el 25/08/2026) y su resumen en [propuesta.md](propuesta.md) |
| Análisis FODA | [foda.md](foda.md) |
| Análisis de mercado | [analisis-mercado.md](analisis-mercado.md) |
| SFW: alcance funcional | [sfw.md](sfw.md) |
| Mapas (sitio, navegación, procesos, estados) | [mapas.md](mapas.md) |
| Diseño: brief, wireframes, mockups y prototipo | [diseno.md](diseno.md) |
| Documentación técnica (arquitectura, instalación, configuración, uso) | [tecnica.md](tecnica.md) |
| UML de componentes y de entidades (entregas P2 y P6) | [uml-componentes.svg](uml-componentes.svg), [uml-entidades.svg](uml-entidades.svg) |

## Cumplimiento de los requisitos mínimos

| Requisito | Cómo se cumple |
|---|---|
| Astro | Front con rutas por archivo y arquitectura de islas (`front/src/pages`) |
| React | Islas interactivas: carrito, checkout, filtros, panel (`front/src/components/islas`) |
| PostgreSQL | Usuarios, pedidos, renglones, pagos, envíos, recompras y correos (`back/relacional.py`, `back/sql/`) |
| MongoDB | Catálogo con variantes, fotos, planes y membresías (`back/database.py`) |
| GraphQL | API principal en `/graphql` con Query, Mutation y Subscription (`back/schema.py`) |
| MCP | Servidor Model Context Protocol en `/mcp` para agentes de IA (`back/servidor_mcp.py`) |
| Mercado Pago y PayPal | Checkout Pro y Orders v2, en modo simulado o sandbox (`back/pagos.py`) |
| 5+ APIs de terceros | Mercado Pago, PayPal, Envia.com (cotizar, guía, rastreo), Envia Geocodes (códigos postales), Brevo (correos), OpenFreeMap + MapLibre (mapa) |
| Control de versiones | Git + GitHub (`ElliotOnGod/Frecuente`), trabajo por ramas y pull requests |
| CI/CD | GitHub Actions: lint, pruebas, build y despliegue (`.github/workflows/ci.yml`) |
| Despliegue en la nube | Backend en Render, front en Netlify, PostgreSQL en Neon, MongoDB en Atlas |
| Secretos seguros | Variables de entorno en Render/Netlify/GitHub Secrets; nada sensible en el código (`back/.env.example`) |
