# Mapas del proyecto

Los diagramas están en Mermaid: GitHub los dibuja solos al abrir este archivo.

## 1. Mapa del sitio
```mermaid
flowchart TD
  I["/ Inicio<br/>categorías, métodos, mapa del local"] --> T["/tienda<br/>buscador y filtros"]
  I --> C["/categoria?id=N"]
  T --> M(["Modal de producto<br/>galería y molienda"])
  C --> M
  M --> K["/carrito"]
  K --> CH["/checkout<br/>entrega · pago · recompra"]
  CH --> L["/login · /registro"]
  CH --> PS["/pago/simulado<br/>o Mercado Pago / PayPal"]
  PS --> R["/pago/resultado"]
  R --> P["/pedido?id=N<br/>estado y rastreo"]
  I --> MB["/membresias"] --> MM["/mi-membresia<br/>código del día"]
  I --> CU["/cuenta<br/>pedidos y recompras"]
  CU --> P
  subgraph Panel ["/admin (solo administradores)"]
    A0["Resumen"] --- A1["Pedidos"] --- A2["Caja"] --- A3["Membresías"]
    A3 --- A4["Recompras"] --- A5["Clientes"] --- A6["Productos"] --- A7["Integraciones"]
  end
  CU -. rol admin .-> A0
```

## 2. Flujo de navegación de una compra (experiencia del cliente)
```mermaid
journey
  title Mariana compra café para su V60
  section Descubrir
    Entra a Tienda y elige "V60 / Chemex": 5: Cliente
    Abre Etiopía y elige "Molido para V60": 5: Cliente
  section Comprar
    Revisa su carrito: 4: Cliente
    Inicia sesión: 3: Cliente
    Escribe su CP y elige paquetería: 4: Cliente
    Marca "Repetir cada mes": 5: Cliente
  section Pagar y recibir
    Paga con Mercado Pago: 4: Cliente
    Recibe correo de confirmación: 5: Cliente
    Recibe correo con la guía y rastrea: 5: Cliente
```

## 3. Proceso de compra (sistema)
```mermaid
sequenceDiagram
  autonumber
  actor C as Cliente
  participant F as Front (Astro + React)
  participant B as Backend (GraphQL)
  participant E as Envia.com
  participant M as MongoDB
  participant P as PostgreSQL
  participant G as Mercado Pago / PayPal
  participant R as Brevo
  C->>F: Escribe su código postal
  F->>B: buscarCodigoPostal / cotizarEnvio
  B->>E: geocodes + /ship/rate (por paquetería)
  E-->>B: precios
  B-->>F: opciones con FIRMA (HMAC)
  C->>F: Confirmar pedido
  F->>B: registrarPedido(items, entrega + firma, método, recompra)
  B->>B: verifica firma, CP y peso
  B->>M: descuenta stock ($gte + $inc, atómico)
  B->>P: TRANSACCIÓN: pedido + renglones + pago + envío (+ suscripción)
  B->>R: aviso a la tienda
  F->>B: iniciarPago
  B->>G: crea preferencia / orden
  C->>G: paga
  G-->>F: regresa con payment_id / token
  F->>B: confirmarPago
  B->>G: consulta el pago (no le cree al navegador)
  B->>P: pago aprobado → pedido "pagado" (FOR UPDATE, idempotente)
  B->>R: correo "Recibimos tu pago"
```

## 4. Ciclo de vida del pedido
```mermaid
stateDiagram-v2
  [*] --> registrado: registrarPedido
  registrado --> pagado: pago aprobado / transferencia confirmada
  registrado --> entregado: efectivo cobrado al recoger
  registrado --> cancelado: cliente o tienda (stock regresa)
  pagado --> enviado: tienda envía (genera guía en Envia.com)
  pagado --> entregado: recogido en el local
  pagado --> cancelado: pago queda "por reembolsar"
  enviado --> entregado
  entregado --> [*]
  cancelado --> [*]
```

## 5. Proceso de recompra
```mermaid
flowchart LR
  A["Checkout con<br/>'Repetir cada 30 días'"] --> B[("suscripciones<br/>PostgreSQL")]
  T["Cada hora (backend)<br/>o cron diario (GitHub Actions)"] --> C{"¿proxima <= hoy?<br/>FOR UPDATE SKIP LOCKED"}
  B --> C
  C -- sí, hay stock --> D["Crea el pedido<br/>(mismos productos y entrega)"] --> E["Correo con enlace<br/>para pagar (Brevo)"] --> F["proxima += 30 días"]
  C -- sin stock --> G["Correo 'no pudimos'<br/>reintenta mañana"]
  C -- pausada / cancelada --> H["No hace nada"]
```

## 6. Arquitectura y despliegue
```mermaid
flowchart LR
  U["Navegador"] -->|HTML estático| N["Netlify<br/>front Astro"]
  U -->|GraphQL HTTP + WebSocket| R["Render<br/>FastAPI + Strawberry"]
  IA["Agente de IA"] -->|MCP /mcp| R
  R --> PG[("Neon<br/>PostgreSQL")]
  R --> MG[("MongoDB Atlas")]
  R --> MP["Mercado Pago"]
  R --> PP["PayPal"]
  R --> EN["Envia.com"]
  R --> BR["Brevo"]
  U --> OFM["OpenFreeMap<br/>mapa"]
  GH["GitHub"] -->|push| GA["GitHub Actions<br/>lint · pruebas · build"]
  GA -->|deploy hook| R
  GA -->|build hook| N
```

## 7. Modelo de datos relacional (PostgreSQL)
```mermaid
erDiagram
  usuarios ||--o{ pedidos : hace
  usuarios ||--o{ suscripciones : programa
  suscripciones ||--o{ suscripcion_items : contiene
  suscripciones ||--o{ pedidos : genera
  pedidos ||--|{ pedido_items : tiene
  pedidos ||--|| pagos : "se cobra con"
  pedidos ||--o| envios : "se entrega con"
  pedidos ||--o{ correos : "notifica"
  usuarios {
    int id PK
    text email UK
    text rol
    bool activo
  }
  pedidos {
    int id PK
    int usuario_id FK
    text estado
    numeric subtotal
    numeric envio
    numeric total
  }
  pedido_items {
    int id PK
    int pedido_id FK
    int producto_id "MongoDB"
    text variante
    int cantidad
  }
  pagos {
    int pedido_id PK
    text metodo
    text estado
  }
  envios {
    int pedido_id PK
    text tipo
    text cp
    text guia
  }
  suscripciones {
    int id PK
    int cada_dias
    date proxima
  }
```
El catálogo y las membresías viven en MongoDB (ver `back/database.py`); se unen por id
(`pedido_items.producto_id` → producto, `membresias.usuario_id` → `usuarios.id`).
