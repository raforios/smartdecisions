-- ============================================================================
-- Binaria 2026-07-17 — Revisión 3 (Fase A).
--
-- Cubre las observaciones del correo de Paula sobre TRADE que requieren cambio
-- de esquema. La mayoría de las observaciones ("falta company_id / pos_id /
-- user_id en la respuesta") NO tocan la base: esos datos se resuelven por JOIN
-- con la visita (t_trade_attendances) en la capa de servicio.
--
-- Único cambio de esquema de la Fase A:
--
--   A) t_trade_promotion_details (+ sku_quantity)
--      Cantidad de cada SKU que compone una unidad de la promoción (bandeo).
--      Ej.: 12 salchichas por paquete "san juanero". Habilita el cálculo de
--      la demanda planificada del bandeo:  qty_planned = promotion_quantity *
--      sku_quantity  (se usará en la Fase B — planificación de bandeos).
--
-- La columna es NOT NULL con DEFAULT 1 para preservar filas previas (cada SKU
-- contaba como 1). Estamos en fase de pruebas; coordinar con Binaria antes de
-- aplicar en cualquier ambiente con datos productivos.
-- ============================================================================

ALTER TABLE t_trade_promotion_details
    ADD COLUMN sku_quantity INTEGER NOT NULL DEFAULT 1
    COMMENT 'Qty of this SKU per unit of the promotion (Binaria 2026-07-17)';
