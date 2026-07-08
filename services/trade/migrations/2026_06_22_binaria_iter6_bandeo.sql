-- Active: 1753321721448@@localhost@3309@binaria
-- ============================================================================
-- Binaria iter 6 (2026-06-22) — Bandeo en ejecucion (req 7.3.4.1)
--
-- Cambios:
--   A) t_trade_complementary_bandeo_header
--      - Se elimina el UNIQUE (attendance_id): una visita puede registrar N
--        bandeos (uno por bandeo planificado / promotion).
--      - Se agrega promotion_id (FK a t_trade_promotions) para identificar a
--        que bandeo planificado pertenece el header.
--      - Se agrega un UNIQUE compuesto (attendance_id, promotion_id) para
--        evitar duplicados por visita y promocion.
--      - Se agrega status (PENDING/RECEIVED/RETURNED) + received_at +
--        returned_at, para soportar el flujo de 2 pasos demandado por el
--        requerimiento.
--
--   B) t_trade_complementary_bandeo_detail
--      - Se agregan quantity_planned, quantity_received, quantity_used,
--        unit_of_measure, observations.
--      - quantity_returned pasa a ser NULLABLE (la operadora la confirma en
--        el paso Devolver; default = recibida - utilizada).
--
-- Estamos en fase de pruebas (no productivo). Si Binaria ya tuviera
-- registros previos de bandeo, conviene avisar antes de correr este script.
-- ============================================================================

-- =========================================================================
-- A.0) Drop defensivo del UNIQUE legacy sobre attendance_id
-- =========================================================================
-- Nota (2026-06-22): el modelo SQLAlchemy declaraba attendance_id como
-- UNIQUE pero en el ambiente de Binaria el indice no llego a crearse,
-- por lo que un DROP INDEX directo fallaba. Lo envolvemos en una
-- sentencia preparada que primero verifica si existe el indice; asi el
-- script es seguro de reejecutar tanto en ambientes que SI tienen el
-- indice como en los que NO.
SET @idx_exists := (
    SELECT COUNT(1) FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 't_trade_complementary_bandeo_header'
      AND index_name = 'attendance_id'
);
SET @sql := IF(
    @idx_exists > 0,
    'ALTER TABLE t_trade_complementary_bandeo_header DROP INDEX attendance_id',
    'SELECT "Index attendance_id not present, skipping drop" AS notice'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- =========================================================================
-- A) t_trade_complementary_bandeo_header
-- =========================================================================
ALTER TABLE t_trade_complementary_bandeo_header
    ADD COLUMN promotion_id INT NULL AFTER attendance_id,
    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'PENDING' AFTER promotion_id,
    ADD COLUMN received_at DATETIME NULL AFTER status,
    ADD COLUMN returned_at DATETIME NULL AFTER received_at,
    ADD INDEX idx_bandeo_header_attendance (attendance_id),
    ADD INDEX idx_bandeo_header_promotion (promotion_id),
    ADD INDEX idx_bandeo_header_status (status),
    ADD CONSTRAINT fk_bandeo_header_promotion
        FOREIGN KEY (promotion_id) REFERENCES t_trade_promotions(id)
        ON DELETE RESTRICT,
    ADD CONSTRAINT uc_bandeo_attendance_promotion
        UNIQUE (attendance_id, promotion_id);

-- =========================================================================
-- B) t_trade_complementary_bandeo_detail
-- =========================================================================
ALTER TABLE t_trade_complementary_bandeo_detail
    ADD COLUMN quantity_planned INT NOT NULL DEFAULT 0 AFTER product_id,
    ADD COLUMN quantity_received INT NOT NULL DEFAULT 0 AFTER quantity_planned,
    ADD COLUMN quantity_used INT NULL AFTER quantity_received,
    ADD COLUMN unit_of_measure VARCHAR(20) NULL AFTER quantity_returned,
    ADD COLUMN observations TEXT NULL AFTER unit_of_measure,
    MODIFY COLUMN quantity_returned INT NULL;
