-- =========================================================
-- 001_inicial.sql — tablas transaccionales de Frecuente (PostgreSQL)
--
-- Aquí vive lo que necesita llaves foráneas y transacciones ACID:
-- quién compra, qué compró, cuánto pagó, a dónde se envía y qué
-- correos se le mandaron. El catálogo y las membresías siguen en
-- MongoDB (ver relacional.py, "persistencia políglota").
-- =========================================================

CREATE TABLE usuarios (
    id            SERIAL PRIMARY KEY,
    nombre        TEXT        NOT NULL CHECK (length(btrim(nombre)) > 0),
    email         TEXT        NOT NULL UNIQUE CHECK (email = lower(email) AND email LIKE '%_@_%'),
    telefono      TEXT        NOT NULL DEFAULT '' CHECK (telefono = '' OR telefono ~ '^[0-9]{10}$'),
    rol           TEXT        NOT NULL DEFAULT 'cliente' CHECK (rol IN ('cliente', 'admin')),
    activo        BOOLEAN     NOT NULL DEFAULT TRUE,
    password_hash TEXT        NOT NULL,
    creado        TIMESTAMP(0) NOT NULL
);

-- Recompra: el cliente pide que se le repita el mismo pedido cada N días
CREATE TABLE suscripciones (
    id          SERIAL PRIMARY KEY,
    usuario_id  INT          NOT NULL REFERENCES usuarios (id) ON DELETE RESTRICT,
    estado      TEXT         NOT NULL CHECK (estado IN ('activa', 'pausada', 'cancelada')),
    cada_dias   INT          NOT NULL CHECK (cada_dias IN (15, 30, 60)),
    proxima     DATE         NOT NULL,
    metodo_pago TEXT         NOT NULL CHECK (metodo_pago IN ('mercadopago', 'paypal', 'transferencia', 'efectivo')),
    entrega     JSONB        NOT NULL,   -- dirección y paquetería elegidas
    creada      TIMESTAMP(0) NOT NULL
);

CREATE TABLE suscripcion_items (
    suscripcion_id INT  NOT NULL REFERENCES suscripciones (id) ON DELETE CASCADE,
    producto_id    INT  NOT NULL,          -- vive en MongoDB (catálogo)
    variante       TEXT NOT NULL DEFAULT '',
    cantidad       INT  NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (suscripcion_id, producto_id, variante)
);

CREATE TABLE pedidos (
    id             SERIAL PRIMARY KEY,
    usuario_id     INT           NOT NULL REFERENCES usuarios (id) ON DELETE RESTRICT,
    suscripcion_id INT           REFERENCES suscripciones (id) ON DELETE SET NULL,
    fecha          TIMESTAMP(0)  NOT NULL,
    estado         TEXT          NOT NULL CHECK (estado IN ('registrado', 'pagado', 'enviado', 'entregado', 'cancelado')),
    subtotal       NUMERIC(10,2) NOT NULL CHECK (subtotal >= 0),
    envio          NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (envio >= 0),
    total          NUMERIC(10,2) NOT NULL,
    CHECK (total = subtotal + envio)
);

-- Renglones del pedido. Se guarda el nombre y el precio COMO ESTABAN al
-- comprar: si mañana cambia el precio, el pedido de hoy no cambia.
CREATE TABLE pedido_items (
    id          SERIAL PRIMARY KEY,
    pedido_id   INT           NOT NULL REFERENCES pedidos (id) ON DELETE CASCADE,
    producto_id INT           NOT NULL,     -- vive en MongoDB (catálogo)
    nombre      TEXT          NOT NULL,
    variante    TEXT          NOT NULL DEFAULT '',
    cantidad    INT           NOT NULL CHECK (cantidad > 0),
    precio_unit NUMERIC(10,2) NOT NULL CHECK (precio_unit >= 0)
);

