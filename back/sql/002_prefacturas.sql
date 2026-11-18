-- =========================================================
-- 002_prefacturas.sql — prefactura con la estructura del CFDI (RQF90 a RQF96)
--
-- PREFACTURAS: una por pedido pagado (1 : 0..1 con pedidos), con las columnas
-- del Diagrama Entidad-Relación (sección 5.4 del SRS). El XML completo queda
-- en `xml`; el PDF se genera a partir de él al descargarlo.
--   estado: generada → validada (pasó XSD y catálogos) | error (no se pone
--   a disposición del cliente, RQNF118) | timbrada (con PAC, por implementar).
--
-- pedidos.datos_fiscales: lo que el cliente captura en el pago (RFC, nombre,
-- régimen, CP fiscal y uso del CFDI) se guarda con el pedido hasta que se
-- aprueba el pago y se genera la prefactura. NULL = público en general.
-- =========================================================

CREATE TABLE prefacturas (
    id                      SERIAL PRIMARY KEY,
    pedido_id               INT           NOT NULL UNIQUE REFERENCES pedidos (id) ON DELETE RESTRICT,
    serie                   TEXT          NOT NULL,
    folio                   INT           NOT NULL,
    rfc_receptor            TEXT          NOT NULL,
    nombre_receptor         TEXT          NOT NULL,
    regimen_fiscal_receptor TEXT          NOT NULL,
    cp_fiscal_receptor      TEXT          NOT NULL CHECK (cp_fiscal_receptor ~ '^[0-9]{5}$'),
    uso_cfdi                TEXT          NOT NULL,
    subtotal                NUMERIC(12,2) NOT NULL CHECK (subtotal >= 0),
    iva                     NUMERIC(12,2) NOT NULL CHECK (iva >= 0),
    total                   NUMERIC(12,2) NOT NULL CHECK (total >= 0),
    xml                     TEXT          NOT NULL,
    estado                  TEXT          NOT NULL CHECK (estado IN ('generada', 'validada', 'timbrada', 'error')),
    uuid_timbre             TEXT,
    creada                  TIMESTAMP(0)  NOT NULL
);

CREATE INDEX prefacturas_estado ON prefacturas (estado);

ALTER TABLE pedidos ADD COLUMN datos_fiscales JSONB;
