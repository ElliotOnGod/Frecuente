# Frecuente — e-commerce de café de especialidad (Producto Integrador)

**Equipo:**

| Integrante | Registro |
|---|---|
| Jehu Uribe Bermúdez | 23100139 |
| José Fernando León López | 23100146 |
| Elliot García López | 22300923 |

**Grupo:** 8C · **Materia:** Programación Web II · **CETI Colomos**

Avance funcional del proyecto final: tienda en línea de la cafetería
**Frecuente** (Guadalajara) para vender café en grano/molido, leches y
alternativas, matcha y accesorios.

Implementa lo documentado en los reportes **P2** (maquetado del flujo, UML de
componentes) y **P6** (backend GraphQL, UML de entidades), con la identidad
visual del **Manual de Identidad Digital — Café Frecuente v1.0**
(`front/src/styles/theme.css`, sin modificar).

**Sitio publicado:** <https://frecuente.onrender.com> · **API:**
<https://frecuente-api.onrender.com/graphql> · **Repositorio:**
<https://github.com/ElliotOnGod/Frecuente>

**Producto Integrador:** la especificación de requerimientos (SRS) y el
estudio de viabilidad se entregan como documentos aparte. Los diagramas UML
están en `docs/` (`uml-componentes.svg` y `uml-entidades.svg`).

| Requisito | Implementación |
|---|---|
| Astro + React | Rutas por archivo con islas de React (`front/`) |
| PostgreSQL + MongoDB | Persistencia políglota: transaccional en Postgres, catálogo y membresías en Mongo |
| GraphQL + MCP | `/graphql` para el front y `/mcp` para agentes de IA |
| Mercado Pago + PayPal | Checkout Pro y Orders v2 (simulado o sandbox) |
| 5+ APIs de terceros | Mercado Pago, PayPal, Envia.com, Envia Geocodes, Brevo, OpenFreeMap |
| CI/CD | GitHub Actions: lint, pruebas, build y despliegue (`.github/workflows/`) |
| Nube | Render (backend), Netlify (front), Neon (PostgreSQL), MongoDB Atlas |

---

## Cómo correrlo

Se levantan **dos procesos**: el backend en el puerto 8000 y el front (Astro) en el 4321.

### 1. Bases de datos (PostgreSQL y MongoDB)

