# Diseño — brief, wireframes, mockups y prototipo

## 1. Brief
| Punto | Definición |
|---|---|
| Cliente | Frecuente Café Bar · C. Justo Sierra 2665, Arcos Vallarta, Guadalajara |
| Proyecto | Tienda en línea complementaria al local |
| Objetivo | Vender café de especialidad, leches, matcha y accesorios para preparar en casa, con recompra y envío |
| Público | Clientes del local, entusiastas del café (22–45 años), oficinas |
| Mensaje | "Tu café de cada día, también en casa" — cercano, artesanal, sin pretensión |
| Tono | Cálido, directo, en español de México, tuteo |
| Identidad | *Manual de Identidad Digital — Café Frecuente v1.0* (`front/src/styles/theme.css`) |
| Colores | Espresso `#3E2A20`, Crema `#F3E5D4`, Tostado `#8B5E3C`, Hoja `#4F7A52` (+ modo oscuro) |
| Tipografía | Títulos con personalidad y texto de lectura cómoda, definidos como tokens del manual |
| Restricciones | Accesible (contraste AA, foco visible, estados con texto), responsivo desde 360 px, rápido en móvil |
| Entregables | Wireframes, mockups (sitio en alta fidelidad), prototipo navegable (el sitio desplegado) |

## 2. Wireframes (baja fidelidad)

### Inicio
```
┌──────────────────────────────────────────────────────────┐
│ ☕ Frecuente      Inicio  Tienda  Membresías   👤  🛒 2   │
├──────────────────────────────────────────────────────────┤
│  [ Hero: foto de café · "Tu café de cada día" · CTA ]    │
├────────────┬─────────────────────────────────────────────┤
│ Categorías │  Compra por categoría                        │
│ · Café     │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐         │
│ · Leches   │  │ foto │ │ foto │ │ foto │ │ foto │         │
│ · Matcha   │  │ Café │ │Leches│ │Matcha│ │Acces.│         │
│ · Acces.   │  └──────┘ └──────┘ └──────┘ └──────┘         │
│            │  ¿Cómo lo preparas?                          │
│            │  (Espresso)(V60)(Prensa)(Goteo)(Frío) Tienda→│
├────────────┴─────────────────────────────────────────────┤
│  Visítanos: dirección · Cómo llegar · Waze │ [ MAPA ]    │
└──────────────────────────────────────────────────────────┘
```

### Tienda
```
┌──────────────────────────────────────────────────────────┐
│ Tienda                                                    │
│ [ Buscar: Etiopía, avena…          ] [ Categoría ▾ ]      │
│ (Todos)(Espresso)(V60)(●Prensa)(Goteo)(Frío)(Matcha)       │
│ 4 productos · Quitar filtros                              │
│ ┌────────┐ ┌────────┐ ┌────────┐                          │
│ │  foto  │ │  foto  │ │  foto  │                          │
│ │ Nombre │ │ Nombre │ │ Nombre │                          │
│ │ $185   │ │ $260   │ │ $420   │                          │
│ │[Detalle]││[Detalle]││[Detalle]│                         │
│ └────────┘ └────────┘ └────────┘                          │
└──────────────────────────────────────────────────────────┘
```

### Detalle de producto (modal)
```
┌───────────────────────────────────────────── ✕ ┐
│ Etiopía Yirgacheffe 250 g                       │
│ ┌─────────────┐  Lavado, floral y cítrico.      │
│ │    foto     │  Ideal para: (V60)(Prensa)      │
│ └─────────────┘  $260.00   [8 disponibles]      │
│ [▫][▫]           Molienda:                      │
│                  (●Grano)(Espresso)(V60)(Prensa)│
│                  Cantidad [-] 1 [+]             │
│                  [Agregar al carrito][Comprar]  │
└─────────────────────────────────────────────────┘
```

### Checkout
```
┌─────────────────────────────┬──────────────────────────┐
│ Entrega                     │ Tu pedido                │
│ ( ) Recoger en el local     │ Etiopía · V60     2 $520 │
│ (●) Envío a domicilio       │ Productos           $520 │
│  CP [44160] Guadalajara,Jal │ Envío               $119 │
│  Estado[Jalisco▾] Ciudad[ ] │ Total               $639 │
│  Colonia[▾] Calle[ ] Núm[ ] │ [ Pagar $639 ]           │
│  Paquetería:                │                          │
│  (●) Estafeta 2-3 días $119 │                          │
│  ( ) FedEx    1-2 días $165 │                          │
│ Método de pago              │                          │
│  (●) Mercado Pago ( ) PayPal│                          │
│ Recompra automática         │                          │
│  [✓] Repetir cada [mes ▾]   │                          │
└─────────────────────────────┴──────────────────────────┘
```

### Panel de administración
```
┌──────────────┬───────────────────────────────────────────┐
│ Panel        │ Resumen (últimos 30 días)                 │
│ ● En vivo    │ [Ventas $] [Pedidos] [Ticket] [Por cobrar]│
│ Resumen      │ ┌ gráfica de ventas por día ─────────────┐│
│ Pedidos      │ └─────────────────────────────────────────┘│
│ Caja         │ Más vendidos        │ Stock bajo           │
│ Membresías   │ 1. Prensa 20 pzs    │ Prensa francesa 9    │
│ Recompras    │ 2. Matcha 15 pzs    │                      │
│ Clientes     │                                            │
│ Productos    │                                            │
│ Integraciones│                                            │
└──────────────┴───────────────────────────────────────────┘
```

## 3. Mockups (alta fidelidad)
Los mockups son las pantallas del sitio con la identidad del manual aplicada. Se ven en
el sitio desplegado y en modo claro/oscuro (respeta la preferencia del sistema):

| Pantalla | Ruta |
|---|---|
| Inicio con categorías, métodos y mapa del local | `/` |
| Tienda con buscador y filtros | `/tienda` |
| Detalle con galería y molienda | `/tienda` → "Ver detalle" |
| Checkout con envío y recompra | `/checkout` |
| Pedido con rastreo | `/pedido?id=N` |
| Mi cuenta con recompras | `/cuenta` |
| Panel: resumen, pedidos, recompras, integraciones | `/admin`, `/admin/pedidos`, `/admin/recompras`, `/admin/integraciones` |

Componentes del sistema de diseño (en `global.css`): botones (primario, secundario,
peligro), tarjetas de producto, chips de filtro/variante, insignias de estado (siempre con
texto), alertas, paneles, tablas, skeletons de carga y modal.

## 4. Prototipo
El **prototipo navegable** es el propio sitio: el front publicado en Netlify con el
backend en Render. Con los modos simulados (pagos, envíos y correos) se puede recorrer
el flujo completo sin cuentas reales:

1. Cuenta de cliente de prueba: `demo@frecuente.mx` / `cafe1234`.
2. Cuenta de administrador de prueba: `admin@frecuente.mx` / `admin1234`.
3. Pasarela simulada con tarjetas de prueba (aprobada, rechazada, pendiente).

## 5. Decisiones de UX
- **Molienda como chips**, no como lista desplegable: se ven todas las opciones de un vistazo.
- **Código postal primero**: llena estado, ciudad y colonias y evita errores de dirección.
- **La paquetería más barata queda elegida** y el total se actualiza al momento.
- **El carrito no se vacía hasta que el pago se aprueba**: si el pago falla, no se pierde nada.
- **Recompra opcional en el checkout**, no un flujo aparte: se ofrece cuando el cliente ya decidió comprar.
- **Estados con palabra y color** (nunca solo color) para accesibilidad.
