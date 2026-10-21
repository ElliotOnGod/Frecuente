# Frecuente — e-commerce (avance 4: backoffice completo en vivo con GraphQL Subscriptions + membresías)

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

---

## Cómo correrlo

Se levantan **dos procesos**: el backend en el puerto 8000 y el front (Astro) en el 4321.

### 1. Base de datos (MongoDB)

Necesitas un MongoDB corriendo. Tienes dos opciones:

- **Local:** instala MongoDB Community Server como servicio. En Windows, desde
  una PowerShell como administrador: `winget install MongoDB.Server` (y,
  opcional, `winget install MongoDB.Compass.Full` para ver los datos).
  Revisa que esté corriendo con `Get-Service MongoDB` (debe decir `Running`).
  Queda en `mongodb://localhost:27017` y no hay que configurar nada más.
- **En la nube:** crea un clúster gratis en MongoDB Atlas, copia su cadena de
  conexión y ponla en `back/.env` (ver abajo).

No hace falta crear nada a mano: el backend crea la base `frecuente`, sus
colecciones, validadores e índices la primera vez que arranca, y carga
`datos_ejemplo.json`.

### 2. Backend (FastAPI + Strawberry + MongoDB)

```bash
cd back
python -m venv .venv
source .venv/bin/activate          # Windows (PowerShell): .\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

> El zip **no trae** `back/.venv` ni `front/node_modules`: se crean en cada
> computadora con los comandos de arriba y `npm install`. Si copias el
> proyecto de otra PC con esas carpetas, bórralas primero (si no, salen
> errores como *"Unable to create process"* o
> *"SyntaxError: Invalid or unexpected token env.mjs"*). En Windows:
> `Remove-Item -Recurse -Force .venv` y `Remove-Item -Recurse -Force node_modules`.

Si tu MongoDB no está en `localhost:27017` (por ejemplo, si usas Atlas),
copia `.env.example` a `.env` y cambia `MONGO_URI`.

La primera vez verás `Base 'frecuente' creada en MongoDB desde
datos_ejemplo.json`, con 4 categorías, 9 productos, cuentas de prueba y
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
├── back/
│   ├── main.py             FastAPI, CORS y router de GraphQL
│   ├── schema.py           Tipos, Query y Mutation (Strawberry)
│   ├── database.py         Conexión a MongoDB (PyMongo), validadores e init_db()
│   ├── auth.py             Hash de contraseñas (PBKDF2) y tokens de sesión (JWT)
│   ├── pagos.py            Métodos de cobro: Mercado Pago, PayPal, transferencia, efectivo
│   ├── eventos.py          Pub/sub en memoria que alimenta las Subscriptions (tiempo real)
│   ├── .env.example        Datos de conexión (copiar a .env)
│   └── requirements.txt
├── front/                  Astro
│   ├── astro.config.mjs    Integración de React
│   ├── public/             favicon y archivos estáticos
│   └── src/
│       ├── layouts/BaseLayout.astro    TopBar + página + Footer + modal
│       ├── layouts/AdminLayout.astro   BaseLayout + menú lateral + conexión en vivo
│       ├── pages/                      Una página por vista (rutas reales)
│       │   ├── index.astro             /
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
│       │   ├── admin/clientes.astro    /admin/clientes (compras y membresía por cliente)
│       │   ├── membresias.astro        /membresias (planes y contratación)
│       │   ├── mi-membresia.astro      /mi-membresia (código del día en vivo, canjes)
│       │   ├── login.astro             /login?siguiente=/ruta
│       │   ├── registro.astro          /registro?siguiente=/ruta
│       │   ├── cuenta.astro            /cuenta (datos y mis pedidos)
│       │   └── 404.astro
│       ├── components/                 Componentes estáticos (.astro):
│       │   │                           TopBar, Hero, ContextSection, Footer
│       │   └── islas/                  Componentes interactivos (React):
│       │                               CatalogoHome, Sidebar, CategoryGrid,
│       │                               CategoryDetail, ProductCard,
│       │                               ProductDetailModal, Cart, Checkout,
│       │                               OrderSuccess, CartButton, Skeleton,
│       │                               LoginForm, RegistroForm, SessionMenu,
│       │                               Cuenta, Insignia, PasarelaSimulada,
│       │                               ResultadoPago, Planes, MiMembresia
│       │                               admin/: SoloAdmin, AdminResumen,
│       │                               AdminPedidos, AdminProductos, Graficas,
│       │                               AvisosEnVivo, AdminCaja, AdminMembresias,
│       │                               AdminClientes
│       ├── store/useStore.js           Zustand: sesión, carrito, pedido y modal
│       ├── store/enVivo.js             Zustand: avisos en vivo del backoffice
│       ├── lib/graphql.js              Cliente GraphQL sobre fetch
│       ├── lib/formato.js              Iconos, formato de pesos, rutas y estados
│       ├── lib/pagos.js                Consultas y acciones de cobro compartidas
│       ├── lib/membresias.js           Consultas y acciones de membresía
│       ├── lib/subscripciones.js       Cliente WebSocket propio (graphql-transport-ws)
│       ├── hooks/useGraphQLQuery.js    Hook propio de fetching (con `recarga`)
│       ├── hooks/useSuscripcion.js     Hook propio para Subscriptions
│       ├── hooks/useRecargaEnVivo.js   Recarga una consulta cuando llega un aviso
│       ├── hooks/usePedidoPendiente.js Pedido sin pagar del carrito (lo sincroniza con el servidor)
│       └── styles/                     theme.css (manual) + global.css
└── docs/                   UML de componentes (Astro + islas) y de entidades
                            (colecciones de MongoDB), en SVG
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
  para redirigir a otro sitio.

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
| Query | `categorias`, `categoria(id)`, `productos(categoriaId)`, `producto(id)`, `metodosPago` | Público |
| Query | `yo`, `misPedidos`, `pedido(id)` | Con sesión (un cliente solo ve sus pedidos) |
| Query | `resumenAdmin(dias)`, `pedidosAdmin(estado, metodo, buscar, limite, salto)` | Solo admin |
| Mutation | `registrarUsuario`, `iniciarSesion` | Público |
| Mutation | `registrarPedido`, `iniciarPago`, `confirmarPago`, `cancelarMiPedido` | Con sesión |
| Mutation | `crearProducto`, `actualizarProducto`, `eliminarProducto`, `cambiarEstadoPedido`, `marcarReembolsado` | Solo admin |
| Query | `planes` | Público (`incluirInactivos` solo admin) |
| Query | `miMembresia`, `misMembresias`, `membresia(id)` | Con sesión |
| Query | `resumenMembresias`, `membresiasAdmin(...)`, `membresiaPorCodigo(codigo)`, `canjesHoy`, `clientesAdmin(...)` | Solo admin |
| Mutation | `contratarMembresia`, `iniciarPagoMembresia`, `confirmarPagoMembresia`, `cancelarMiMembresia` | Con sesión |
| Mutation | `confirmarPagoMembresiaManual`, `cancelarMembresia`, `canjearMembresia`, `crearPlan`, `actualizarPlan` | Solo admin |
| Subscription | `eventosAdmin` | Solo admin |
| Subscription | `seguirPedido(id)`, `seguirMembresia(id)` | Dueño o admin |

Además, `POST /webhooks/mercadopago` recibe los avisos de Mercado Pago (opcional).

Para probar las operaciones con sesión en GraphiQL, primero corre
`iniciarSesion`, copia el `token` y agrégalo en la pestaña *Headers*:
`{ "Authorization": "Bearer <token>" }`.

Ejemplo:

```graphql
mutation {
  registrarPedido(input: { items: [{ productoId: 1, cantidad: 2 }], metodoPago: "transferencia" }) {
    id total estado referencia
    items { cantidad precioUnit subtotal producto { nombre } }
    pago { metodoNombre estado instrucciones { etiqueta valor } }
  }
}
```

`registrarPedido` es el checkout: valida stock, calcula el total con el precio
vigente, descuenta stock y guarda el pedido. El descuento usa una
actualización condicional atómica (`{stock: {$gte: cantidad}}` + `$inc`), así
dos compras simultáneas no venden el mismo stock; si algún producto falla, se
regresa lo que ya se había descontado. `eliminarProducto` no deja borrar un
producto que ya aparece en pedidos.

### Base de datos (MongoDB)

| Colección | Documento |
|---|---|
| `categorias` | `{ _id, nombre, descripcion, imagen_url }` |
| `productos` | `{ _id, nombre, descripcion, precio, stock, imagen_url, categoria_id }` |
| `usuarios` | `{ _id, nombre, email, telefono, rol, password_hash, creado }` |
| `pedidos` | `{ _id, usuario_id, fecha, estado, total, items: [ { producto_id, cantidad, precio_unit } ], pago: { metodo, estado, modo, referencia, proveedor_id, pago_id, detalle, intentos, fecha_pago, actualizado } }` |
| `planes` | `{ _id, nombre, descripcion, precio, incluye: [..], opciones: [..], activo, orden }` |
| `membresias` | `{ _id, usuario_id, plan_id, estado, precio, creada, inicio, fin, pago: {…}, canjes: [ { dia, fecha, opcion, nota, admin_id } ] }` |
| `contadores` | `{ _id: "<colección>", valor }` — ids consecutivos |

Decisiones de modelado:

- **Items embebidos en el pedido.** Siempre se leen junto con su pedido y no
  existen solos, así que van dentro del mismo documento (en SQL era la tabla
  `pedido_item`). Guardan `precio_unit` para que el pedido conserve el precio
  con el que se vendió aunque el producto cambie después.
- **Categoría y usuario por referencia** (`categoria_id`, `usuario_id`): un
  producto se consulta por separado y un usuario acumula muchos pedidos.
- **Ids enteros** con la colección `contadores` (como `AUTO_INCREMENT`), para
  que la API y el front sigan usando 1, 2, 3… en lugar de `ObjectId`.
- **Pago embebido en el pedido.** Un pedido tiene un solo cobro y siempre se
  muestra con él. Es opcional en el validador para que los pedidos de la
  entrega anterior sigan siendo válidos (en la API salen con `pago: null`).
- **Validación `$jsonSchema`** en cada colección (campos obligatorios, tipos,
  precio y stock ≥ 0, estados permitidos) e **índices** en `categoria_id`,
  `usuario_id`, `items.producto_id` y `email` (único).

## Temas del curso aplicados (10 de 15)

Componentes · Hooks (`useState`, `useEffect`, hook propio `useGraphQLQuery`) ·
Eventos · Fetching real contra el backend · Keys · Fragment · Estilos propios ·
Zustand (ahora con `persist`) · Skeletons · Portales. Además: **GraphQL
Subscriptions por WebSocket** (con un cliente del protocolo hecho a mano y
un hook propio `useSuscripcion`), y el front corre
sobre **Astro** con arquitectura de islas y rutas por archivo, y hay inicio
de sesión con JWT y formularios controlados con validación.

## Pendiente para la siguiente entrega

Rediseño visual más profesional, renovación automática de membresías
(cobro recurrente), dirección de envío en el checkout y fotos reales del
catálogo — por ahora cada producto muestra
un placeholder con el icono de su categoría.
