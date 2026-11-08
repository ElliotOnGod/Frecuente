# Documentación técnica

## 1. Arquitectura
```
front/  Astro 7 + islas de React 19 + Zustand   → Netlify (sitio estático)
back/   FastAPI + Strawberry GraphQL + MCP       → Render
        ├─ PostgreSQL (Neon)   transaccional: usuarios, pedidos, pagos, envíos, recompras, correos
        └─ MongoDB (Atlas)     documentos: catálogo, fotos, planes, membresías
```
Diagramas: [mapas.md](mapas.md) (arquitectura, secuencia de compra, estados, modelo
relacional) y los UML [de componentes](uml-componentes.svg) y [de entidades](uml-entidades.svg).

### Persistencia políglota: por qué dos bases
| Dato | Base | Razón |
|---|---|---|
| Usuarios, pedidos, renglones, pagos, envíos | PostgreSQL | Relaciones fijas con llaves foráneas, `CHECK`, `UNIQUE` y transacciones: un pedido inserta en 4 tablas y debe quedar todo o nada. Agregaciones SQL para el panel (`GROUP BY`, `generate_series`, `FILTER`). |
| Suscripciones de recompra | PostgreSQL | `FOR UPDATE SKIP LOCKED` evita generar dos pedidos si dos procesos corren a la vez. |
| Catálogo (variantes, métodos, galería) | MongoDB | Cada producto tiene campos distintos (algunos con variantes, otros no); se lee completo. |
| Membresías con canjes | MongoDB | Los canjes van embebidos y el candado de "uno por día" es una sola actualización atómica. |

Las dos se unen por id: `pedido_items.producto_id` → producto (Mongo) y
`membresias.usuario_id` → `usuarios.id` (Postgres). Como una transacción no abarca dos
bases, el stock (Mongo) se descuenta primero con una actualización condicional y, si el
pedido falla en Postgres, se **compensa** (se regresa).

### Módulos del backend
| Archivo | Qué hace |
|---|---|
| `main.py` | App FastAPI: `/graphql`, `/mcp`, `/imagenes/<id>`, `/webhooks/mercadopago`, `/tareas/recompras`, `/salud`; CORS; ciclo de recompras cada hora |
| `schema.py` | Esquema GraphQL (tipos, queries, mutations, subscriptions) y reglas de negocio |
| `relacional.py` | PostgreSQL: pool de conexiones, migraciones, consultas y transacciones; migra los datos viejos desde Mongo |
| `sql/001_inicial.sql` | Tablas, restricciones e índices de PostgreSQL |
| `database.py` | MongoDB: colecciones con `$jsonSchema`, índices y datos de ejemplo |
| `pagos.py` | Mercado Pago (Checkout Pro) y PayPal (Orders v2), modos simulado/sandbox, verificación de firma del webhook |
| `envios.py` | Envia.com: código postal, cotización firmada (HMAC), guía y rastreo |
| `correos.py` | Brevo: plantillas HTML y envío en segundo plano con bitácora |
| `servidor_mcp.py` | Servidor MCP (Streamable HTTP) con herramientas públicas y de admin |
| `auth.py` | PBKDF2 y JWT |
| `eventos.py` | Pub/sub en memoria para las Subscriptions |

## 2. APIs de terceros
| API | Uso | Modo sin llave |
|---|---|---|
| Mercado Pago | Cobro con tarjeta, OXXO, saldo | Pasarela simulada |
| PayPal | Cobro con cuenta PayPal | Pasarela simulada |
| Envia.com (`/ship/rate`, `/ship/generate`, `/ship/generaltrack`) | Cotizar, generar guía, rastrear | Tabla de precios local y guías `SIM…` |
| Envia Geocodes | Estado, ciudad y colonias por CP | Siempre real (API pública) |
| Brevo (`/v3/smtp/email`) | Correos transaccionales | Se anotan en la bitácora |
| OpenFreeMap + MapLibre | Mapa del local | Siempre real |

## 3. API propia
- **GraphQL** `POST /graphql` (GraphiQL en el navegador) y `WS /graphql` para
  Subscriptions. Lista completa de operaciones en el encabezado de `back/schema.py` y en
  el README.
- **MCP** `POST /mcp`. Herramientas: `buscar_productos`, `ver_producto`,
  `listar_categorias`, `metodos_de_preparacion`, `cotizar_envio` y, con
  `Authorization: Bearer <token de admin>`, `estado_de_pedido`, `resumen_de_ventas`,
  `productos_con_poco_stock`, `pedidos_por_cobrar`. Para probarlo:
  `npx @modelcontextprotocol/inspector` → URL `http://localhost:8000/mcp`.

