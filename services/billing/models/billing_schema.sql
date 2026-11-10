-- BILLING: el esquema de su base PostgreSQL, generado de models/billing_tables.py
-- con schema_sql(). Se aplica conectado como el usuario billing; sin Alembic.


CREATE TABLE products (
	owner VARCHAR(120) NOT NULL, 
	sku VARCHAR(40) NOT NULL, 
	description VARCHAR(200) NOT NULL, 
	laboratory VARCHAR(120) NOT NULL, 
	category VARCHAR(80), 
	unit VARCHAR(20) NOT NULL, 
	barcode VARCHAR(60), 
	min_stock NUMERIC(14, 3) NOT NULL, 
	suggested_price NUMERIC(14, 4), 
	requires_prescription BOOLEAN NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	sin_activity_code VARCHAR(20), 
	sin_product_code VARCHAR(20), 
	sin_unit_code INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (owner, sku)
);

CREATE TABLE lots (
	owner VARCHAR(120) NOT NULL, 
	sku VARCHAR(40) NOT NULL, 
	lot_id VARCHAR(60) NOT NULL, 
	unit_cost NUMERIC(14, 4) NOT NULL, 
	sale_price NUMERIC(14, 4) NOT NULL, 
	quantity_received NUMERIC(14, 3) NOT NULL, 
	quantity_remaining NUMERIC(14, 3) NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	lot_code VARCHAR(60), 
	expiry_date DATE, 
	purchase_id VARCHAR(60), 
	PRIMARY KEY (owner, sku, lot_id)
);

CREATE TABLE sales (
	owner VARCHAR(120) NOT NULL, 
	sale_id VARCHAR(60) NOT NULL, 
	number VARCHAR(40) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	payment_method VARCHAR(30) NOT NULL, 
	lines JSONB NOT NULL, 
	subtotal NUMERIC(14, 4) NOT NULL, 
	discount NUMERIC(14, 4) NOT NULL, 
	total NUMERIC(14, 4) NOT NULL, 
	cost NUMERIC(14, 4) NOT NULL, 
	created_by VARCHAR(120) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	buyer JSONB NOT NULL, 
	notes TEXT, 
	card_number VARCHAR(20), 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	cancelled_by VARCHAR(120), 
	cash_session_id VARCHAR(60), 
	invoice JSONB, 
	invoice_xml TEXT, 
	payments JSONB NOT NULL, 
	credit_notes JSONB NOT NULL, 
	PRIMARY KEY (owner, sale_id)
);

CREATE INDEX ix_sales_owner_created ON sales (owner, created_at);

CREATE TABLE purchases (
	owner VARCHAR(120) NOT NULL, 
	purchase_id VARCHAR(60) NOT NULL, 
	number VARCHAR(40) NOT NULL, 
	supplier_name VARCHAR(200) NOT NULL, 
	lines JSONB NOT NULL, 
	total_cost NUMERIC(14, 4) NOT NULL, 
	created_by VARCHAR(120) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	supplier_document VARCHAR(40), 
	invoice_number VARCHAR(40), 
	invoice_date DATE, 
	notes TEXT, 
	PRIMARY KEY (owner, purchase_id)
);

CREATE INDEX ix_purchases_owner_created ON purchases (owner, created_at);

CREATE TABLE settings (
	owner VARCHAR(120) NOT NULL, 
	setting_key VARCHAR(120) NOT NULL, 
	value JSONB NOT NULL, 
	PRIMARY KEY (owner, setting_key)
);

CREATE TABLE cash_sessions (
	owner VARCHAR(120) NOT NULL, 
	session_id VARCHAR(60) NOT NULL, 
	user_email VARCHAR(120) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	business_day DATE NOT NULL, 
	opened_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	opening_cash NUMERIC(14, 4) NOT NULL, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	closed_by VARCHAR(120), 
	counted_cash NUMERIC(14, 4), 
	expected_cash NUMERIC(14, 4), 
	difference NUMERIC(14, 4), 
	note TEXT, 
	PRIMARY KEY (owner, session_id)
);

CREATE INDEX ix_cash_sessions_owner_day ON cash_sessions (owner, business_day);

CREATE TABLE cash_movements (
	owner VARCHAR(120) NOT NULL, 
	session_id VARCHAR(60) NOT NULL, 
	movement_id VARCHAR(60) NOT NULL, 
	expense_type VARCHAR(30) NOT NULL, 
	amount NUMERIC(14, 4) NOT NULL, 
	concept VARCHAR(200) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_by VARCHAR(120) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	purchase_id VARCHAR(60), 
	cancelled_by VARCHAR(120), 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (owner, session_id, movement_id)
);

CREATE TABLE customers (
	owner VARCHAR(120) NOT NULL, 
	document VARCHAR(40) NOT NULL, 
	name VARCHAR(200), 
	document_type INTEGER, 
	email VARCHAR(200), 
	created_at TIMESTAMP WITH TIME ZONE, 
	created_by VARCHAR(120), 
	last_invoiced_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (owner, document)
);

CREATE TABLE parameters (
	name VARCHAR(120) NOT NULL, 
	value TEXT NOT NULL, 
	description TEXT, 
	PRIMARY KEY (name)
);
