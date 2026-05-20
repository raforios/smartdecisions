-- ============================================================
-- TRADE Migration — 2026-05-19
-- Cliente: Binaria
-- Requerimientos cubiertos:
--   1) PlannedRoute: executor_company_id, route_type, country_id,
--      city_id, status, color.
--   2) ProductAssignmentPOS: observations.
--   3) TradePlanning: client_company_id (cliente);
--      TradePlanningDetail.date_of_day → DATETIME.
--   4) Attendance: point_of_sale_id (FK directo a t_points_of_sale).
--   5) Observations en t_trade_impulse_inventory_start,
--      t_trade_impulse_inventory_end y t_trade_replenishment_inventory.
--
-- Aplicar en producción (MySQL ≥ 8.0):
--   mysql -h <host> -u <user> -p <db> < 2026_05_19_binaria_requirements.sql
--
-- Notas:
--   - Las columnas nuevas se crean NULLABLE para no romper rows existentes.
--   - El frontend / Pydantic enforcean los valores requeridos en items
--     nuevos. Si querés volverlas NOT NULL, hacelo tras el backfill.
--   - `status` en t_trade_planned_routes lleva default 'ACTIVE'.
-- ============================================================

-- ---------- 1) PlannedRoute ----------
ALTER TABLE t_trade_planned_routes
    ADD COLUMN executor_company_id INT NULL AFTER company_id,
    ADD COLUMN route_type VARCHAR(20) NULL AFTER description,
    ADD COLUMN country_id INT NULL AFTER route_type,
    ADD COLUMN city_id INT NULL AFTER country_id,
    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' AFTER city_id,
    ADD COLUMN color VARCHAR(7) NULL AFTER status,
    ADD INDEX idx_planned_routes_executor (executor_company_id),
    ADD INDEX idx_planned_routes_status (status);

-- ---------- 2) ProductAssignmentPOS ----------
ALTER TABLE t_trade_product_assignments_pos
    ADD COLUMN observations TEXT NULL AFTER status;

-- ---------- 3a) TradePlanning: client_company_id ----------
ALTER TABLE t_trade_planning
    ADD COLUMN client_company_id INT NULL AFTER company_id,
    ADD INDEX idx_trade_planning_client (client_company_id);

-- ---------- 3b) TradePlanningDetail: date_of_day DATE → DATETIME ----------
-- MySQL preserva la fecha y agrega 00:00:00 como hora.
ALTER TABLE t_trade_planning_detail
    MODIFY COLUMN date_of_day DATETIME NOT NULL;

-- ---------- 4) Attendance: point_of_sale_id ----------
ALTER TABLE t_trade_attendances
    ADD COLUMN point_of_sale_id INT NULL AFTER trade_planned_point_id,
    ADD INDEX idx_attendance_pos (point_of_sale_id),
    ADD CONSTRAINT fk_attendance_pos
        FOREIGN KEY (point_of_sale_id) REFERENCES t_points_of_sale (id);

-- Backfill opcional para los registros existentes — descomentar si querés
-- poblar la nueva columna a partir del planned_point:
-- UPDATE t_trade_attendances a
--     JOIN t_trade_planned_points pp ON pp.id = a.trade_planned_point_id
-- SET a.point_of_sale_id = pp.point_of_sale_id
-- WHERE a.point_of_sale_id IS NULL;

-- ---------- 5) Observations en inventarios ----------
ALTER TABLE t_trade_impulse_inventory_start
    ADD COLUMN observations TEXT NULL AFTER quantity;

ALTER TABLE t_trade_impulse_inventory_end
    ADD COLUMN observations TEXT NULL AFTER quantity;

ALTER TABLE t_trade_replenishment_inventory
    ADD COLUMN observations TEXT NULL AFTER quantity;
