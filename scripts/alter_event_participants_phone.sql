-- event_participants: phone required + unique per event (table empty or backfill phones first)

ALTER TABLE event_participants
    MODIFY COLUMN phone VARCHAR(50) NOT NULL;

ALTER TABLE event_participants
    ADD INDEX idx_event_participants_phone (phone);

ALTER TABLE event_participants
    ADD UNIQUE KEY uq_event_participants_event_phone (event_id, phone);

SELECT 'event_participants phone migration complete' AS message;
