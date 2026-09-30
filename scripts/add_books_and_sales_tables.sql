-- Combined runner: all books + book sales tables
-- Idempotent. Does NOT run Alembic.
--
-- Recommended usage from repo root (two commands):
--   mysql -h HOST -u USER -p DB_NAME < scripts/add_books_lms_tables.sql
--   mysql -h HOST -u USER -p DB_NAME < scripts/add_book_sales_tables.sql
--
-- Or paste/run the two files above in order in your SQL client.
--
-- Optional Alembic stamp after both succeed:
--   UPDATE alembic_version SET version_num = 'fm5e6f7a8b9c';

SELECT 'Run add_books_lms_tables.sql then add_book_sales_tables.sql (see file header)' AS message;
