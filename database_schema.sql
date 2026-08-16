-- ============================================================
-- WATAVE'S BIRYANI
-- FRESH SUPABASE DATABASE SCHEMA
--
-- Supports:
--   - Project A style FastAPI backend
--   - Project B WhatsApp ordering
--   - Project B Razorpay payment flow
--
-- Run ONCE on the new Supabase PostgreSQL database.
-- ============================================================


BEGIN;


-- ============================================================
-- 1. SHOPS
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
ON CONFLICT (id) DO NOTHING;



-- ============================================================
-- 2. WHATSAPP CUSTOMERS
--
-- Project B already expects:
--
-- users(phone_number)
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    phone_number VARCHAR(32) PRIMARY KEY
);



-- ============================================================
-- 3. WHATSAPP CUSTOMER SESSIONS
--
-- Project B expects:
--
-- phone_number
-- step
-- order_type
-- table_number
-- temp_item_id
-- cart
-- ============================================================

CREATE TABLE IF NOT EXISTS sessions (
    phone_number VARCHAR(32) PRIMARY KEY
        REFERENCES users(phone_number)
        ON DELETE CASCADE,

    step VARCHAR(100)
        NOT NULL,

    order_type VARCHAR(50),

    table_number VARCHAR(50),

    temp_item_id INTEGER,

    cart JSONB
        NOT NULL
        DEFAULT '[]'::jsonb
);



-- ============================================================
-- 4. MENU
-- ============================================================

CREATE TABLE IF NOT EXISTS menu (
    id SERIAL PRIMARY KEY,

    name VARCHAR(200)
        NOT NULL,

    price INTEGER
        NOT NULL,

    inventory INTEGER
        NOT NULL
        DEFAULT 0,

    is_active BOOLEAN
        NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW(),

    CONSTRAINT menu_price_non_negative
        CHECK (
            price >= 0
        ),

    CONSTRAINT menu_inventory_non_negative
        CHECK (
            inventory >= 0
        )
);



-- ============================================================
-- 5. ORDERS
--
-- IMPORTANT:
--
-- Keep the Project B columns:
--
-- order_id
-- phone_number
-- order_type
-- table_number
-- total_amount
-- cart_items
-- status
--
-- because its WhatsApp/Razorpay code uses them directly.
-- ============================================================

CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(50)
        PRIMARY KEY,

    phone_number VARCHAR(32)
        NOT NULL,

    order_type VARCHAR(50)
        NOT NULL,

    table_number VARCHAR(50),

    total_amount INTEGER
        NOT NULL,

    cart_items JSONB
        NOT NULL
        DEFAULT '[]'::jsonb,

    status VARCHAR(50)
        NOT NULL
        DEFAULT 'Pending',

    status_reason TEXT,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW(),

    updated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW(),

    paid_at TIMESTAMPTZ,

    preparation_started_at TIMESTAMPTZ,

    estimated_ready_at TIMESTAMPTZ,

    ready_at TIMESTAMPTZ,

    completed_at TIMESTAMPTZ,

    CONSTRAINT orders_total_non_negative
        CHECK (
            total_amount >= 0
        ),

    CONSTRAINT orders_status_check
        CHECK (
            status IN (
                'Pending',
                'Paid',
                'Preparation',
                'Ready',
                'Collected',
                'Cancelled',
                'Rejected'
            )
        )
);



-- ============================================================
-- 6. STAFF USERS
--
-- Separate from WhatsApp customer "users".
--
-- Roles:
--
-- OWNER
-- MANAGER
-- KITCHEN
-- CASHIER
-- ============================================================

CREATE TABLE IF NOT EXISTS staff_users (
    id SERIAL PRIMARY KEY,

    shop_id INTEGER
        NOT NULL
        REFERENCES shops(id)
        ON DELETE CASCADE,

    name VARCHAR(150)
        NOT NULL,

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
        DEFAULT NOW(),

    CONSTRAINT staff_users_role_check
        CHECK (
            role IN (
                'OWNER',
                'MANAGER',
                'KITCHEN',
                'CASHIER'
            )
        )
);



-- ============================================================
-- 7. SHOP SETTINGS
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
        DEFAULT NOW(),

    CONSTRAINT shop_settings_prep_positive
        CHECK (
            default_preparation_minutes > 0
        ),

    CONSTRAINT shop_settings_warning_non_negative
        CHECK (
            warning_active_orders >= 0
        ),

    CONSTRAINT shop_settings_max_positive
        CHECK (
            max_active_orders > 0
        ),

    CONSTRAINT shop_settings_warning_below_max
        CHECK (
            warning_active_orders
            <= max_active_orders
        )
);


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
ON CONFLICT (shop_id) DO NOTHING;



-- ============================================================
-- 8. ORDER ITEMS
--
-- We keep orders.cart_items for compatibility with
-- Project B.
--
-- order_items gives us Project A-style structured reporting.
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
        DEFAULT NOW(),

    CONSTRAINT order_items_price_non_negative
        CHECK (
            unit_price >= 0
        ),

    CONSTRAINT order_items_quantity_positive
        CHECK (
            quantity > 0
        ),

    CONSTRAINT order_items_total_non_negative
        CHECK (
            line_total >= 0
        )
);



-- ============================================================
-- 9. ORDER STATUS HISTORY
-- ============================================================

CREATE TABLE IF NOT EXISTS order_status_history (
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
-- 10. INDEXES
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
idx_orders_phone_number
ON orders(phone_number);


CREATE INDEX IF NOT EXISTS
idx_orders_status_created_at
ON orders(
    status,
    created_at DESC
);


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


COMMIT;