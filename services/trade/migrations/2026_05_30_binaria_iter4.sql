-- ============================================================
-- TRADE Migration — 2026-05-30 (iter 4)
-- Cliente: Binaria. Fix urgente del bulk-upload de productos.
--
-- Cambios cubiertos:
--   1) Product.stock_unit, replenishment_unit, purchase_unit, sale_unit,
--      country_of_origin pasan de VARCHAR(10) a INTEGER. Son IDs que
--      vienen de catálogos externos (manejados por el frontend) y por
--      eso deben almacenarse como enteros.
--
-- Aplicar después de 2026_05_28_binaria_iter3.sql.
--
-- Pre-requisito: las filas existentes en t_products deben tener los 5
-- campos rellenos con valores numéricos (strings de dígitos). Si por
-- accidente quedó algún valor alfanumérico, el ALTER COLUMN va a fallar.
-- Para auditarlo antes de aplicar la migración, correr:
--
--   SELECT id, stock_unit, replenishment_unit, purchase_unit,
--          sale_unit, country_of_origin
--   FROM t_products
--   WHERE stock_unit REGEXP '[^0-9]'
--      OR replenishment_unit REGEXP '[^0-9]'
--      OR purchase_unit REGEXP '[^0-9]'
--      OR sale_unit REGEXP '[^0-9]'
--      OR country_of_origin REGEXP '[^0-9]';
-- ============================================================

ALTER TABLE t_products
    MODIFY COLUMN stock_unit INT NOT NULL,
    MODIFY COLUMN replenishment_unit INT NOT NULL,
    MODIFY COLUMN purchase_unit INT NULL,
    MODIFY COLUMN sale_unit INT NULL,
    MODIFY COLUMN country_of_origin INT NULL;
