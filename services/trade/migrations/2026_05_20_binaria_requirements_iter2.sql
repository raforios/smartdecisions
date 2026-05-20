-- ============================================================
-- TRADE Migration — 2026-05-20 (iter 2)
-- Cliente: Binaria. Continúa con los hallazgos del segundo correo.
--
-- Requerimientos cubiertos:
--   1) Attendance lleva la compañía cliente (además de la ejecutora).
--   2) Planning.company_id pasa a NULLABLE (la ejecutora puede definirse
--      más tarde).
--   3) ImpulseSale lleva la compañía cliente (dueña del PDV/productos).
--
-- Aplicar después de 2026_05_19_binaria_requirements.sql.
-- ============================================================

-- ---------- 1) Attendance: client_company_id ----------
ALTER TABLE t_trade_attendances
    ADD COLUMN client_company_id INT NULL AFTER company_id,
    ADD INDEX idx_attendance_client (client_company_id);

-- Backfill opcional: si las attendances existentes tenían planeado un
-- cliente fijo, completalo manualmente. Si no, queda NULL hasta el
-- próximo check-in con el campo cargado.

-- ---------- 2) Planning: company_id NULLABLE ----------
-- 2026-05-20 (Binaria): la compañía ejecutora se decide en otro paso del
-- flujo. La columna pasa a nullable para permitirlo.
ALTER TABLE t_trade_planning
    MODIFY COLUMN company_id INT NULL;

-- ---------- 3) ImpulseSale: client_company_id ----------
ALTER TABLE t_trade_impulse_sales
    ADD COLUMN client_company_id INT NULL AFTER company_id,
    ADD INDEX idx_impulse_sales_client (client_company_id);
