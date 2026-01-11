# Primary Device Race Condition Fix

## Problem

Multiple devices for the same user were being marked as `is_primary = 1` simultaneously, violating the business rule that only one device per user should be primary.

### Root Cause

Race conditions in two methods:

1. **`check_device_access` method** (lines 119-123):
   - Used a check-then-act pattern: check if primary exists, then set current device as primary
   - Two concurrent requests could both see "no primary device" and both set themselves as primary

2. **`update_device_status` method** (lines 156-165):
   - While it tried to set all others to False first, there was still a window where concurrent requests could cause issues
   - No row-level locking to prevent concurrent modifications

### Example Scenario

```
Time    Request A                          Request B
----    ---------                          ---------
T1      Check for primary → None
T2                                    Check for primary → None
T3      Set device A as primary
T4                                    Set device B as primary
T5      Commit → device A is primary
T6                                    Commit → device B is primary
Result: Both devices are primary! ❌
```

## Solution

### 1. Code Fixes

#### Fixed `check_device_access` method:
- Added `with_for_update()` to lock device rows during the check
- Made the operation atomic by:
  1. Locking the target device
  2. Setting all other devices to non-primary in one atomic UPDATE
  3. Double-checking with a locked query before setting primary
  4. Using proper transaction rollback on conflicts

#### Fixed `update_device_status` method:
- Added `with_for_update()` to lock the device row
- Made the operation atomic by:
  1. Locking the target device
  2. Setting all other devices to non-primary in one atomic UPDATE
  3. Double-checking with a locked query
  4. Rolling back if another device is still primary

### 2. Database-Level Protection

Created database triggers to prevent multiple primary devices:
- **`check_single_primary_device_before_insert`**: Prevents inserting a new primary device if one already exists
- **`check_single_primary_device_before_update`**: Prevents updating a device to primary if another is already primary

### 3. Data Cleanup

Created SQL script to fix existing duplicate primary devices:
- For each user with multiple primary devices, keeps only the most recently used one
- Sets all others to `is_primary = 0`

## Files Modified

1. **`auth/services/device_fingerprint_service.py`**:
   - Fixed `check_device_access` method with proper locking
   - Fixed `update_device_status` method with proper locking

2. **`migrations/fix_duplicate_primary_devices.sql`**:
   - SQL script to fix existing duplicate primary devices

3. **`migrations/add_unique_primary_device_constraint.sql`**:
   - Database triggers to prevent future duplicates

## Deployment Steps

1. **Fix existing data**:
   ```bash
   mysql -u ocpac -p ocpac < migrations/fix_duplicate_primary_devices.sql
   ```

2. **Add database triggers**:
   ```bash
   mysql -u ocpac -p ocpac < migrations/add_unique_primary_device_constraint.sql
   ```

3. **Deploy code changes**:
   - Deploy the updated `device_fingerprint_service.py`
   - Restart the application

4. **Verify**:
   ```sql
   -- Check for any remaining duplicates
   SELECT user_id, COUNT(*) as primary_count
   FROM user_devices
   WHERE is_primary = 1 AND is_active = 1
   GROUP BY user_id
   HAVING COUNT(*) > 1;
   ```
   This should return no rows.

## Testing

To test the fix:

1. **Test concurrent requests**:
   - Use a tool like `ab` (Apache Bench) or `wrk` to send concurrent requests
   - Verify only one device becomes primary

2. **Test database triggers**:
   ```sql
   -- This should fail
   UPDATE user_devices 
   SET is_primary = 1 
   WHERE user_id = 4 AND visitor_id = 'test123';
   -- Should get error: "Only one primary device allowed per user"
   ```

## Technical Details

### Row-Level Locking

The `with_for_update()` method in SQLAlchemy:
- Locks the selected rows until the transaction commits
- Prevents other transactions from modifying the locked rows
- Works with MySQL/MariaDB's `SELECT ... FOR UPDATE` statement

### Atomic Operations

The fix uses atomic UPDATE statements:
```sql
UPDATE user_devices 
SET is_primary = 0 
WHERE user_id = ? AND is_active = 1 AND id != ?
```
This ensures all other devices are set to non-primary in a single database operation.

### Transaction Management

Proper rollback on conflicts:
- If a conflict is detected, the transaction is rolled back
- The operation fails gracefully with an error message
- No partial state is left in the database

## Prevention

The combination of:
1. Application-level locking (`with_for_update()`)
2. Database-level triggers
3. Atomic UPDATE operations

Ensures that even under high concurrency, only one device per user can be primary.

