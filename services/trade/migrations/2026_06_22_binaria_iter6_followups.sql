-- Active: 1753321721448@@api-binaria-mysql-db.cgbqmuawkgko.us-east-1.rds.amazonaws.com@3306@binaria
-- ============================================================================
-- Binaria iter 6 (2026-06-22) — Follow-ups (req 7.3.4.2, 7.3.4.3, 7.1.1)
--
-- Companion del script 2026_06_22_binaria_iter6_bandeo.sql.
--
--   A) t_trade_complementary_promo_point (req 7.3.4.2)
--      - opening_time TIME       : hora de apertura del punto promocional.
--      - closing_time TIME       : hora de cierre.
--      - description TEXT        : descripcion larga del punto.
--      (comments queda como observacion opcional adicional.)
--
--   B) t_trade_complementary_competition (req 7.3.4.3)
--      - price DECIMAL(12,2)     : precio observado (opcional).
--      - latitude / longitude    : ubicacion geografica del PC (opcional).
--      - location_description TEXT : direccion en formato libre del PC.
--
--   C) t_trade_planned_points (req 7.1.1)
--      - planned_check_in_time TIME : hora prevista de ingreso al PDV.
--
-- Todas las columnas son NULLABLE para preservar filas previas a iter 6.
-- ============================================================================

-- =========================================================================
-- A) t_trade_complementary_promo_point
-- =========================================================================
ALTER TABLE t_trade_complementary_promo_point
    ADD COLUMN opening_time TIME NULL AFTER attendance_id,
    ADD COLUMN closing_time TIME NULL AFTER opening_time,
    ADD COLUMN description TEXT NULL AFTER closing_time;

-- =========================================================================
-- B) t_trade_complementary_competition
-- =========================================================================
ALTER TABLE t_trade_complementary_competition
    ADD COLUMN price DECIMAL(12, 2) NULL AFTER details,
    ADD COLUMN latitude FLOAT NULL AFTER price,
    ADD COLUMN longitude FLOAT NULL AFTER latitude,
    ADD COLUMN location_description TEXT NULL AFTER longitude;

-- =========================================================================
-- C) t_trade_planned_points
-- =========================================================================
ALTER TABLE t_trade_planned_points
    ADD COLUMN planned_check_in_time TIME NULL AFTER point_of_sale_id;
