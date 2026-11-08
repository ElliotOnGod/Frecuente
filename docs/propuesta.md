# Propuesta formal del proyecto (resumen)

> Documento original: `FRECUENTE_Propuesta_Producto_Integrador.docx`, primera versión, 25/08/2026.
> Aquí se resume y se indica cómo quedó implementado cada punto.

## Nombre
E-commerce enfocado a la distribución de café de especialidad: **Frecuente en línea**.

## Problema
FRECUENTE es una cafetería de Guadalajara que solo vende en su local. Los clientes que
quieren preparar su café en casa no pueden comprar grano, molido, leches, matcha o
accesorios fuera del horario o la ubicación del local, y los ingresos dependen únicamente
del tráfico presencial.

## A quién afecta
- Clientes actuales del local que quieren llevarse su café a casa.
- Amantes del café de especialidad que buscan grano de origen y calidad artesanal.
- Oficinas y negocios que necesitan un proveedor de café recurrente.
- La propia cafetería, que no tiene un canal digital de ventas.

## Qué se propone
Un eCommerce para FRECUENTE con catálogo filtrable, variantes de producto (molienda),
carrito, checkout con pagos en línea (Mercado Pago y PayPal), envío a domicilio,
suscripción de recompra y panel administrativo, desplegado en la nube con CI/CD.

## Objetivo general
Llevar la marca más allá del mostrador con una tienda funcional, una experiencia de compra
simple y coherente con la identidad visual, que abra una fuente de ingresos que no dependa
del tráfico presencial.

## De la propuesta a la implementación

| Prometido en la propuesta | Estado | Dónde |
|---|---|---|
| Catálogo filtrable por categoría | Hecho | `/tienda`, `/categoria` |
| Filtro por método de preparación | Hecho | `/tienda?metodo=prensa`, chips del inicio |
| Variantes configurables (molienda) sin duplicar páginas | Hecho | Modal de producto, renglón del pedido |
| Carrito y checkout simples | Hecho | `/carrito`, `/checkout` |
| Pagos con Mercado Pago y PayPal | Hecho (simulado/sandbox) | `back/pagos.py` |
| Cuentas de usuario | Hecho | `/registro`, `/login`, `/cuenta` |
| Suscripción para recompra mensual | Hecho | Checkout → "Repetir este pedido"; `/cuenta`; `/admin/recompras` |
| Recibir el producto en domicilio u oficina | Hecho | Envío con Envia.com en el checkout |
| Panel administrativo (productos, usuarios, pedidos) | Hecho | `/admin/*` |
| PostgreSQL + MongoDB | Hecho | `back/relacional.py`, `back/database.py` |
| GraphQL y MCP | Hecho | `/graphql`, `/mcp` |
| Despliegue en la nube con CI/CD | Hecho | Render + Netlify, GitHub Actions |
| Variables de entorno y credenciales seguras | Hecho | `back/.env.example`, secretos en Render/GitHub |

Además de lo propuesto se agregaron **membresías** con canje diario en el local (código
del día firmado con HMAC) y **tiempo real** en el panel (GraphQL Subscriptions).
