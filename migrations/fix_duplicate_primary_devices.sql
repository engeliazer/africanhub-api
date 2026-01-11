-- Fix duplicate primary devices
-- This script ensures only one device per user has is_primary = 1
-- It keeps the most recently used device as primary (or the one with the highest ID if tied)

-- For each user with multiple primary devices, keep only the one with:
-- 1. The most recent last_used timestamp, or
-- 2. The highest ID if multiple devices have the same last_used

UPDATE user_devices ud1
INNER JOIN (
    -- Find the device to keep for each user (most recent last_used, then highest ID)
    SELECT 
        ud_inner.user_id,
        MAX(ud_inner.id) as keep_id
    FROM user_devices ud_inner
    INNER JOIN (
        -- Find the maximum last_used for each user with multiple primary devices
        SELECT 
            user_id,
            MAX(last_used) as max_last_used
        FROM user_devices
        WHERE is_primary = 1 
          AND is_active = 1
        GROUP BY user_id
        HAVING COUNT(*) > 1
    ) max_dates ON ud_inner.user_id = max_dates.user_id
    WHERE ud_inner.is_primary = 1 
      AND ud_inner.is_active = 1
      AND ud_inner.last_used = max_dates.max_last_used
    GROUP BY ud_inner.user_id
) ud2 ON ud1.user_id = ud2.user_id
SET ud1.is_primary = 0
WHERE ud1.is_primary = 1 
  AND ud1.is_active = 1
  AND ud1.id != ud2.keep_id;

-- Verify the fix - should return no rows
SELECT 
    user_id, 
    COUNT(*) as primary_count,
    GROUP_CONCAT(visitor_id ORDER BY id) as visitor_ids
FROM user_devices
WHERE is_primary = 1 
  AND is_active = 1
GROUP BY user_id
HAVING COUNT(*) > 1;

-- If the above query returns no rows, the fix was successful

