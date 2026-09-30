-- ROLLBACK — drops book sales + LMS book tables (destructive)
-- Run only if you need to undo scripts/add_books_* on a non-production database.
--
-- Usage:
--   mysql -u USER -p DB_NAME < scripts/rollback_books_and_sales_tables.sql
--
-- Order: child tables first.

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS book_order_items;
DROP TABLE IF EXISTS book_orders;
DROP TABLE IF EXISTS book_listings;
DROP TABLE IF EXISTS edition_prices;
DROP TABLE IF EXISTS book_access_grant_logs;
DROP TABLE IF EXISTS book_subject_links;

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'Books and sales tables dropped' AS message;
