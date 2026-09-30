-- Book store / sales tables (pricing, listings, orders)
-- Idempotent for MySQL 8+ — safe to run more than once on production.
-- Alembic equivalent: fm5e6f7a8b9c_add_book_sales_tables.py
--
-- Prerequisites:
--   - Run scripts/add_books_lms_tables.sql first (optional for sales-only, but recommended)
--   - Table `users` must exist
--
-- Usage:
--   mysql -u USER -p DB_NAME < scripts/add_book_sales_tables.sql

-- ---------------------------------------------------------------------------
-- edition_prices
-- ---------------------------------------------------------------------------
SET @table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'edition_prices'
);

SET @sql := IF(
    @table_exists = 0,
    'CREATE TABLE edition_prices (
        id BIGINT NOT NULL AUTO_INCREMENT,
        edition_reference_id VARCHAR(100) NOT NULL COMMENT ''LMS edition ref e.g. ED-000125-02'',
        new_buyer_price DECIMAL(12, 2) NOT NULL,
        previous_buyer_price DECIMAL(12, 2) NOT NULL,
        currency VARCHAR(10) NOT NULL DEFAULT ''TZS'',
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        effective_from DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        effective_to DATETIME NULL,
        created_by BIGINT NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        INDEX ix_edition_prices_id (id),
        INDEX idx_edition_prices_edition (edition_reference_id),
        INDEX idx_edition_prices_active (is_active),
        CONSTRAINT fk_edition_prices_created_by
            FOREIGN KEY (created_by) REFERENCES users (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''edition_prices already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- book_listings
-- ---------------------------------------------------------------------------
SET @table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'book_listings'
);

SET @sql := IF(
    @table_exists = 0,
    'CREATE TABLE book_listings (
        id BIGINT NOT NULL AUTO_INCREMENT,
        edition_reference_id VARCHAR(100) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT ''UNLISTED'',
        listed_at DATETIME NULL,
        listed_by BIGINT NULL,
        unlisted_at DATETIME NULL,
        unlisted_by BIGINT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uq_book_listings_edition (edition_reference_id),
        INDEX ix_book_listings_id (id),
        INDEX idx_book_listings_status (status),
        CONSTRAINT fk_book_listings_listed_by
            FOREIGN KEY (listed_by) REFERENCES users (id),
        CONSTRAINT fk_book_listings_unlisted_by
            FOREIGN KEY (unlisted_by) REFERENCES users (id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''book_listings already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- book_orders
-- ---------------------------------------------------------------------------
SET @table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'book_orders'
);

SET @sql := IF(
    @table_exists = 0,
    'CREATE TABLE book_orders (
        id BIGINT NOT NULL AUTO_INCREMENT,
        user_id BIGINT NOT NULL,
        order_number VARCHAR(50) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT ''pending'',
        total_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
        currency VARCHAR(10) NOT NULL DEFAULT ''TZS'',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME NULL,
        PRIMARY KEY (id),
        UNIQUE KEY uq_book_orders_order_number (order_number),
        INDEX ix_book_orders_id (id),
        INDEX idx_book_orders_user (user_id),
        INDEX idx_book_orders_status (status),
        CONSTRAINT fk_book_orders_user
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''book_orders already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- book_order_items
-- ---------------------------------------------------------------------------
SET @table_exists := (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'book_order_items'
);

SET @sql := IF(
    @table_exists = 0,
    'CREATE TABLE book_order_items (
        id BIGINT NOT NULL AUTO_INCREMENT,
        order_id BIGINT NOT NULL,
        book_reference_id VARCHAR(100) NOT NULL COMMENT ''LMS book ref e.g. BK-000125'',
        edition_reference_id VARCHAR(100) NOT NULL,
        quantity INT NOT NULL DEFAULT 1,
        unit_price DECIMAL(12, 2) NOT NULL,
        total_price DECIMAL(12, 2) NOT NULL,
        PRIMARY KEY (id),
        UNIQUE KEY uq_book_order_item_edition (order_id, edition_reference_id),
        INDEX ix_book_order_items_id (id),
        INDEX idx_book_order_items_book (book_reference_id),
        INDEX idx_book_order_items_edition (edition_reference_id),
        CONSTRAINT fk_book_order_items_order
            FOREIGN KEY (order_id) REFERENCES book_orders (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci',
    'SELECT ''book_order_items already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'Book sales tables migration complete' AS message;
