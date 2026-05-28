-- Active: 1753321721448@@127.0.0.1@3309@binaria
-- ============================================================
-- TRADE Migration — 2026-05-28 (iter 3)
-- Cliente: Binaria. Set urgente previo al go-live del 2026-06-03.
--
-- Cambios cubiertos:
--   1) ImpulseSale gana columna `observations` (registro de ventas).
--   2) PlannedRoute.status: el default cambia de 'ACTIVE' a 'IN_CREATION'
--      para permitir el flujo de activación posterior. Los registros
--      existentes que estén en estados productivos se respetan; SOLO el
--      DEFAULT del DDL se ajusta (no se hace UPDATE masivo).
--
-- Aplicar después de 2026_05_20_binaria_requirements_iter2.sql.
-- ============================================================

-- ---------- 1) ImpulseSale: observations ----------
ALTER TABLE t_trade_impulse_sales
    ADD COLUMN observations TEXT NULL AFTER client_company_id;

-- ---------- 2) PlannedRoute: status default = IN_CREATION ----------
ALTER TABLE t_trade_planned_routes
    MODIFY COLUMN status VARCHAR(20) NOT NULL DEFAULT 'IN_CREATION';

-- Backfill OPCIONAL: si quieres que las rutas ya creadas hoy también
-- pasen a IN_CREATION antes del go-live, ejecuta manualmente:
--
--   UPDATE t_trade_planned_routes SET status = 'IN_CREATION'
--    WHERE status = 'ACTIVE' AND created_at >= '2026-05-27';
--
-- No se hace automático para no tocar rutas productivas que ya están
-- ACTIVE intencionalmente.
