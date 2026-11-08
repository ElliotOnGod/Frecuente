# SFW — Alcance funcional de Frecuente en línea

## 1. Actores
| Actor | Descripción |
|---|---|
| Visitante | Navega el catálogo, busca y arma su carrito sin cuenta. |
| Cliente | Tiene cuenta: compra, paga, rastrea, programa recompras y contrata membresías. |
| Administrador | Personal de Frecuente: gestiona productos, pedidos, envíos, usuarios, membresías y caja. |
| Agente de IA | Asistente que usa el servidor MCP para consultar la tienda (y, con token de admin, ventas). |
| Sistemas externos | Mercado Pago, PayPal, Envia.com, Brevo, OpenFreeMap. |

## 2. Requerimientos funcionales

### Catálogo
| Id | Requerimiento | Actor |
|---|---|---|
| RF-01 | Ver categorías y productos con foto, precio y disponibilidad. | Visitante |
| RF-02 | Buscar por texto (nombre, descripción, variante) sin importar mayúsculas. | Visitante |
| RF-03 | Filtrar por categoría y por método de preparación (espresso, V60, prensa, goteo, frío, matcha). | Visitante |
| RF-04 | Ver el detalle de un producto con galería y métodos para los que sirve. | Visitante |
| RF-05 | Elegir la variante (molienda) de un producto; comparte precio y stock. | Visitante |

### Carrito y checkout
| Id | Requerimiento | Actor |
|---|---|---|
| RF-06 | Agregar, cambiar cantidad y quitar productos; el carrito se conserva en el navegador. | Visitante |
| RF-07 | No permitir más piezas que el stock (sumando todas las variantes). | Visitante |
| RF-08 | Elegir entrega: recoger en el local (sin costo) o envío a domicilio. | Cliente |
| RF-09 | Autollenar estado, ciudad y colonias al escribir el código postal. | Cliente |
| RF-10 | Cotizar el envío con varias paqueterías y elegir una; el costo se suma al total. | Cliente |
| RF-11 | Elegir método de pago: Mercado Pago, PayPal, transferencia SPEI o efectivo (solo al recoger). | Cliente |
| RF-12 | Registrar el pedido validando stock y precios en el servidor. | Cliente |
| RF-13 | Pagar en la pasarela y confirmar el pago con el proveedor al regresar. | Cliente |
| RF-14 | Ver instrucciones de pago (CLABE / referencia) para transferencia o efectivo. | Cliente |
| RF-15 | Programar la recompra del pedido cada 15, 30 o 60 días. | Cliente |

### Cuenta del cliente
| Id | Requerimiento | Actor |
|---|---|---|
| RF-16 | Registrarse e iniciar sesión (correo y contraseña). | Visitante |
| RF-17 | Ver historial de pedidos con estado de pago y de entrega. | Cliente |
| RF-18 | Ver el detalle de un pedido en vivo y rastrear su envío. | Cliente |
| RF-19 | Pausar, reanudar, cambiar frecuencia o cancelar una recompra. | Cliente |
| RF-20 | Cancelar un pedido no pagado (el stock regresa). | Cliente |
| RF-21 | Contratar una membresía y ver su código del día para canjear en el local. | Cliente |
| RF-22 | Recibir correos: bienvenida, pago confirmado, pedido enviado, membresía activada, recompra lista. | Cliente |

### Administración
| Id | Requerimiento | Actor |
|---|---|---|
| RF-23 | Ver resumen de ventas, ticket promedio, por cobrar, por enviar, más vendidos y stock bajo. | Admin |
| RF-24 | Crear, editar y eliminar productos con fotos, variantes, métodos y peso. | Admin |
| RF-25 | Listar y filtrar pedidos; confirmar pagos, enviar (genera guía), entregar, cancelar y reembolsar. | Admin |
| RF-26 | Ver clientes con su gasto y membresía; cambiar rol y activar/desactivar cuentas. | Admin |
| RF-27 | Ver recompras y generar las del día manualmente. | Admin |
| RF-28 | Gestionar planes y membresías; canjear el beneficio diario en caja con el código. | Admin |
| RF-29 | Recibir avisos en tiempo real (pedido nuevo, pago, stock bajo, canje). | Admin |
| RF-30 | Ver el estado de las integraciones y la bitácora de correos. | Admin |

### Integración con agentes
| Id | Requerimiento | Actor |
|---|---|---|
| RF-31 | Buscar productos, ver categorías y cotizar envío vía MCP. | Agente de IA |
| RF-32 | Consultar pedidos, ventas y stock bajo vía MCP con token de administrador. | Agente de IA |

## 3. Requerimientos no funcionales
| Id | Requerimiento |
|---|---|
| RNF-01 | **Seguridad:** contraseñas con PBKDF2-SHA256 (260 000 iteraciones y sal); sesiones JWT HS256 de 7 días; mismo mensaje y tiempo en login fallido. |
| RNF-02 | **Integridad del cobro:** el precio, el envío (cotización firmada con HMAC) y el resultado del pago los decide el servidor, nunca el navegador. |
| RNF-03 | **Consistencia:** stock con actualización atómica y compensación; pedidos en transacción ACID; idempotencia de pagos y recompras. |
| RNF-04 | **Secretos:** llaves solo en variables de entorno (Render, Netlify, GitHub Secrets). |
| RNF-05 | **Rendimiento:** HTML estático con islas; imágenes comprimidas y con carga diferida. |
| RNF-06 | **Accesibilidad:** etiquetas en formularios, foco visible, estados con texto (no solo color), modo oscuro. |
| RNF-07 | **Responsivo:** usable desde 360 px de ancho. |
| RNF-08 | **Calidad:** lint y pruebas automatizadas en cada push (GitHub Actions). |
| RNF-09 | **Disponibilidad:** modo simulado en cada API externa para que la tienda funcione si una falla o no tiene llave. |

## 4. Reglas de negocio
1. El efectivo solo se acepta al recoger en el local.
2. La recompra se paga en línea o por transferencia; no guarda tarjetas: manda un enlace de pago.
3. Un pedido pagado y cancelado queda "por reembolsar".
4. Un producto que ya se vendió no se puede eliminar (se pone stock 0).
5. La cotización del envío dura 30 minutos y es válida solo para ese código postal y ese peso.
6. El beneficio de la membresía se canjea una vez por persona por día.
7. Un admin no puede quitarse su propio rol ni desactivar su cuenta.

## 5. Fuera de alcance (siguiente etapa)
Cobro recurrente automático con tarjeta guardada, facturación electrónica (CFDI),
cupones de descuento, reseñas de producto, app móvil nativa y fotografía propia.
