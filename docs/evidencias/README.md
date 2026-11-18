# Evidencias de verificación (SRS FRECUENTE 2.1)

Reportes de Lighthouse 13.5.0 (Chrome DevTools) medidos sobre el sitio publicado <https://frecuente.onrender.com> con el commit `6faa99c` desplegado en Render, dispositivo **Mobile**. Las horas son del centro de México. Cada archivo `.html` se abre en el navegador y muestra el reporte completo.

## RQNF141 — Rendimiento de la página de inicio (umbral: 90 o más)

Tres corridas seguidas en modo *Navigation*. Se reporta la mediana, porque la puntuación varía entre corridas.

| Archivo | Ruta | Fecha y hora | Performance |
|---|---|---|---|
| `lighthouse/rendimiento-inicio-1.html` | `/` | 17/11/2026 22:58 | 79 |
| `lighthouse/rendimiento-inicio-2.html` | `/` | 17/11/2026 23:08 | 95 |
| `lighthouse/rendimiento-inicio-3.html` | `/` | 17/11/2026 23:08 | 91 |

**Mediana: 91** (corridas: 79, 95, 91). Cumple el umbral de 90.

## RQNF161 — Accesibilidad de las rutas del cliente (umbral: 0 incumplimientos A y AA de WCAG 2.1)

Categoría *Accessibility* de Lighthouse (reglas de axe-core). Las rutas públicas se midieron en modo *Navigation* sin sesión; las que requieren sesión, en modo *Snapshot* con la cuenta de prueba `mariana@frecuente.mx`. La lista de rutas es la de la sección 4.1 del SRS. `/pago/resultado` se midió sin parámetros porque, con un pedido válido, la página confirma el pago y redirige de inmediato a `/pedido`.

| Archivo | Ruta | Modo | Fecha y hora | Accessibility | Auditorías fallidas |
|---|---|---|---|---|---|
| `lighthouse/accesibilidad-inicio.html` | `/` | Navigation | 17/11/2026 23:07 | 100 | 0 |
| `lighthouse/accesibilidad-tienda.html` | `/tienda` | Navigation | 17/11/2026 22:58 | 100 | 0 |
| `lighthouse/accesibilidad-categoria.html` | `/categoria?id=1` | Navigation | 17/11/2026 23:09 | 100 | 0 |
| `lighthouse/accesibilidad-membresias.html` | `/membresias` | Navigation | 17/11/2026 23:09 | 100 | 0 |
| `lighthouse/accesibilidad-login.html` | `/login` | Navigation | 17/11/2026 23:10 | 100 | 0 |
| `lighthouse/accesibilidad-registro.html` | `/registro` | Navigation | 17/11/2026 23:10 | 100 | 0 |
| `lighthouse/accesibilidad-recuperar.html` | `/recuperar` | Navigation | 17/11/2026 23:10 | 100 | 0 |
| `lighthouse/accesibilidad-aviso-de-privacidad.html` | `/aviso-de-privacidad` | Navigation | 17/11/2026 23:10 | 100 | 0 |
| `lighthouse/accesibilidad-carrito.html` | `/carrito` | Snapshot | 17/11/2026 23:03 | 100 | 0 |
| `lighthouse/accesibilidad-checkout.html` | `/checkout` | Snapshot | 17/11/2026 23:14 | 100 | 0 |
| `lighthouse/accesibilidad-pago-simulado.html` | `/pago/simulado?pedido=51` | Snapshot | 17/11/2026 23:04 | 100 | 0 |
| `lighthouse/accesibilidad-pago-resultado.html` | `/pago/resultado` | Snapshot | 17/11/2026 23:17 | 100 | 0 |
| `lighthouse/accesibilidad-pedido.html` | `/pedido?id=51` | Snapshot | 17/11/2026 23:04 | 100 | 0 |
| `lighthouse/accesibilidad-cuenta.html` | `/cuenta` | Snapshot | 17/11/2026 23:05 | 100 | 0 |
| `lighthouse/accesibilidad-mi-membresia.html` | `/mi-membresia` | Snapshot | 17/11/2026 23:05 | 100 | 0 |

**Resultado:** las 15 rutas obtienen 100 con 0 auditorías fallidas. Cumple el RQNF161.

## Requisitos que siguen *Por verificar*

RQNF79, RQNF83, RQNF139, RQNF140, RQNF151, RQNF159 y RQNF160 se miden en el entorno de producción antes del lanzamiento (diciembre de 2026), con los métodos que indica la matriz 6.2 del SRS.
