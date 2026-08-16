-- ============================================================
-- PROJECT B -> PROJECT A STYLE BACKEND MIGRATION
--
-- Run once against the EXISTING PostgreSQL database.
--
-- Existing WhatsApp / Razorpay tables are preserved.
-- ============================================================



-- ============================================================
-- MENU
-- ============================================================

ALTER TABLE menu
    ALTER COLUMN name SET NOT NULL,
    ALTER COLUMN price SET NOT NULL,
    ALTER COLUMN inventory SET NOT NULL,
    ADD COLUMN IF NOT EXISTS is_active
        BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS created_at
        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS updated_at
        TIMESTAMPTZ NOT NULL DEFAULT NOW();


ALTER TABLE menu
DROP CONSTRAINT IF EXISTS menu_price_non_negative;


ALTER TABLE menu
ADD CONSTRAINT menu_price_non_negative
CHECK (
    price >= 0
);


ALTER TABLE menu
DROP CONSTRAINT IF EXISTS menu_inventory_non_negative;


ALTER TABLE menu
ADD CONSTRAINT menu_inventory_non_negative
CHECK (
    inventory >= 0
);



-- ============================================================
-- ORDERS
-- ============================================================

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS created_at
        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    ADD COLUMN IF NOT EXISTS updated_at
        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    ADD COLUMN IF NOT EXISTS paid_at
        TIMESTAMPTZ,

    ADD COLUMN IF NOT EXISTS preparation_started_at
        TIMESTAMPTZ,

    ADD COLUMN IF NOT EXISTS estimated_ready_at
        TIMESTAMPTZ,

    ADD COLUMN IF NOT EXISTS ready_at
        TIMESTAMPTZ,

    ADD COLUMN IF NOT EXISTS completed_at
        TIMESTAMPTZ,

    ADD COLUMN IF NOT EXISTS status_reason
        TEXT;



-- ============================================================
-- SHOPS
-- ============================================================

CREATE TABLE IF NOT EXISTS shops (

    id INTEGER PRIMARY KEY,

    name VARCHAR(150) NOT NULL,

    timezone VARCHAR(100)
        NOT NULL
        DEFAULT 'Asia/Kolkata',

    is_active BOOLEAN
        NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW()
);



-- ============================================================
-- DEFAULT SHOP
-- ============================================================

INSERT INTO shops (
    id,
    name,
    timezone,
    is_active
)
VALUES (
    1,
    'Watave''s Biryani',
    'Asia/Kolkata',
    TRUE
)
ON CONFLICT (id)
DO NOTHING;



-- ============================================================
-- STAFF USERS
--
-- Existing Project B "users" table remains for
-- WhatsApp customers.
--
-- Staff accounts use a separate table.
-- ============================================================

CREATE TABLE IF NOT EXISTS staff_users (

    id SERIAL PRIMARY KEY,

    shop_id INTEGER NOT NULL
        REFERENCES shops(id)
        ON DELETE CASCADE,

    name VARCHAR(150) NOT NULL,

    email VARCHAR(255)
        NOT NULL
        UNIQUE,

    password_hash VARCHAR(255)
        NOT NULL,

    role VARCHAR(30)
        NOT NULL
        DEFAULT 'KITCHEN',

    is_active BOOLEAN
        NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW()
);



-- ============================================================
-- STAFF ROLE VALIDATION
-- ============================================================

ALTER TABLE staff_users
DROP CONSTRAINT IF EXISTS
staff_users_role_check;


ALTER TABLE staff_users
ADD CONSTRAINT
staff_users_role_check
CHECK (
    role IN (
        'OWNER',
        'MANAGER',
        'KITCHEN',
        'CASHIER'
    )
);



-- ============================================================
-- SHOP SETTINGS
-- ============================================================

CREATE TABLE IF NOT EXISTS shop_settings (

    shop_id INTEGER PRIMARY KEY
        REFERENCES shops(id)
        ON DELETE CASCADE,

    accepting_orders BOOLEAN
        NOT NULL
        DEFAULT TRUE,

    default_preparation_minutes INTEGER
        NOT NULL
        DEFAULT 20,

    warning_active_orders INTEGER
        NOT NULL
        DEFAULT 30,

    max_active_orders INTEGER
        NOT NULL
        DEFAULT 40,

    opening_time TIME,

    closing_time TIME,

    updated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW()
);



ALTER TABLE shop_settings
DROP CONSTRAINT IF EXISTS
shop_settings_preparation_positive;


