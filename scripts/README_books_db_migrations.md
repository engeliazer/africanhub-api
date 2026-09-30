# Books & sales — manual DB migration (production)

Use these SQL scripts when you **do not** want to run Alembic against production.

## Order

1. **LMS / reading** (optional if you only need the store):
   ```bash
   mysql -h HOST -u USER -p DB_NAME < scripts/add_books_lms_tables.sql
   ```

2. **Store / sales**:
   ```bash
   mysql -h HOST -u USER -p DB_NAME < scripts/add_book_sales_tables.sql
   ```

Run both files in order (same as Alembic chain `fl4d5e6f7a8b` → `fm5e6f7a8b9c`):

```bash
mysql -h HOST -u USER -p DB_NAME < scripts/add_books_lms_tables.sql
mysql -h HOST -u USER -p DB_NAME < scripts/add_book_sales_tables.sql
```

## Tables created

| Script | Tables |
|--------|--------|
| `add_books_lms_tables.sql` | `book_subject_links`, `book_access_grant_logs` |
| `add_book_sales_tables.sql` | `edition_prices`, `book_listings`, `book_orders`, `book_order_items` |

All scripts are **idempotent** (skip create if the table already exists).

## Alembic revision (optional)

If other environments use Alembic and you need the version row to match after manual SQL on prod:

```sql
-- Check current
SELECT * FROM alembic_version;

-- After both scripts applied, head should be:
UPDATE alembic_version SET version_num = 'fm5e6f7a8b9c';
```

Only do this if `alembic_version` exists and your team agrees prod is stamped manually.

## Rollback

**Destructive** — deletes data:

```bash
mysql -h HOST -u USER -p DB_NAME < scripts/rollback_books_and_sales_tables.sql
```

## Verify

```sql
SHOW TABLES LIKE 'book%';
SHOW TABLES LIKE 'edition_prices';

DESCRIBE book_listings;
DESCRIBE edition_prices;
```