-- Un pedido tiene exactamente un cobro (relación 1 a 1: la llave es el pedido)
CREATE TABLE pagos (
    pedido_id    INT          PRIMARY KEY REFERENCES pedidos (id) ON DELETE CASCADE,
    metodo       TEXT         NOT NULL CHECK (metodo IN ('mercadopago', 'paypal', 'transferencia', 'efectivo')),
    estado       TEXT         NOT NULL CHECK (estado IN ('pendiente', 'aprobado', 'rechazado', 'por_reembolsar', 'reembolsado')),
    modo         TEXT         NOT NULL CHECK (modo IN ('simulado', 'sandbox', 'manual')),
    referencia   TEXT         NOT NULL,
    proveedor_id TEXT         NOT NULL DEFAULT '',
    pago_id      TEXT         NOT NULL DEFAULT '',
    detalle      TEXT         NOT NULL DEFAULT '',
    intentos     INT          NOT NULL DEFAULT 0 CHECK (intentos >= 0),
    fecha_pago   TIMESTAMP(0),
    actualizado  TIMESTAMP(0) NOT NULL
);

-- Cómo se entrega: recoger en el local o envío a domicilio (Envia.com)
CREATE TABLE envios (
    pedido_id    INT           PRIMARY KEY REFERENCES pedidos (id) ON DELETE CASCADE,
    tipo         TEXT          NOT NULL CHECK (tipo IN ('recoger', 'domicilio')),
    nombre       TEXT          NOT NULL DEFAULT '',
    telefono     TEXT          NOT NULL DEFAULT '',
    calle        TEXT          NOT NULL DEFAULT '',
    numero       TEXT          NOT NULL DEFAULT '',
    colonia      TEXT          NOT NULL DEFAULT '',
    ciudad       TEXT          NOT NULL DEFAULT '',
    estado       TEXT          NOT NULL DEFAULT '',   -- código de 2 letras (JA, CX, NL…)
    cp           TEXT          NOT NULL DEFAULT '',
    referencias  TEXT          NOT NULL DEFAULT '',
    paqueteria   TEXT          NOT NULL DEFAULT '',
    servicio     TEXT          NOT NULL DEFAULT '',
    descripcion  TEXT          NOT NULL DEFAULT '',
    dias         TEXT          NOT NULL DEFAULT '',
    costo        NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (costo >= 0),
    modo         TEXT          NOT NULL DEFAULT 'simulado' CHECK (modo IN ('simulado', 'sandbox', 'manual')),
    guia         TEXT          NOT NULL DEFAULT '',
    rastreo_url  TEXT          NOT NULL DEFAULT '',
    etiqueta_url TEXT          NOT NULL DEFAULT '',
    CHECK (tipo = 'recoger' OR cp ~ '^[0-9]{5}$')
);

-- Bitácora de correos (Brevo). Sirve para auditar y para la demo en modo simulado.
CREATE TABLE correos (
    id           SERIAL PRIMARY KEY,
    destinatario TEXT         NOT NULL,
    asunto       TEXT         NOT NULL,
    plantilla    TEXT         NOT NULL,
    estado       TEXT         NOT NULL CHECK (estado IN ('enviado', 'simulado', 'error')),
    proveedor_id TEXT         NOT NULL DEFAULT '',
    detalle      TEXT         NOT NULL DEFAULT '',
    pedido_id    INT          REFERENCES pedidos (id) ON DELETE SET NULL,
    creado       TIMESTAMP(0) NOT NULL
);

-- Índices: las búsquedas que hace el panel y "mis pedidos"
CREATE INDEX pedidos_usuario_fecha  ON pedidos (usuario_id, fecha DESC);
CREATE INDEX pedidos_estado_fecha   ON pedidos (estado, fecha);
CREATE INDEX pedido_items_producto  ON pedido_items (producto_id);
CREATE INDEX pedido_items_pedido    ON pedido_items (pedido_id);
CREATE INDEX pagos_estado           ON pagos (estado);
CREATE INDEX pagos_metodo           ON pagos (metodo);
CREATE INDEX suscripciones_proximas ON suscripciones (estado, proxima);
CREATE INDEX correos_creado         ON correos (creado DESC);