ALTER TABLE shop_settings
ADD CONSTRAINT
shop_settings_preparation_positive
CHECK (
    default_preparation_minutes > 0
);



ALTER TABLE shop_settings
DROP CONSTRAINT IF EXISTS
shop_settings_warning_non_negative;


ALTER TABLE shop_settings
ADD CONSTRAINT
shop_settings_warning_non_negative
CHECK (
    warning_active_orders >= 0
);



ALTER TABLE shop_settings
DROP CONSTRAINT IF EXISTS
shop_settings_max_positive;


ALTER TABLE shop_settings
ADD CONSTRAINT
shop_settings_max_positive
CHECK (
    max_active_orders > 0
);



ALTER TABLE shop_settings
DROP CONSTRAINT IF EXISTS
shop_settings_warning_not_above_max;


ALTER TABLE shop_settings
ADD CONSTRAINT
shop_settings_warning_not_above_max
CHECK (
    warning_active_orders
    <= max_active_orders
);



-- ============================================================
-- DEFAULT SETTINGS
-- ============================================================

INSERT INTO shop_settings (
    shop_id,
    accepting_orders,
    default_preparation_minutes,
    warning_active_orders,
    max_active_orders
)
VALUES (
    1,
    TRUE,
    20,
    30,
    40
)
ON CONFLICT (shop_id)
DO NOTHING;



-- ============================================================
-- ORDER ITEMS
--
-- Existing orders.cart_items stays untouched for
-- WhatsApp/Razorpay compatibility.
--
-- This table is available for Project A style
-- reporting/order normalization later.
-- ============================================================

CREATE TABLE IF NOT EXISTS order_items (

    id SERIAL PRIMARY KEY,

    order_id VARCHAR(50)
        NOT NULL
        REFERENCES orders(order_id)
        ON DELETE CASCADE,

    menu_item_id INTEGER
        REFERENCES menu(id)
        ON DELETE SET NULL,

    item_name VARCHAR(200)
        NOT NULL,

    unit_price INTEGER
        NOT NULL,

    quantity INTEGER
        NOT NULL,

    line_total INTEGER
        NOT NULL,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW()
);



ALTER TABLE order_items
DROP CONSTRAINT IF EXISTS
order_items_unit_price_non_negative;


ALTER TABLE order_items
ADD CONSTRAINT
order_items_unit_price_non_negative
CHECK (
    unit_price >= 0
);



ALTER TABLE order_items
DROP CONSTRAINT IF EXISTS
order_items_quantity_positive;


ALTER TABLE order_items
ADD CONSTRAINT
order_items_quantity_positive
CHECK (
    quantity > 0
);



ALTER TABLE order_items
DROP CONSTRAINT IF EXISTS
order_items_line_total_non_negative;


ALTER TABLE order_items
ADD CONSTRAINT
order_items_line_total_non_negative
CHECK (
    line_total >= 0
);



-- ============================================================
-- ORDER STATUS HISTORY
-- ============================================================

CREATE TABLE IF NOT EXISTS
order_status_history (

    id SERIAL PRIMARY KEY,

    order_id VARCHAR(50)
        NOT NULL
        REFERENCES orders(order_id)
        ON DELETE CASCADE,

    old_status VARCHAR(50),

    new_status VARCHAR(50)
        NOT NULL,

    reason TEXT,

    changed_by_user_id INTEGER
        REFERENCES staff_users(id)
        ON DELETE SET NULL,

    changed_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW()
);



-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS
idx_orders_status
ON orders(status);


CREATE INDEX IF NOT EXISTS
idx_orders_created_at
ON orders(created_at DESC);


CREATE INDEX IF NOT EXISTS
idx_orders_paid_at
ON orders(paid_at DESC);


CREATE INDEX IF NOT EXISTS
idx_orders_status_created_at
ON orders(
    status,
    created_at DESC
);


CREATE INDEX IF NOT EXISTS
idx_orders_phone_number
ON orders(phone_number);


CREATE INDEX IF NOT EXISTS
idx_staff_users_shop_id
ON staff_users(shop_id);


CREATE INDEX IF NOT EXISTS
idx_order_items_order_id
ON order_items(order_id);


CREATE INDEX IF NOT EXISTS
idx_order_items_menu_item_id
ON order_items(menu_item_id);


CREATE INDEX IF NOT EXISTS
idx_order_status_history_order_id
ON order_status_history(order_id);


CREATE INDEX IF NOT EXISTS
idx_order_status_history_changed_at
ON order_status_history(
    changed_at DESC
);