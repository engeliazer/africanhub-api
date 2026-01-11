# Device Access Control Fix

## Problem

The `check_device_access` method was automatically promoting non-primary devices to primary when a user had no primary device. This violated the intended access control:

**Unwanted Behavior:**
- Non-primary device tries to access materials
- System checks: "No primary device exists"
- System automatically makes the requesting device primary
- Device gains access

**Intended Behavior:**
- Non-primary device tries to access materials
- System checks: "Is this device primary?"
- If NO → Deny access (even if user has no primary device)
- Primary status should only be set:
  1. When creating the user's **first device** (automatic)
  2. Via explicit API call to set a device as primary (manual)

## Solution

### 1. Fixed `check_device_access` Method

**Before:**
- Checked if device is primary
- If not primary, checked if user has any primary device
- If no primary device exists, automatically promoted current device to primary
- This allowed unauthorized access

**After:**
- Only checks if device exists and if it's primary
- Returns `True` only if device is already primary
- Returns `False` for all non-primary devices
- **Does NOT modify device status** - read-only check

```python
def check_device_access(self, user_id: int, visitor_id: str) -> bool:
    """
    Check if a device is allowed to access materials.
    Only returns True if the device is already marked as primary.
    Does NOT automatically promote devices to primary.
    """
    device = self.db.query(UserDevice).filter(...).first()
    if not device:
        return False
    return device.is_primary  # Simple check, no modifications
```

### 2. Updated `get_or_create_device` Method

**Added logic to set primary status only during device creation:**

- When creating a **new device** (not updating existing):
  - Check if this is the user's first device (with row-level locking to prevent race conditions)
  - If first device → Set `is_primary = True`
  - If not first device → Set `is_primary = False` (default)

- When updating an **existing device**:
  - Does NOT change `is_primary` status
  - Only updates `last_used`, fingerprint data, etc.

```python
# Create new device
existing_devices = self.db.query(UserDevice).filter(
    UserDevice.user_id == user_id,
    UserDevice.is_active == True
).with_for_update().all()  # Lock to prevent race conditions

# If this is the first device for this user, make it primary
if len(existing_devices) == 0:
    device_data['is_primary'] = True
```

## Access Control Flow

### Scenario 1: New User, First Device
1. User registers/logs in
2. Device fingerprint sent → `get_or_create_device` called
3. No existing devices → Device created with `is_primary = True`
4. `check_device_access` called → Device is primary → **Access granted** ✅

### Scenario 2: Existing User, New Device (User Already Has Primary)
1. User logs in from new device
2. Device fingerprint sent → `get_or_create_device` called
3. User has existing devices → Device created with `is_primary = False`
4. `check_device_access` called → Device is NOT primary → **Access denied** ✅

### Scenario 3: Existing User, Existing Non-Primary Device
1. User tries to access materials from non-primary device
2. `get_or_create_device` called → Returns existing device (status unchanged)
3. `check_device_access` called → Device is NOT primary → **Access denied** ✅

### Scenario 4: Existing User, Existing Primary Device
1. User accesses materials from primary device
2. `get_or_create_device` called → Returns existing device (is_primary = True)
3. `check_device_access` called → Device is primary → **Access granted** ✅

### Scenario 5: User Explicitly Sets New Primary Device
1. User calls API: `PUT /api/user-devices/{device_id}/set-primary`
2. `update_device_status` called → Sets new device as primary, demotes old one
3. `check_device_access` called → Device is now primary → **Access granted** ✅

## Files Modified

- **`auth/services/device_fingerprint_service.py`**:
  - `check_device_access`: Removed auto-promotion logic, now read-only check
  - `get_or_create_device`: Added logic to set primary only for first device

## Testing

To verify the fix works correctly:

1. **Test non-primary device access:**
   ```bash
   # Try to access materials from a non-primary device
   # Should return 403 Forbidden or similar error
   ```

2. **Test first device creation:**
   ```bash
   # Create a new user account
   # First device should automatically be set as primary
   # Verify in database: SELECT * FROM user_devices WHERE user_id = ?;
   ```

3. **Test explicit primary change:**
   ```bash
   # Call: PUT /api/user-devices/{device_id}/set-primary
   # Verify old device is demoted and new device is promoted
   ```

## Database Verification

Check device status:
```sql
SELECT user_id, visitor_id, is_primary, is_active, last_used
FROM user_devices
WHERE user_id = 4
ORDER BY last_used DESC;
```

Expected result:
- Only ONE device per user should have `is_primary = 1`
- Non-primary devices should have `is_primary = 0`

## Summary

The fix ensures:
- ✅ Non-primary devices are **denied access** (no auto-promotion)
- ✅ Only **primary devices** can access materials
- ✅ First device for a user is **automatically set as primary** during creation
- ✅ Subsequent devices are created as **non-primary**
- ✅ Primary status can only be changed via **explicit API call**
- ✅ Race conditions prevented with proper database locking

