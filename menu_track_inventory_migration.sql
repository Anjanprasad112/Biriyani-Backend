BEGIN;


-- ============================================================
-- 1. ADD OPTIONAL INVENTORY TRACKING
-- ============================================================

ALTER TABLE menu
ADD COLUMN IF NOT EXISTS track_inventory BOOLEAN;


-- Any existing rows should default to not tracking stock.
UPDATE menu
SET track_inventory = FALSE
WHERE track_inventory IS NULL;


ALTER TABLE menu
ALTER COLUMN track_inventory SET DEFAULT FALSE;


ALTER TABLE menu
ALTER COLUMN track_inventory SET NOT NULL;


-- Clean up any previous experimental -1 values if they exist.
UPDATE menu
SET inventory = 0
WHERE inventory < 0;


-- ============================================================
-- 2. DEACTIVATE OLD / TEST MENU ITEMS
--
-- Nothing is deleted because historical orders may still
-- reference their IDs.
-- ============================================================

UPDATE menu
SET
    is_active = FALSE,
    updated_at = NOW();


-- ============================================================
-- 3. UPDATE EXISTING MATCHING REAL MENU ITEMS
--
-- If a matching name already exists, reuse the oldest row
-- instead of creating a duplicate.
-- ============================================================

WITH seed(name, price) AS (
    VALUES
        ('Veg Dum Biryani - Half', 90),
        ('Veg Dum Biryani - Full', 130),

        ('Egg Dum Biryani - Half', 110),
        ('Egg Dum Biryani - Full', 150),

        ('Chicken Dum Biryani - Half', 120),
        ('Chicken Dum Biryani - Full', 160),

        ('Mutton Dum Biryani - Half', 200),

        ('Chicken 65 - 100 g', 60),
        ('Chicken 65 - 200 g', 120),
        ('Chicken 65 - 250 g', 150),
        ('Chicken 65 - 500 g', 280),
        ('Chicken 65 - 1 kg', 550),

        ('Chicken 65 - 80 g Pack', 50),
        ('Chicken 65 - 160 g Pack', 100),
        ('Chicken 65 - 330 g Pack', 200),
        ('Chicken 65 - 530 g Pack', 300),
        ('Chicken 65 - 700 g Pack', 400),
        ('Chicken 65 - 860 g Pack', 500)
)

UPDATE menu AS m
SET
    price = seed.price,
    inventory = 0,
    track_inventory = FALSE,
    is_active = TRUE,
    updated_at = NOW()

FROM seed

WHERE m.id = (
    SELECT MIN(m2.id)
    FROM menu AS m2
    WHERE LOWER(m2.name) = LOWER(seed.name)
);


-- ============================================================
-- 4. INSERT MENU ITEMS THAT DO NOT ALREADY EXIST
-- ============================================================

WITH seed(name, price) AS (
    VALUES
        ('Veg Dum Biryani - Half', 90),
        ('Veg Dum Biryani - Full', 130),

        ('Egg Dum Biryani - Half', 110),
        ('Egg Dum Biryani - Full', 150),

        ('Chicken Dum Biryani - Half', 120),
        ('Chicken Dum Biryani - Full', 160),

        ('Mutton Dum Biryani - Half', 200),

        ('Chicken 65 - 100 g', 60),
        ('Chicken 65 - 200 g', 120),
        ('Chicken 65 - 250 g', 150),
        ('Chicken 65 - 500 g', 280),
        ('Chicken 65 - 1 kg', 550),

        ('Chicken 65 - 80 g Pack', 50),
        ('Chicken 65 - 160 g Pack', 100),
        ('Chicken 65 - 330 g Pack', 200),
        ('Chicken 65 - 530 g Pack', 300),
        ('Chicken 65 - 700 g Pack', 400),
        ('Chicken 65 - 860 g Pack', 500)
)

INSERT INTO menu (
    name,
    price,
    inventory,
    track_inventory,
    is_active
)

SELECT
    seed.name,
    seed.price,
    0,
    FALSE,
    TRUE

FROM seed

WHERE NOT EXISTS (
    SELECT 1
    FROM menu AS existing
    WHERE LOWER(existing.name) = LOWER(seed.name)
);


COMMIT;