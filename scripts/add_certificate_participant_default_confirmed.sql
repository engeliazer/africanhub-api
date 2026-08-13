-- Default certificate_participants.confirmation_status to confirmed — idempotent MySQL 8+

ALTER TABLE certificate_participants
  MODIFY COLUMN confirmation_status VARCHAR(20) NOT NULL DEFAULT 'confirmed';

UPDATE certificate_participants
SET confirmation_status = 'confirmed'
WHERE confirmation_status = 'pending'
  AND deleted_at IS NULL;

SELECT 'certificate_participants default confirmation_status = confirmed' AS message;