## 4. Instalación local
Requisitos: Python 3.11+, Node 22+, MongoDB y PostgreSQL (locales o en la nube).

```bash
# Backend
cd back
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env            # y llena DATABASE_URL y MONGO_URI
uvicorn main:app --reload --port 8000

# Frontend (otra terminal)
cd front
npm install
npm run dev                       # http://localhost:4321
```
Al primer arranque el backend crea las tablas (migraciones), las colecciones, y carga los
datos de ejemplo. Si la base de MongoDB es de una entrega anterior, copia sus usuarios y
pedidos a PostgreSQL conservando los ids.

## 5. Configuración (variables de entorno)
Todas están explicadas en `back/.env.example`. Las importantes en producción:

| Variable | Dónde | Para qué |
|---|---|---|
| `DATABASE_URL` | Render | PostgreSQL (Neon, con `sslmode=require`) |
| `MONGO_URI`, `MONGO_DB` | Render | MongoDB Atlas |
| `JWT_SECRET` | Render | Firma de sesiones, códigos de canje y cotizaciones |
| `TZ=America/Mexico_City` | Render | El "día" de membresías y recompras |
| `CORS_ORIGENES` | Render | Dominio de Netlify |
| `PAGOS_MODO`, `MP_*`, `PAYPAL_*` | Render | Pasarelas |
| `ENVIA_TOKEN`, `ENVIA_API` | Render | Envíos |
| `BREVO_API_KEY`, `BREVO_REMITENTE`, `CORREO_TIENDA` | Render | Correos |
| `CRON_SECRET` | Render + GitHub Secret | `POST /tareas/recompras` |
| `PUBLIC_API_URL` | Netlify + GitHub Variable | URL del backend para el front |
| `RENDER_DEPLOY_HOOK_URL`, `NETLIFY_BUILD_HOOK_URL` | GitHub Secrets | Despliegue desde el pipeline |

Ningún secreto está en el código ni en el repositorio (`.env` está en `.gitignore`).

## 6. Calidad y CI/CD
| Etapa | Backend | Frontend |
|---|---|---|
| Validación / análisis de calidad | `ruff check .` (PEP 8, errores, bugbear, seguridad básica) | `npm run lint` (ESLint + reglas de React y hooks) |
| Pruebas automatizadas | `pytest` (42 pruebas contra PostgreSQL y MongoDB reales) | `npm test` (Vitest: carrito, formatos, envíos, seguridad de redirección) |
| Build de producción | Arranque del backend con las dos bases | `npm run build` (Astro) y artefacto `front-dist` |
| Despliegue | Deploy hook de Render (o Auto-Deploy "After CI checks pass") | Build hook de Netlify |

Workflows: `.github/workflows/ci.yml` (cada push y pull request; despliega solo desde
`main` si todo pasó) y `.github/workflows/recompras.yml` (cron diario de respaldo).

Qué cubren las pruebas del backend: hash y tokens, registro y login, permisos de admin,
cuentas desactivadas, filtros del catálogo, variantes, validación de fotos por bytes,
total calculado por el servidor, compensación de stock, **6 compras simultáneas de la
última pieza (solo una gana)**, idempotencia del pago, cancelación, cotización firmada y
sus intentos de alteración, guía y rastreo, recompras (incluye no duplicar), cron con
clave, servidor MCP y salud de las dos bases.

## 7. Seguridad
- Contraseñas PBKDF2-SHA256 con sal; login con mismo mensaje y tiempo si el correo no existe.
- JWT firmado; las cuentas desactivadas invalidan su token al momento.
- El servidor calcula precios, envío (firma HMAC de la cotización) y confirma el pago con
  el proveedor; webhooks con verificación de firma.
- SQL con parámetros y nombres de columna de una lista blanca (`psycopg.sql`).
- Fotos validadas por sus primeros bytes (sin SVG); `nosniff`.
- Redirección del login solo a rutas internas.
- CORS restringible con `CORS_ORIGENES`; endpoint de cron con clave y comparación en tiempo constante.

## 8. Uso
- **Cliente:** Tienda → producto → molienda → carrito → checkout (entrega, pago, recompra)
  → pasarela → pedido con rastreo. En "Mi cuenta" ve pedidos y administra recompras.
- **Administrador:** `/admin` con resumen, pedidos (confirmar pago, enviar con guía,
  entregar, cancelar, reembolsar), caja de membresías, recompras ("Procesar ahora"),
  clientes (rol y activación), productos (fotos, variantes, métodos, peso) e
  integraciones (estado de las APIs y correos enviados).
