-- Rebuild serial_no for rows that used the old EVENT/SUBJECT/COURSE middle segment.
-- Run after deploying the updated serial_no_service.py logic.
-- Requires MySQL 8+ with a JSON helper or run the Python one-liner on the app server instead.

-- Quick fix for EVENT literal (event contexts, Aug 2026 example — adjust MMYY per context):
UPDATE certificate_participants cp
JOIN certificate_training_contexts ctc ON ctc.id = cp.training_context_id
SET cp.serial_no = CONCAT(
    ctc.home_code,
    '/',
    COALESCE(ctc.invited_code, ctc.home_code),
    '/',
    DATE_FORMAT(ctc.start_date, '%m%y'),
    '/',
    cp.id
)
WHERE cp.deleted_at IS NULL
  AND ctc.training_type = 'event'
  AND (cp.serial_no LIKE '%/EVENT/%' OR cp.serial_no IS NULL);

-- Subject/course rows: replace /SUBJECT/ or /COURSE/ with MMYY if no subject code available;
-- re-run POST add for new rows to pick up subject.code automatically when possible.

SELECT 'certificate_participants serial_no backfill complete (event rows)' AS message;
