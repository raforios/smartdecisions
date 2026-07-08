-- Active: 1753321721448@@localhost@3309@binaria
-- ============================================================================
-- Binaria iter 5 (2026-06-20) — Replenishment + Impulses unification
--
-- Tickets cubiertos (todos del email del equipo de Binaria del 2026-06-20):
--   A) Generales — client_company_id en los modelos de Reposiciones que
--      aún no lo tienen, para alinear con la lógica ya presente en Impulsos.
--   B) Registrar reposición — campo reviewed (bool) en el reporte.
--   C) Inventario de productos — UNIFICACIÓN: la tabla
--      t_trade_replenishment_inventory se elimina y se reemplaza por las
--      tablas de Impulsos (t_trade_impulse_inventory_start /
--      t_trade_impulse_inventory_end), que reciben los campos nuevos
--      (batch / vencimiento / sala / almacén / client_company_id).
--      Razón funcional: el inventario es un solo concepto físico que
--      transita por dos procesos (Impulsos lo mueven, Reposiciones lo
--      restituyen); mantenerlo en una sola tabla evita inconsistencias.
--   D) Productos del proveedor — batch_number y expiration_date en
--      recepciones (faltaban en el modelo).
--
-- Las columnas nuevas se agregan como NULLABLE (o con DEFAULT) para que
-- las filas previas a iter 5 sigan siendo válidas. Estamos en fase de
-- pruebas, así que también se ejecuta el DROP de la tabla legacy.
-- ============================================================================

-- =========================================================================
-- A + B) t_trade_replenishment_reports
-- =========================================================================
ALTER TABLE t_trade_replenishment_reports
    ADD COLUMN client_company_id INT NULL,
    ADD COLUMN reviewed BOOLEAN NOT NULL DEFAULT FALSE,
    ADD INDEX idx_replenish_report_client_company (client_company_id),
    ADD INDEX idx_replenish_report_reviewed (reviewed);

-- =========================================================================
-- C) UNIFICACIÓN: t_trade_impulse_inventory_start / _end absorben los
--    campos de Reposiciones. La unique constraint pasa a incluir
--    batch_number para que un PdV pueda reportar el mismo producto en
--    múltiples lotes durante una misma visita.
-- =========================================================================
ALTER TABLE t_trade_impulse_inventory_start
    ADD COLUMN client_company_id INT NULL,
    ADD COLUMN batch_number VARCHAR(50) NULL,
    ADD COLUMN expiration_date DATETIME NULL,
    ADD COLUMN quantity_in_room INT NOT NULL DEFAULT 0,
    ADD COLUMN quantity_in_warehouse INT NOT NULL DEFAULT 0,
    MODIFY COLUMN quantity INT NULL,
    ADD INDEX idx_impulse_start_client_company (client_company_id),
    ADD INDEX idx_impulse_start_batch (batch_number),
    DROP INDEX uc_impulse_start_attendance_product,
    ADD CONSTRAINT uc_impulse_start_attendance_product_batch
        UNIQUE (attendance_id, product_id, batch_number);

-- Backfill: cualquier fila previa con quantity > 0 se trata como en sala.
UPDATE t_trade_impulse_inventory_start
SET quantity_in_room = quantity
WHERE quantity_in_room = 0 AND quantity IS NOT NULL AND quantity > 0;

ALTER TABLE t_trade_impulse_inventory_end
    ADD COLUMN client_company_id INT NULL,
    ADD COLUMN batch_number VARCHAR(50) NULL,
    ADD COLUMN expiration_date DATETIME NULL,
    ADD COLUMN quantity_in_room INT NOT NULL DEFAULT 0,
    ADD COLUMN quantity_in_warehouse INT NOT NULL DEFAULT 0,
    MODIFY COLUMN quantity INT NULL,
    ADD INDEX idx_impulse_end_client_company (client_company_id),
    ADD INDEX idx_impulse_end_batch (batch_number);

UPDATE t_trade_impulse_inventory_end
SET quantity_in_room = quantity
WHERE quantity_in_room = 0 AND quantity IS NOT NULL AND quantity > 0;

-- Si el ambiente de Binaria ya tenía una unique constraint adicional en
-- t_trade_impulse_inventory_end, descomentar:
--   ALTER TABLE t_trade_impulse_inventory_end
--       DROP INDEX uc_impulse_end_attendance_product,
--       ADD CONSTRAINT uc_impulse_end_attendance_product_batch
--           UNIQUE (attendance_id, product_id, batch_number);

-- =========================================================================
-- C) ELIMINACIÓN de t_trade_replenishment_inventory.
-- Estamos en fase de pruebas; no hay datos productivos. La tabla queda
-- obsoleta porque la lógica vive ahora en las tablas de Impulsos.
-- =========================================================================
DROP TABLE IF EXISTS t_trade_replenishment_inventory;

-- =========================================================================
-- A + D) t_trade_replenishment_receptions
--   - client_company_id.
--   - batch_number + expiration_date (faltaban; sin ellos no se podían
--     registrar vencimientos en la recepción del proveedor).
-- =========================================================================
ALTER TABLE t_trade_replenishment_receptions
    ADD COLUMN client_company_id INT NULL,
    ADD COLUMN batch_number VARCHAR(50) NULL,
    ADD COLUMN expiration_date DATETIME NULL,
    ADD INDEX idx_replenish_recep_client_company (client_company_id),
    ADD INDEX idx_replenish_recep_batch (batch_number);

-- =========================================================================
-- A) t_trade_complementary_bandeo_header / promo_point
--   client_company_id consistente con los demás reportes de reposición.
-- =========================================================================
ALTER TABLE t_trade_complementary_bandeo_header
    ADD COLUMN client_company_id INT NULL,
    ADD INDEX idx_bandeo_client_company (client_company_id);

ALTER TABLE t_trade_complementary_promo_point
    ADD COLUMN client_company_id INT NULL,
    ADD INDEX idx_promo_point_client_company (client_company_id);

-- t_trade_complementary_competition NO se modifica: es un reporte general
-- sobre la competencia, no específico a una compañía cliente.