El backend usa **dos bases**: PostgreSQL para usuarios, pedidos, pagos,
envíos, recompras y correos, y MongoDB para el catálogo, las fotos y las
membresías (ver [Bases de datos](#bases-de-datos)).

**PostgreSQL** (elige una):

- **En la nube (recomendado):** crea un proyecto gratis en [Neon](https://neon.tech),
  copia la *Connection string* y ponla en `back/.env` como `DATABASE_URL`.
- **Local:** instala PostgreSQL (`winget install PostgreSQL.PostgreSQL.17`),
  crea la base `frecuente` y usa
  `DATABASE_URL=postgresql://postgres:TU_CONTRASEÑA@localhost:5432/frecuente`.

**MongoDB** (elige una):

- **Local:** instala MongoDB Community Server como servicio. En Windows, desde
  una PowerShell como administrador: `winget install MongoDB.Server` (y,
  opcional, `winget install MongoDB.Compass.Full` para ver los datos).
  Revisa que esté corriendo con `Get-Service MongoDB` (debe decir `Running`).
  Queda en `mongodb://localhost:27017` y no hay que configurar nada más.
- **En la nube:** crea un clúster gratis en MongoDB Atlas, copia su cadena de
  conexión y ponla en `back/.env` como `MONGO_URI`.

No hace falta crear tablas ni colecciones a mano: al arrancar, el backend
aplica las migraciones de `back/sql/`, crea las colecciones con sus
validadores e índices y carga `datos_ejemplo.json`. **Si tu MongoDB es de una
entrega anterior**, copia sus usuarios y pedidos a PostgreSQL conservando los
ids (verás `PostgreSQL: se migraron N usuarios y M pedidos desde MongoDB`).

### 2. Backend (FastAPI + Strawberry + PostgreSQL + MongoDB)

```bash
cd back
python -m venv .venv
source .venv/bin/activate          # Windows (PowerShell): .\.venv\Scripts\activate
pip install -r requirements-dev.txt   # incluye pytest y ruff
copy .env.example .env                # (macOS/Linux: cp) y llena DATABASE_URL
uvicorn main:app --reload --port 8000
```

Pruebas y análisis de calidad (los mismos que corre GitHub Actions):

```bash
cd back
ruff check .
pytest            # usa las bases *_test: pon DATABASE_URL apuntando a una base de pruebas
```

> El zip **no trae** `back/.venv` ni `front/node_modules`: se crean en cada
> computadora con los comandos de arriba y `npm install`. Si copias el
> proyecto de otra PC con esas carpetas, bórralas primero (si no, salen
> errores como *"Unable to create process"* o
> *"SyntaxError: Invalid or unexpected token env.mjs"*). En Windows:
> `Remove-Item -Recurse -Force .venv` y `Remove-Item -Recurse -Force node_modules`.

Todas las variables están explicadas en `back/.env.example` (bases de datos,
pagos, Envia.com, Brevo, CORS y la clave del cron).

La primera vez verás `Catálogo 'frecuente' creado en MongoDB` y
`PostgreSQL: se cargaron los usuarios y pedidos de ejemplo`, con 4 categorías, 9 productos, cuentas de prueba y
**36 pedidos de ejemplo** repartidos en los últimos 30 días (para que el
panel de administración tenga gráficas desde el primer arranque):

| Cuenta | Correo | Contraseña |
|---|---|---|
| Cliente | `demo@frecuente.mx` | `cafe1234` |
| Administrador | `admin@frecuente.mx` | `admin1234` |
| Clientes extra | `mariana@frecuente.mx`, `carlos@frecuente.mx`, `compras@andares.mx` | `cafe1234` |

> **Si ya tenías la base de la entrega anterior:** no hace falta borrarla; al
> arrancar se actualizan los validadores e índices solos. Pero para ver los
> pedidos de ejemplo del panel corre una vez `python database.py` (borra y
> recarga todo).

También se cargan **3 planes de membresía** y 5 membresías de ejemplo (el
cliente demo tiene "Café + Comida" activa). Si ya tenías la base de una
entrega anterior, al arrancar se agregan solas las colecciones `planes` y
`membresias` sin tocar tus datos.

Para regresar a los datos de ejemplo (borra pedidos y cambios):
`python database.py`.

Para probar el API a mano: <http://localhost:8000/graphql> (GraphiQL).

### Pagos: modo simulado o sandbox

No necesitas cuentas para la demo: por defecto `PAGOS_MODO=simulado` y, al
pagar con Mercado Pago o PayPal (un pedido **o una membresía**), el sitio abre
una **pasarela de prueba propia** (`/pago/simulado`). Ahí puedes:

- **Pagar con tarjeta sin iniciar sesión** (como invitado) o entrar con una
  cuenta de prueba (`comprador@`, `sinfondos@`, `nueva@` u `oxxo@prueba.frecuente`,
  contraseña `prueba1234`).
- **Escribir la tarjeta** (número, titular, vencimiento y CVV). Se valida el
  número con el algoritmo de Luhn, la marca, el vencimiento y el CVV.
- Usar las **tarjetas de prueba de Mercado Pago México**. Igual que en su
  sandbox, **el nombre del titular decide el resultado**:

  | Tarjeta | Número | CVV | Vence |
  |---|---|---|---|
  | Mastercard | 5474 9254 3267 0366 | 123 | 11/30 |
  | Visa | 4075 5957 1648 3764 | 123 | 11/30 |
  | American Express | 3711 803032 57522 | 1234 | 11/30 |
  | Mastercard débito | 5579 0534 6148 2647 | 123 | 11/30 |
  | Visa débito | 4189 1412 2126 7633 | 123 | 11/30 |

  Titular: `APRO` aprobado · `CONT` pendiente · `FUND` fondos insuficientes ·
  `SECU` CVV inválido · `EXPI` vencimiento · `OTHE` error general.

- También acepta tarjetas genéricas de prueba (`4242 4242 4242 4242` aprobada,
  `4000 0000 0000 9995` sin fondos, `4000 0000 0000 0002` rechazada…).

Solo acepta **números de prueba**: si alguien escribe una tarjeta real, la
rechaza. El número completo nunca sale del navegador; al backend solo llega el
resultado. Si una tarjeta se rechaza, te quedas en la pasarela y puedes usar otra.

Para conectarlo a los **entornos de prueba reales** (no se mueve dinero):

1. Copia `back/.env.example` a `back/.env` y pon `PAGOS_MODO=sandbox`.
2. **Mercado Pago:**
   - En *Tus integraciones → tu aplicación → Credenciales de prueba* copia el
     Access Token (`TEST-…`) a `MP_ACCESS_TOKEN`.
   - En *Cuentas de prueba* crea (o usa) un **comprador de prueba** y pon su
     correo en `MP_COMPRADOR_PRUEBA`.
   - Paga en una **ventana de incógnito**, entrando a Mercado Pago con ese
     comprador de prueba (nunca con tu cuenta real), con una tarjeta de la
     tabla de arriba y titular `APRO`.
   - Al terminar da clic en **"Volver al sitio"**. Si cerraste la pestaña,
     abre el pedido (o *Mi membresía*) en la tienda: se revisa solo con
     Mercado Pago (y hay un botón **"Revisar mi pago"**).
3. **PayPal:** en developer.paypal.com → *Apps & Credentials (Sandbox)* copia
   `PAYPAL_CLIENT_ID` y `PAYPAL_SECRET`. Paga con una cuenta *Personal* del sandbox.
4. Reinicia el backend. En el checkout la etiqueta cambia de "Prueba" a "Sandbox".

> ¿Por qué fallaban las tarjetas de prueba de Mercado Pago? En su entorno de
> pruebas **el pagador tiene que ser una cuenta de prueba**. Antes mandábamos
> el correo real del cliente como pagador y Mercado Pago rechazaba el pago.
> Ahora se manda el del comprador de prueba (o ninguno), y con credenciales
> `TEST-` se abre el checkout de pruebas (`sandbox_init_point`).

Si falta la llave de un proveedor, ese método se queda en simulado y los
demás siguen funcionando. Webhooks de Mercado Pago (opcional): expón el
backend con ngrok y pon esa URL en `BACKEND_PUBLIC_URL`.

### 3. Frontend (Astro + islas de React + Zustand)

En otra terminal (requiere Node 22 o superior):

```bash
cd front
npm install
npm run dev
```

Abre <http://localhost:4321>. Si el backend no está en el puerto 8000, copia
`.env.example` a `.env` y ajusta `PUBLIC_API_URL`.

Para generar la versión de producción: `npm run build` (sale en `front/dist/`)
y `npm run preview` para revisarla.

---

## Estructura

```
frecuente/
├── datos_ejemplo.json      Datos iniciales (categorías, productos, cuentas de prueba)
├── .github/workflows/      CI/CD (ci.yml) y recompras diarias (recompras.yml)
├── back/
│   ├── main.py             FastAPI, CORS, GraphQL, MCP, cron y salud
│   ├── schema.py           Tipos, Query, Mutation y Subscription (Strawberry)
│   ├── relacional.py       PostgreSQL: pool, migraciones, pedidos, pagos, envíos, recompras
│   ├── sql/                Migraciones de PostgreSQL (001_inicial.sql)
│   ├── envios.py           Envia.com: código postal, cotización firmada, guía y rastreo
│   ├── correos.py          Brevo: correos automáticos y su bitácora
│   ├── servidor_mcp.py     Servidor MCP para agentes de IA
│   ├── tests/              Pruebas automatizadas (pytest)
│   ├── ruff.toml           Reglas del análisis de calidad
│   ├── database.py         MongoDB (catálogo y membresías), validadores e init_db()
│   ├── auth.py             Hash de contraseñas (PBKDF2) y tokens de sesión (JWT)
│   ├── pagos.py            Métodos de cobro: Mercado Pago, PayPal, transferencia, efectivo
│   ├── eventos.py          Pub/sub en memoria que alimenta las Subscriptions (tiempo real)
│   ├── .env.example        Datos de conexión (copiar a .env)
│   ├── requirements.txt
│   └── requirements-dev.txt  + pytest, httpx y ruff
├── front/                  Astro
│   ├── astro.config.mjs    Integración de React
│   ├── public/             favicon y archivos estáticos
│   └── src/
│       ├── layouts/BaseLayout.astro    TopBar + página + Footer + modal
│       ├── layouts/AdminLayout.astro   BaseLayout + menú lateral + conexión en vivo
│       ├── pages/                      Una página por vista (rutas reales)
│       │   ├── index.astro             /
│       │   ├── tienda.astro            /tienda (buscador y filtros por método)
│       │   ├── categoria.astro         /categoria?id=N
│       │   ├── carrito.astro           /carrito
│       │   ├── checkout.astro          /checkout
│       │   ├── pedido.astro            /pedido?id=N (estado del pago, instrucciones, reintentar)
│       │   ├── pago/simulado.astro     /pago/simulado?pedido=N (pasarela de prueba)
│       │   ├── pago/resultado.astro    /pago/resultado (regreso de Mercado Pago / PayPal)
│       │   ├── admin/index.astro       /admin (resumen y gráficas)
│       │   ├── admin/pedidos.astro     /admin/pedidos (filtros y cambio de estado)
│       │   ├── admin/productos.astro   /admin/productos (inventario y altas/bajas)
│       │   ├── admin/caja.astro        /admin/caja (validar código y registrar canje)
│       │   ├── admin/membresias.astro  /admin/membresias (miembros y planes)
│       │   ├── admin/clientes.astro    /admin/clientes (compras, membresía, rol y activación)
│       │   ├── admin/recompras.astro   /admin/recompras (suscripciones de recompra)
│       │   ├── admin/integraciones.astro /admin/integraciones (APIs y correos enviados)
│       │   ├── membresias.astro        /membresias (planes y contratación)
│       │   ├── mi-membresia.astro      /mi-membresia (código del día en vivo, canjes)
│       │   ├── login.astro             /login?siguiente=/ruta
│       │   ├── registro.astro          /registro?siguiente=/ruta
│       │   ├── cuenta.astro            /cuenta (datos y mis pedidos)
│       │   └── 404.astro
│       ├── components/                 Componentes estáticos (.astro):
│       │   │                           TopBar, Hero, ContextSection, Ubicacion, Footer
│       │   └── islas/                  Componentes interactivos (React):
│       │                               CatalogoHome, Sidebar, CategoryGrid,
│       │                               CategoryDetail, ProductCard,
│       │                               ProductDetailModal, Cart, Checkout,
│       │                               OrderSuccess, CartButton, Skeleton,
│       │                               LoginForm, RegistroForm, SessionMenu,
│       │                               Cuenta, Insignia, PasarelaSimulada,
│       │                               ResultadoPago, Planes, MiMembresia, MapaLocal, Foto,
│       │                               Tienda, EntregaForm, EntregaPedido, MisRecompras
│       │                               admin/: SoloAdmin, AdminResumen,
│       │                               AdminPedidos, AdminProductos, Graficas,
│       │                               AvisosEnVivo, AdminCaja, AdminMembresias,
│       │                               AdminClientes, AdminRecompras, AdminIntegraciones
│       ├── store/useStore.js           Zustand: sesión, carrito, pedido y modal
│       ├── store/enVivo.js             Zustand: avisos en vivo del backoffice
│       ├── lib/carrito.js              Reglas del carrito con variantes (funciones puras + pruebas)
│       ├── lib/envios.js               Código postal, cotización y datos de entrega
│       ├── lib/graphql.js              Cliente GraphQL sobre fetch
│       ├── lib/formato.js              Iconos, formato de pesos, rutas y estados
│       ├── lib/pagos.js                Consultas y acciones de cobro compartidas
│       ├── lib/membresias.js           Consultas y acciones de membresía
│       ├── lib/local.js                Dirección, coordenadas y enlaces del local
│       ├── lib/imagenes.js             URLs de fotos y compresión antes de subir
│       ├── lib/subscripciones.js       Cliente WebSocket propio (graphql-transport-ws)
│       ├── hooks/useGraphQLQuery.js    Hook propio de fetching (con `recarga`)
│       ├── hooks/useSuscripcion.js     Hook propio para Subscriptions
│       ├── hooks/useRecargaEnVivo.js   Recarga una consulta cuando llega un aviso
│       ├── hooks/usePedidoPendiente.js Pedido sin pagar del carrito (lo sincroniza con el servidor)
│       └── styles/                     theme.css (manual) + global.css
└── docs/                   Diagramas UML en SVG (componentes y entidades)
```

## Arquitectura: Astro con islas

Astro genera el HTML de cada página y solo manda JavaScript a las partes que
lo necesitan (las **islas**). Lo que no cambia (Hero, banda de beneficios,
pie, encabezado) es `.astro` y llega como HTML puro.

| Isla | Directiva | Por qué |
|---|---|---|
| `CatalogoHome` | `client:load` | El skeleton ya viene en el HTML y se hidrata al cargar |
| `CategoryDetail`, `Cart`, `Checkout`, `OrderSuccess`, `CartButton`, `SessionMenu`, `LoginForm`, `RegistroForm`, `Cuenta`, `PasarelaSimulada`, `ResultadoPago` | `client:only="react"` | Dependen del navegador (URL, carrito o sesión guardados) |
| `Planes`, `MiMembresia` | `client:only="react"` | Dependen de la sesión; `MiMembresia` abre un WebSocket |
| `AdminResumen`, `AdminPedidos`, `AdminProductos`, `AdminCaja`, `AdminMembresias`, `AdminClientes` | `client:only="react"` | Dependen de la sesión de admin |
| `AvisosEnVivo` (en `AdminLayout`) | `client:only="react"` | Abre la única conexión en vivo del panel y la comparte por Zustand |
| `ProductDetailModal` | `client:only="react"` | Usa `createPortal` sobre `document.body` |
| `Foto` | (dentro de otras islas) | Foto con carga diferida y el icono de la categoría si no hay imagen |
| `MapaLocal` | `client:visible` | El mapa (MapLibre) solo se descarga cuando llegas a la sección "Visítanos" |

Todas las islas de una página comparten el mismo store de Zustand, por eso
una `ProductCard` puede abrir el modal aunque vivan en islas distintas.

## Navegación (antes máquina de estados, ahora rutas)

En el avance anterior `view` en el store decidía qué vista se pintaba. Con
Astro cada vista es una página real, así que se puede recargar, compartir el
enlace o usar el botón de atrás del navegador:

| Antes (evento del store) | Ahora |
|---|---|
| `goHome()` | enlace a `/` |
| `goToCategory(id)` | enlace a `/categoria?id=N` |
| `goToCart()` | enlace a `/carrito` |
| `goToCheckout()` | enlace a `/checkout` |
| `completeCheckout(pedido)` | guarda el pedido, vacía el carrito y va a la pasarela o a `/pedido?id=N` |
| `openProduct(id)` | sigue igual: abre el modal sin cambiar de página |

Como ahora sí se cambia de página, la sesión, el carrito y el último pedido
se guardan en `localStorage` con el middleware `persist` de Zustand.

## Inicio de sesión

1. **Registro** (`registrarUsuario`) o **login** (`iniciarSesion`): el backend
   revisa los datos y regresa `{ token, usuario }`.
2. El front guarda eso en el store (`sesion`) y, desde ahí, `graphqlRequest`
   manda en cada petición el encabezado `Authorization: Bearer <token>`.
3. El backend verifica el token (JWT firmado con `JWT_SECRET`, dura 7 días)
   para saber quién hace la petición. Si expiró o es inválido, responde
   "Tu sesión expiró…" y el front cierra la sesión solo.

Seguridad aplicada:

- Las contraseñas se guardan como **hash PBKDF2-SHA256 con sal** (nunca en
  texto) y se comparan en tiempo constante. `password_hash` nunca sale en la
  API.
- El login responde lo mismo si el correo no existe o si la contraseña está
  mal, para no revelar qué correos tienen cuenta.
- Correos únicos (índice único) y guardados en minúsculas; contraseña de
  mínimo 8 caracteres, validada en el front y otra vez en el backend.
- El pedido se registra a nombre del **usuario del token**, no de un id que
  mande el front. Cada cliente solo puede ver sus propios pedidos.
- Las cuentas nuevas siempre son `cliente`; crear, editar o borrar productos
  requiere rol `admin`.
- `?siguiente=` solo acepta rutas internas, así el login no se puede usar
  para redirigir a otro sitio (también rechaza trucos como `/\otro.com`,
  que el navegador interpreta como `//otro.com`).
- El login tarda lo mismo si el correo no existe (se verifica contra un hash
  falso), así el tiempo de respuesta tampoco revela qué correos tienen cuenta.
- Si falta `JWT_SECRET` en `back/.env` (o se dejó el valor de ejemplo), el
  backend genera una clave aleatoria al arrancar y lo avisa en la consola.
  Así nadie puede firmar tokens de admin con una clave conocida; para que las
  sesiones no se cierren al reiniciar, pon tu propia clave en `.env`.

Pantallas: el checkout pide iniciar sesión (o crear cuenta) y después regresa
solo al checkout con el carrito intacto. En la barra aparece "Iniciar sesión"
o el nombre del usuario, que lleva a `/cuenta` con sus datos, su historial de
pedidos y el botón para cerrar sesión.

## Métodos de pago

| Método | Cómo se cobra | Quién lo confirma |
|---|---|---|
| **Mercado Pago** | Checkout Pro: tarjeta, OXXO o saldo | El backend, preguntándole a Mercado Pago |
| **PayPal** | Orders API v2: se aprueba en PayPal y el backend captura el cobro | El backend, al capturar |
| **Transferencia SPEI** | Se muestran banco, CLABE, referencia `FREC-000012` y monto | El admin, al ver el depósito |
| **Efectivo al recoger** | Se aparta el pedido y se paga en el local | El admin, al entregarlo |

Flujo en línea:

1. **Checkout** → `registrarPedido(metodoPago)` valida y aparta stock; el pedido
   nace `registrado` con `pago.estado = pendiente`.
2. `iniciarPago` crea la preferencia (Mercado Pago) u orden (PayPal) y regresa
   la URL de la pasarela. En modo simulado regresa `/pago/simulado`.
3. El cliente paga y la pasarela lo regresa a `/pago/resultado?pedido=N…`.
4. `confirmarPago` **le pregunta al proveedor** con la llave secreta (nunca le
   cree al navegador): revisa que el pago sea de ese pedido, en MXN y por el
   total exacto. Si se aprobó, el pedido pasa a `pagado`.

Si el pago se rechaza, los productos siguen apartados: en `/pedido?id=N` el
cliente puede reintentar, **cambiar de método** o cancelar (el stock regresa).

**El carrito se conserva hasta que el pago se aprueba**:

- Registrar el pedido ya no vacía el carrito. Se guarda qué pedido está
  esperando pago (y de qué cuenta es) en el store de Zustand.
- Si el pago se rechaza, se abandona la pasarela o se cancela el pedido, el
  carrito sigue igual.
- Mientras haya un pedido sin pagar, el carrito lo avisa y el checkout **no
  deja crear otro igual** (se duplicaría el stock apartado): ofrece pagarlo o
  cancelarlo y hacer uno nuevo.
- Cuando el pago se aprueba (en línea, o cuando el admin confirma la
  transferencia / entrega en efectivo) salen del carrito **solo los productos
  de ese pedido**; lo que agregaste después se queda.
- Cerrar sesión no pierde el pedido pendiente; si entra otra cuenta en la misma
  computadora, no lo hereda.

Seguridad aplicada a pagos:

- Las llaves (`MP_ACCESS_TOKEN`, `PAYPAL_SECRET`) solo viven en el backend.
- Confirmación **idempotente**: si llega el aviso dos veces (regreso + webhook o
  recargar la página) no se duplica nada, y un pago aprobado nunca vuelve a
  pendiente.
- Llaves de idempotencia en Mercado Pago (`X-Idempotency-Key`) y PayPal
  (`PayPal-Request-Id`) para no crear cobros dobles.
- Webhook con verificación de firma (`x-signature`) si configuras `MP_WEBHOOK_SECRET`.
- Si pagan un pedido que ya estaba cancelado, queda **por reembolsar** en vez de perderse.
- Nota: en modo **simulado** cualquier cliente puede "aprobar" su propio pago
  (para eso es la demo). En sandbox eso ya no es posible.
- La pasarela simulada solo acepta tarjetas de prueba y nunca manda el número
  de tarjeta al servidor (como las pasarelas reales: la tienda no toca tarjetas).

## Tiempo real: GraphQL Subscriptions

Además de Query y Mutation, el esquema tiene un tipo **`Subscription`**. Una
subscription no responde una sola vez: se queda abierta por **WebSocket** y
el servidor manda un mensaje cada vez que pasa algo.

```
 Navegador                         Backend (FastAPI + Strawberry)
 ─────────                         ──────────────────────────────
 WebSocket ws://…/graphql  ───────▶ GraphQLRouter (graphql-transport-ws)
   connection_init {token}            │
   subscribe eventosAdmin             ▼
                                   async def eventos_admin(): ◀── cola asyncio
 ◀── next {pedido_nuevo}              while True: yield await cola.get()
 ◀── next {canje}                                   ▲
                                   eventos.publicar(…) ── la llaman las mutations
                                   (registrarPedido, confirmarPago, canjearMembresia…)
```

| Subscription | Quién | Para qué |
|---|---|---|
| `eventosAdmin` | Solo admin | Feed del backoffice: pedido nuevo, pago aprobado/rechazado, cambio de estado, stock bajo, membresía nueva/activada, canje |
| `seguirPedido(id)` | Dueño o admin | La página del pedido cambia sola cuando la tienda confirma la transferencia o lo envía |
| `seguirMembresia(id)` | Dueño o admin | "Mi membresía" marca el código como usado en cuanto la caja registra el canje |

Cómo está hecho:

- **`back/eventos.py`**: pub/sub en memoria. Cada conexión tiene su
  `asyncio.Queue`; `publicar()` copia el aviso a todas con
  `loop.call_soon_threadsafe` (se puede llamar desde los resolvers síncronos).
  Para varios servidores se cambiaría por Redis o Change Streams de MongoDB.
- **Sesión por WebSocket**: el navegador no deja poner encabezados en un
  WebSocket, así que el token va en `connection_init`
  (`{ "Authorization": "Bearer …" }`) y Strawberry lo deja en
  `context["connection_params"]`. `usuario_actual()` lo busca ahí.
- **Front sin dependencias**: `lib/subscripciones.js` implementa el protocolo
  `graphql-transport-ws` con el `WebSocket` del navegador (≈100 líneas), con
  ping/pong y reconexión automática (1 s, 2 s, 4 s… hasta 15 s).
- **Una sola conexión por pestaña** en el panel: la isla `AvisosEnVivo`
  (en el menú) se suscribe y guarda los avisos en un store de Zustand; las
  demás islas lo leen y se recargan solas con `useRecargaEnVivo`.

**Para verlo en la demo:** abre `/admin` como admin en una ventana y, en otra
(o en incógnito), haz un pedido como cliente. Sin recargar, al admin le sale
el aviso, el feed se actualiza y los números del resumen cambian. Para la caja:
abre `/mi-membresia` como `demo@frecuente.mx` (ahí está su código) y
`/admin/caja` como admin; al registrar el canje, el código del cliente se
tacha solo.

## Membresías

El cliente paga un **plan de 30 días** y puede canjear su beneficio **una vez
al día** en el local:

| Plan | Precio (ejemplo) | Incluye |
|---|---|---|
| Café Diario | $549 / 30 días | 1 café al día (americano, latte, capuchino o espresso) |
| Café + Comida | $1,199 / 30 días | 1 café + 1 alimento al día |
| Combo Frecuente | $1,499 / 30 días | Bebida de especialidad + alimento + postre al día |

Los planes se editan en `/admin/membresias` → *Planes* (precio, qué incluye,
opciones de canje, pausar la venta).

**Flujo del cliente:** `/membresias` → elige plan y método de pago
(los mismos 4 de la tienda) → pasarela (Mercado Pago / PayPal, o la de prueba)
→ `/mi-membresia` con su **código del día** (ej. `FM12-K7QX2P`).

**Flujo de la caja:** `/admin/caja` → escribe el código → ve al cliente, su
plan y si ya canjeó hoy → elige la opción (botones con las opciones del plan)
→ *Registrar canje*. En la pantalla del cliente el código se tacha al momento.

Ciclo de vida (`vencida` y `programada` no se guardan, se calculan con las fechas):

```
pendiente ──(pago aprobado / caja confirma)──▶ activa ──(pasa la fecha fin)──▶ vencida
    │                        renovación pagada antes de vencer ─▶ programada ─▶ activa
    └──────────────▶ cancelada ◀──── (si ya estaba pagada: queda por reembolsar)
```

Decisiones importantes:

- **Código del día con HMAC**: `codigo = HMAC-SHA256(JWT_SECRET, "id:fecha")`
  recortado a 6 caracteres. Cambia cada día, no se puede adivinar ni reusar
  el de ayer y **no se guarda en la base** (se recalcula para validar).
  Solo el dueño lo ve (`codigoHoy` es `null` para cualquier otro, incluso admin).
- **Un canje por persona al día, atómico**: el `find_one_and_update` del canje
  exige `"canjes.dia": {"$ne": hoy}` en el filtro. Si dos cajas canjean al
  mismo tiempo, MongoDB solo deja pasar una. Además se revisan todas las
  membresías del cliente (por si tiene una renovación).
- **Renovar sin perder días**: si pagas una membresía teniendo otra vigente,
  la nueva empieza cuando termina la actual (`programada`).
- **Precio congelado**: cada membresía guarda el precio con el que se vendió;
  cambiar el precio del plan no afecta a quien ya pagó.
- **Canjes embebidos** en la membresía (máx. ~31 por mes, siempre se leen con
  ella) y **plan por referencia** (lo comparten muchas membresías).
- Los pagos reusan `pagos.py`: a Mercado Pago/PayPal se manda la referencia
  `M5` (en vez de `37` de un pedido) y el webhook distingue las dos.

## Panel de administración (`/admin`)

Entra con `admin@frecuente.mx`; en la barra aparece **Panel**. Un cliente que
abre `/admin` ve "Sin acceso" y, aunque lo intente por GraphQL, el backend lo
rechaza (`requiere_admin`).

- **Resumen:** ventas, pedidos pagados, ticket promedio y monto por cobrar
  (7, 30 o 90 días, con comparación contra el periodo anterior); gráfica de
  ventas por día (SVG propio, con tooltip y vista de tabla); ventas por método
  de pago; pedidos por estado; los 5 más vendidos y el stock bajo. Arriba,
  accesos directos a lo que requiere acción (por enviar, por cobrar, por
  reembolsar). Los más vendidos y el conteo por estado usan
  **`aggregate()` de MongoDB** (`$match`, `$unwind`, `$group`, `$sort`).
- **Pedidos:** filtros por estado y método, búsqueda por número, `FREC-…`,
  nombre o correo, paginación, y un detalle con las acciones permitidas.
- **Productos:** editar stock en la misma tabla, crear y editar productos,
  eliminar (si nunca se ha vendido).
- **Caja (canjes):** validar el código del día y registrar el canje; lista de
  canjes de hoy que se actualiza sola con lo que registran otras cajas.
- **Membresías:** miembros con filtros (activas, por pagar, programadas,
  vencidas, canceladas), detalle con historial de canjes, confirmar pago
  manual (transferencia/efectivo), cancelar; y la administración de planes.
- **Clientes:** cada cliente con sus pedidos, lo que ha gastado (solo pagado),
  su última compra y su membresía vigente; enlaces a sus pedidos y membresía.

Todo el panel está **en vivo**: indicador "En vivo" en el menú, avisos
flotantes, feed de actividad en el resumen, y las listas se recargan solas
cuando llega un aviso que les afecta.

Ciclo de vida del pedido (validado en el backend con `TRANSICIONES`):

```
registrado ──(pago aprobado / admin confirma)──▶ pagado ──▶ enviado ──▶ entregado
     │  └──── efectivo: se cobra y entrega en el local ────────────────▶ entregado
     └───────────────▶ cancelado ◀──── (desde pagado: queda por reembolsar)
```

Cancelar regresa el stock una sola vez (actualización condicional).

## API GraphQL

Un solo endpoint: `POST /graphql` (y `WS /graphql` para las Subscriptions).

| | Operación | Acceso |
|---|---|---|
| Query | `categorias`, `categoria(id)`, `productos(categoriaId, metodo, buscar)`, `producto(id)`, `metodosPreparacion`, `metodosPago`, `buscarCodigoPostal(cp)`, `cotizarEnvio(input)` | Público |
| Query | `yo`, `misPedidos`, `pedido(id)`, `rastrearPedido(id)`, `misSuscripciones` | Con sesión (un cliente solo ve lo suyo) |
| Query | `resumenAdmin(dias)`, `pedidosAdmin(estado, metodo, buscar, limite, salto)`, `suscripcionesAdmin`, `correosAdmin`, `integraciones` | Solo admin |
| Mutation | `registrarUsuario`, `iniciarSesion` | Público |
| Mutation | `registrarPedido` (con `entrega` y `recompraCadaDias`), `iniciarPago`, `confirmarPago`, `cancelarMiPedido`, `cambiarMiSuscripcion` | Con sesión |
| Mutation | `crearProducto`, `actualizarProducto`, `eliminarProducto`, `subirImagen`, `cambiarEstadoPedido`, `generarGuia`, `marcarReembolsado`, `procesarRecompras`, `cambiarRolUsuario`, `cambiarActivoUsuario` | Solo admin |
| Query | `planes` | Público (`incluirInactivos` solo admin) |
| Query | `miMembresia`, `misMembresias`, `membresia(id)` | Con sesión |
| Query | `resumenMembresias`, `membresiasAdmin(...)`, `membresiaPorCodigo(codigo)`, `canjesHoy`, `clientesAdmin(...)` | Solo admin |
| Mutation | `contratarMembresia`, `iniciarPagoMembresia`, `confirmarPagoMembresia`, `cancelarMiMembresia` | Con sesión |
| Mutation | `confirmarPagoMembresiaManual`, `cancelarMembresia`, `canjearMembresia`, `crearPlan`, `actualizarPlan` | Solo admin |
| Subscription | `eventosAdmin` | Solo admin |
| Subscription | `seguirPedido(id)`, `seguirMembresia(id)` | Dueño o admin |

Además, `GET /imagenes/<id>` sirve las fotos subidas, `POST /webhooks/mercadopago` recibe los avisos de Mercado Pago (opcional), `POST /mcp` es el servidor MCP, `POST /tareas/recompras` genera las recompras (pide `X-Cron-Secret`) y `GET /salud` revisa las dos bases.

Para probar las operaciones con sesión en GraphiQL, primero corre
`iniciarSesion`, copia el `token` y agrégalo en la pestaña *Headers*:
`{ "Authorization": "Bearer <token>" }`.

Ejemplo:

```graphql
mutation {
  registrarPedido(input: {
    items: [{ productoId: 1, cantidad: 2, variante: "Molido para espresso" }]
    metodoPago: "transferencia"
    entrega: { tipo: "recoger" }
  }) {
    id subtotal costoEnvio total estado referencia
    items { nombre variante cantidad precioUnit subtotal }
    pago { metodoNombre estado instrucciones { etiqueta valor } }
  }
}
```

`registrarPedido` es el checkout: valida stock y variante, calcula el total con
el precio vigente más el envío firmado, descuenta stock en MongoDB y guarda el
pedido en PostgreSQL en una sola transacción (pedido, renglones, pago, envío y,
si se pidió, la suscripción de recompra). El descuento usa una
actualización condicional atómica (`{stock: {$gte: cantidad}}` + `$inc`), así
dos compras simultáneas no venden el mismo stock; si algún producto falla, se
regresa lo que ya se había descontado. `eliminarProducto` no deja borrar un
producto que ya aparece en pedidos.

### Bases de datos

**PostgreSQL** (`back/sql/001_inicial.sql`): `usuarios`, `pedidos`,
`pedido_items`, `pagos` (1 a 1 con el pedido), `envios`, `suscripciones`,
`suscripcion_items` y `correos`, con llaves foráneas, `CHECK` (estados,
montos, CP de 5 dígitos, `total = subtotal + envio`), `UNIQUE` en el correo e
índices para el panel. El renglón del pedido guarda el **nombre, la variante y
el precio** con los que se vendió.

**MongoDB:**

| Colección | Documento |
|---|---|
| `categorias` | `{ _id, nombre, descripcion, imagen_url }` |
| `productos` | `{ _id, nombre, descripcion, precio, stock, imagen_url, imagenes: [..], categoria_id, variante_nombre, variantes: [..], metodos: [..], peso_kg }` |
| `imagenes` | `{ _id: "<hex>", tipo, datos (binario), bytes, creada, admin_id }` — fotos subidas desde el panel |
| `planes` | `{ _id, nombre, descripcion, precio, incluye: [..], opciones: [..], activo, orden }` |
| `membresias` | `{ _id, usuario_id, plan_id, estado, precio, creada, inicio, fin, pago: {…}, canjes: [ { dia, fecha, opcion, nota, admin_id } ] }` |
| `contadores` | `{ _id: "<colección>", valor }` — ids consecutivos |

Decisiones de modelado:

- **Lo transaccional en PostgreSQL.** Un pedido toca cuatro tablas y debe
  quedar completo o no quedar; las restricciones de SQL protegen los datos aunque
  haya un error en el código. Los cambios de un pedido bloquean su renglón
  (`SELECT … FOR UPDATE`) para que dos avisos de pago no choquen.
- **El catálogo en MongoDB.** Cada producto tiene campos distintos (variantes,
  galería, métodos) y se lee completo; el stock se descuenta con una
  actualización condicional atómica (`{stock: {$gte: n}}` + `$inc`).
- **Entre las dos bases** no hay transacción: si el pedido falla en Postgres,
  el stock descontado en Mongo se regresa (compensación).
- **Variantes sin duplicar productos:** la molienda comparte precio y stock y
  se guarda en el renglón del pedido.
- **Validación `$jsonSchema`** en cada colección e **índices** en
  `categoria_id` y `metodos`.

## APIs de terceros

| # | API | Uso en la tienda | Modo sin llave |
|---|---|---|---|
| 1 | **Mercado Pago** (Checkout Pro) | Cobro con tarjeta, OXXO o saldo | Pasarela simulada |
| 2 | **PayPal** (Orders v2) | Cobro con cuenta PayPal | Pasarela simulada |
| 3 | **Envia.com** (`/ship/rate`, `/ship/generate`, `/ship/generaltrack`) | Cotizar envío, generar guía y rastrear | Tabla de precios local y guías `SIM…` |
| 4 | **Envia Geocodes** | Estado, ciudad y colonias por código postal | Siempre real (API pública) |
| 5 | **Brevo** (`/v3/smtp/email`) | Correos transaccionales | Se anotan en la bitácora como "simulado" |
| 6 | **OpenFreeMap + MapLibre** | Mapa interactivo del local | Siempre real (sin API key) |

Todas se llaman desde el backend con las llaves en variables de entorno, salvo
el mapa, que se carga en el navegador. Si falta una llave o la API falla, esa
parte sigue funcionando en modo simulado. El panel muestra el estado de cada
una en **Integraciones**.

### Variables de entorno en producción

Todas están explicadas en `back/.env.example`:

| Variable | Dónde | Para qué |
|---|---|---|
| `DATABASE_URL` | Render | PostgreSQL (Neon, con `sslmode=require`) |
| `MONGO_URI`, `MONGO_DB` | Render | MongoDB Atlas |
| `JWT_SECRET` | Render | Firma de sesiones, códigos de canje y cotizaciones |
| `TZ=America/Mexico_City` | Render | El "día" de membresías y recompras |
| `CORS_ORIGENES` | Render | Dominio del front publicado |
| `PAGOS_MODO`, `MP_*`, `PAYPAL_*` | Render | Pasarelas de pago |
| `ENVIA_TOKEN`, `ENVIA_API` | Render | Envíos |
| `BREVO_API_KEY`, `BREVO_REMITENTE`, `CORREO_TIENDA` | Render | Correos |
| `CRON_SECRET` | Render + GitHub Secret | `POST /tareas/recompras` |
| `PUBLIC_API_URL` | Front + GitHub Variable | URL del backend para el front |

Ningún secreto está en el código ni en el repositorio (`.env` está en `.gitignore`).

## Envíos a domicilio (Envia.com)

- Al escribir el código postal, `buscarCodigoPostal` llena estado, ciudad y
  colonias (Envia Geocodes, API pública).
- `cotizarEnvio` pide precios a Estafeta, FedEx y DHL (`/ship/rate/`) con el
  peso real del carrito. Cada opción viaja con una **firma HMAC**; al
  registrar el pedido se verifica que no la hayan alterado, que no haya
  expirado (30 min) y que sea del mismo CP y peso.
- Al marcar el pedido como enviado se genera la guía (`/ship/generate/`) y el
  cliente puede rastrearlo (`/ship/generaltrack/`).
- Sin `ENVIA_TOKEN` trabaja en modo simulado (tabla de precios por zona y guías `SIM…`).

## Correos automáticos (Brevo)

Bienvenida, aviso de pedido nuevo a la tienda, pago confirmado, pedido enviado
(con guía), membresía activada y recompra lista. Se mandan en segundo plano y
cada uno queda en la tabla `correos` (el admin los ve en **Integraciones**).
Sin `BREVO_API_KEY` se anotan como "simulado".

## Recompra automática

En el checkout, "Repetir este pedido" cada 15, 30 o 60 días crea una
suscripción. El backend revisa cada hora (y un cron diario de GitHub Actions
llama a `POST /tareas/recompras`) qué suscripciones ya vencieron, genera el
pedido con los mismos productos y entrega, y le manda al cliente el enlace para
pagarlo. No se guardan tarjetas. `FOR UPDATE SKIP LOCKED` evita pedidos dobles.
El cliente pausa, cambia la frecuencia o cancela desde **Mi cuenta**.

## Servidor MCP (agentes de IA)

`POST /mcp` (Streamable HTTP). Herramientas públicas: `buscar_productos`,
`ver_producto`, `listar_categorias`, `metodos_de_preparacion`, `cotizar_envio`.
Con `Authorization: Bearer <token de admin>`: `estado_de_pedido`,
`resumen_de_ventas`, `productos_con_poco_stock`, `pedidos_por_cobrar`.
Para probarlo: `npx @modelcontextprotocol/inspector` y la URL
`http://localhost:8000/mcp`.

## CI/CD

`.github/workflows/ci.yml` corre en cada push y pull request:

1. **Backend:** `ruff check .` y `pytest` (42 pruebas) contra PostgreSQL y
   MongoDB reales levantados por el workflow.
2. **Frontend:** `npm run lint` (ESLint), `npm test` (Vitest) y `npm run build`.
3. **Despliegue** (solo en `main` y si todo pasó): deploy hook de Render y
   build hook de Netlify (`RENDER_DEPLOY_HOOK_URL`, `NETLIFY_BUILD_HOOK_URL` en
   GitHub Secrets). Sin ellos, Render puede desplegar solo con
   *Auto-Deploy → After CI checks pass*.

`.github/workflows/recompras.yml` corre a diario las recompras (necesita
`vars.BACKEND_URL` y `secrets.CRON_SECRET`).

## Fotos de productos

Cada producto tiene una **galería de hasta 6 fotos** (`imagenes`); la primera
es la principal y también queda en `imagen_url`. Las categorías tienen una.

- **Catálogo:** tarjetas con foto (carga diferida y fundido suave), galería
  con miniaturas en el detalle y miniatura en el carrito. Si un producto no
  tiene foto o falla la URL, se ve el icono de su categoría como antes.
- **Panel → Productos → Nuevo / Editar:** sección *Fotos* para **elegir o
  arrastrar** imágenes (JPG, PNG o WebP), elegir la principal y quitar fotos.
  Antes de subirlas, el navegador las reduce a 1400 px y las pasa a WebP
  (una foto de celular de 5 MB queda en ~150–300 KB).
- **Backend:** `subirImagen(datos)` (solo admin) guarda la foto en la
  colección `imagenes` de MongoDB y regresa `/imagenes/<id>`, que sirve
  `GET /imagenes/<id>` con caché de un año. Se revisa el tipo real por los
  primeros bytes del archivo (JPG/PNG/WebP, máx. 3 MB; SVG no, porque puede
  traer JavaScript) y `crear/actualizarProducto` solo aceptan fotos subidas
  aquí o URLs `https://`.
- **Fotos de ejemplo:** de [Unsplash](https://unsplash.com) (licencia
  gratuita), en `datos_ejemplo.json`. Si tu base es de una entrega anterior,
  al arrancar el backend se las pone solo a los productos que no tenían foto.

> En Netlify las fotos de Unsplash se ven siempre; las que subas desde el
> panel necesitan que el backend esté publicado (las sirve él).

## Ubicación del local (mapa)

Al final del inicio está la sección **Visítanos** (`/#ubicacion`) con la
dirección de **Frecuente Café Bar GDL** (C. Justo Sierra 2665, Arcos
Vallarta, 44650 Guadalajara, Jal.) y un mapa interactivo. El pie de página
también enlaza a esa sección.

| Pieza | Qué hace |
|---|---|
| `components/Ubicacion.astro` | Tarjeta estática (HTML sin JS): dirección, "Cómo llegar" (Google Maps), "Abrir en Waze" y "Copiar dirección" |
| `components/islas/MapaLocal.jsx` | Isla con `client:visible`: el JS del mapa solo se descarga cuando la sección entra en pantalla |
| `lib/local.js` | Nombre, dirección, coordenadas y enlaces del local en un solo lugar |

API de mapas **gratuita y sin API key**: [MapLibre GL JS](https://maplibre.org)
(librería de código abierto) con los mapas vectoriales de
[OpenFreeMap](https://openfreemap.org) (datos de OpenStreetMap, sin registro
ni límite de visitas). Como el mapa es vectorial, se pinta con la paleta del
manual (Crema, Espresso, Tostado, Hoja), con edificios en 3D al acercarse, y
cambia solo entre modo claro y oscuro. La rueda del mouse no "atrapa" la
página: el zoom es con Ctrl + rueda (dos dedos en el celular).

> Las coordenadas salen de los números de casa de OpenStreetMap; los botones
> de "Cómo llegar" buscan el lugar por nombre y dirección.

## Temas del curso aplicados (10 de 15)

Componentes · Hooks (`useState`, `useEffect`, hook propio `useGraphQLQuery`) ·
Eventos · Fetching real contra el backend · Keys · Fragment · Estilos propios ·
Zustand (ahora con `persist`) · Skeletons · Portales. Además: **GraphQL
Subscriptions por WebSocket** (con un cliente del protocolo hecho a mano y
un hook propio `useSuscripcion`), y el front corre
sobre **Astro** con arquitectura de islas y rutas por archivo, y hay inicio
de sesión con JWT y formularios controlados con validación.

## Pendiente para la siguiente etapa

Cobro recurrente automático con tarjeta guardada, facturación electrónica
(CFDI), cupones de descuento y fotografía propia del local (por ahora son
fotos libres de Unsplash).
