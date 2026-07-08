-- Active: 1753321721448@@localhost@3309@binaria
-- ============================================================================
-- Binaria 2026-07-08 — Detalle por producto en Reposición + Inventario de
-- reposiciones línea-libre + client_company_id en Competencia.
--
-- Cubre las observaciones del email de Binaria sobre Reposiciones,
-- Puntos Promocionales, Competencia e Inventarios:
--
--   A) t_trade_replenishment_report_details (NUEVA TABLA)
--      Detalle por producto del reporte de reposición: cada producto marca
--      si fue repuesto (replaced) y, opcionalmente, cantidad y comentario.
--
--   B) t_trade_complementary_competition (+ client_company_id)
--      OJO: en iter 5 se dijo que esta tabla "no se modifica". Binaria pidió
--      ahora poder filtrar el listado de competencia por marca/cliente, por
--      lo que se AGREGA client_company_id (nullable). Reversa consciente de
--      aquella decisión.
--
--   C) t_trade_replenishment_inventory (NUEVA TABLA, línea-libre)
--      OJO: en iter 5 esta tabla se ELIMINÓ para unificar el inventario con
--      Impulsos. El inventario de Impulsos SIGUE unificado y NO cambia. Pero
--      Binaria necesita, solo para Reposiciones, registrar el mismo producto
--      en varias líneas con distinto lote / vencimiento / ubicación (reporte
--      de fecha corta), algo que el modelo unificado (una fila por producto)
--      no permite. Por eso se RE-INTRODUCE una tabla dedicada, ahora con
--      estructura LÍNEA-LIBRE (sin unique por producto).
--
-- Todas las columnas nuevas de tablas existentes son NULLABLE para preservar
-- filas previas. Estamos en fase de pruebas; coordinar con Binaria antes de
-- aplicar en cualquier ambiente con datos productivos.
-- ============================================================================

-- =========================================================================
-- A) t_trade_replenishment_report_details (NUEVA)
--    Detalle por producto del reporte de reposición (repuesto sí/no).
-- =========================================================================
CREATE TABLE t_trade_replenishment_report_details (
    id           INT         NOT NULL AUTO_INCREMENT,
    report_id    INT         NOT NULL,
    product_id   INT         NOT NULL,
    replaced     BOOLEAN     NOT NULL DEFAULT FALSE,
    quantity     INT         NULL,
    comments     TEXT        NULL,
    PRIMARY KEY (id),
    INDEX idx_replen_report_detail_report (report_id),
    INDEX idx_replen_report_detail_product (product_id),
    CONSTRAINT uc_replenishment_report_product UNIQUE (report_id, product_id),
    CONSTRAINT fk_replen_report_detail_report FOREIGN KEY (report_id)
        REFERENCES t_trade_replenishment_reports (id) ON DELETE CASCADE,
    CONSTRAINT fk_replen_report_detail_product FOREIGN KEY (product_id)
        REFERENCES t_products (id) ON DELETE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

-- =========================================================================
-- B) t_trade_complementary_competition (+ client_company_id)
-- =========================================================================
ALTER TABLE t_trade_complementary_competition
    ADD COLUMN client_company_id INT NULL,
    ADD INDEX idx_competition_client_company (client_company_id);

-- =========================================================================
-- C) t_trade_replenishment_inventory (NUEVA, línea-libre)
--    Sin unique constraint: el mismo product_id puede repetirse en varias
--    filas con distinto lote / vencimiento / ubicación.
--    location = 'SALA' | 'ALMACEN'.
-- =========================================================================
CREATE TABLE t_trade_replenishment_inventory (
    id                 INT         NOT NULL AUTO_INCREMENT,
    attendance_id      INT         NOT NULL,
    product_id         INT         NOT NULL,
    client_company_id  INT         NULL,
    quantity           INT         NOT NULL DEFAULT 0,
    batch_number       VARCHAR(50) NULL,
    expiration_date    DATETIME    NULL,
    location           VARCHAR(20) NOT NULL,
    observations       TEXT        NULL,
    created_at         DATETIME    NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_replen_inv_attendance (attendance_id),
    INDEX idx_replen_inv_product (product_id),
    INDEX idx_replen_inv_client_company (client_company_id),
    INDEX idx_replen_inv_batch (batch_number),
    CONSTRAINT fk_replen_inv_product FOREIGN KEY (product_id)
        REFERENCES t_products (id) ON DELETE RESTRICT
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
