-- ============================================================================
-- Binaria 2026-07-17 — Revisión 3 (Fase B): rediseño de Bandeos.
--
-- El bandeo ahora se PLANIFICA antes de la visita (llave POS + fecha) y luego
-- se Recibe (vincula la visita) y se Devuelve. Cambios de esquema:
--
--   A) t_trade_complementary_bandeo_header
--      + pos_id            : POS planificado (el bandeo existe antes de la visita).
--      + planned_date      : fecha/hora planificada de la visita.
--      + promotion_quantity: unidades de la promoción asignadas al POS + fecha.
--      * attendance_id      : pasa a NULLABLE (se llena al Recibir).
--      * unique             : se reemplaza (attendance_id, promotion_id) por
--                             (pos_id, planned_date, promotion_id) — la llave de
--                             planificación.
--
--   B) t_trade_complementary_bandeo_detail
--      * unit_of_measure    : pasa de VARCHAR(20) a INT (es un ID que viene en el
--                             request, de un catálogo externo).
--
-- OJO: convertir unit_of_measure a INT falla si hay valores de texto no
-- numéricos previos. Estamos en fase de pruebas; coordinar con Binaria antes de
-- aplicar en cualquier ambiente con datos productivos.
-- ============================================================================

-- A) Header --------------------------------------------------------------------
ALTER TABLE t_trade_complementary_bandeo_header
    ADD COLUMN pos_id INT NULL AFTER client_company_id,
    ADD COLUMN planned_date DATETIME NULL AFTER pos_id,
    ADD COLUMN promotion_quantity INT NULL AFTER planned_date,
    MODIFY COLUMN attendance_id INT NULL;

CREATE INDEX ix_bandeo_header_pos_id ON t_trade_complementary_bandeo_header (pos_id);
CREATE INDEX ix_bandeo_header_planned_date ON t_trade_complementary_bandeo_header (planned_date);

-- Replace the planning uniqueness key.
ALTER TABLE t_trade_complementary_bandeo_header
    DROP INDEX uc_bandeo_attendance_promotion;
ALTER TABLE t_trade_complementary_bandeo_header
    ADD CONSTRAINT uc_bandeo_pos_date_promotion
    UNIQUE (pos_id, planned_date, promotion_id);

-- B) Detail --------------------------------------------------------------------
ALTER TABLE t_trade_complementary_bandeo_detail
    MODIFY COLUMN unit_of_measure INT NULL;
