# Análisis FODA — Frecuente en línea

## Fortalezas (internas)
- **Marca y clientela existentes:** el local ya tiene clientes frecuentes que confían en su
  café; la tienda no parte de cero.
- **Producto de especialidad:** grano de origen, blends propios y asesoría por método de
  preparación, algo que un supermercado no ofrece.
- **Molienda a la medida:** cada café se vende en grano o molido para el método del cliente
  (espresso, V60, prensa, goteo) sin duplicar productos.
- **Recompra automática:** el cliente programa su pedido cada 15, 30 o 60 días; ingresos
  recurrentes y previsibles.
- **Omnicanal:** recoger en el local sin costo o envío a todo México; membresías para el
  consumo diario en el local.
- **Tecnología propia y sin comisiones de plataforma:** stack moderno (Astro, React,
  GraphQL, PostgreSQL, MongoDB) y despliegue en servicios con planes gratuitos.
- **Operación ordenada:** panel con ventas, stock bajo, cobros pendientes, guías de envío y
  avisos en tiempo real.

## Oportunidades (externas)
- **Crecimiento del café de especialidad en México** y del consumo en casa después de la
  pandemia.
- **Adopción de pagos digitales** (Mercado Pago, PayPal, SPEI, OXXO) entre compradores
  mexicanos.
- **Paqueterías con API** (Envia.com) que permiten cotizar y generar guías sin contratos
  grandes.
- **Venta a oficinas (B2B):** pedidos recurrentes de volumen con la misma recompra.
- **Agentes de IA:** el servidor MCP permite que asistentes recomienden y consulten la
  tienda, un canal que pocas cafeterías tienen.
- **Temporadas de regalo** (Día del Padre, Navidad) para kits de accesorios y café.

## Debilidades (internas)
- **Equipo pequeño** (3 personas) y tiempo limitado al semestre.
- **Stock pequeño y artesanal:** las existencias pueden agotarse rápido.
- **Pagos en modo prueba:** para cobrar de verdad hace falta dar de alta cuentas de
  producción en Mercado Pago y PayPal.
- **Planes gratuitos de hosting:** Render duerme el backend sin visitas (primer acceso lento).
- **Fotos de catálogo libres (Unsplash)** en lugar de fotografía propia del producto.
- **Sin app móvil nativa** (la web es responsiva, pero no hay notificaciones push).

## Amenazas (externas)
- **Competencia de grandes marcas y marketplaces** (Amazon, Mercado Libre, cadenas con
  tienda en línea) con envíos rápidos y precios agresivos.
- **Costos de envío** que pueden encarecer compras pequeñas.
- **Variación del precio del café** (clima, tipo de cambio) que afecta márgenes.
- **Fraude y contracargos** en pagos en línea.
- **Dependencia de terceros:** caídas o cambios de las APIs de pago, envíos o correo.

## Estrategias derivadas (cruce FODA)
| | Oportunidades | Amenazas |
|---|---|---|
| **Fortalezas** | (FO) Usar la recompra y la molienda a la medida para captar oficinas y consumidores de especialidad. | (FA) Diferenciarse por asesoría y frescura frente a marketplaces; recoger en el local sin costo para evitar el costo de envío. |
| **Debilidades** | (DO) Arrancar con pagos y envíos en sandbox y pasar a producción al validar ventas; fotos propias en la siguiente etapa. | (DA) Confirmar pagos siempre con el proveedor (nunca con el navegador), modos simulados si una API falla y pruebas automatizadas en cada cambio. |
