-- Migration: Add VdoCipher columns to subtopic_materials table
-- Run this to add video integration fields

-- Add VdoCipher video ID
ALTER TABLE subtopic_materials 
ADD COLUMN IF NOT EXISTS vdocipher_video_id VARCHAR(255) NULL;

-- Add video processing status
ALTER TABLE subtopic_materials 
ADD COLUMN IF NOT EXISTS video_status VARCHAR(50) NULL 
DEFAULT 'pending' 
COMMENT 'Values: pending, processing, ready, failed';

-- Add video duration in seconds
ALTER TABLE subtopic_materials 
ADD COLUMN IF NOT EXISTS video_duration INTEGER NULL 
COMMENT 'Duration in seconds';

-- Add video thumbnail URL
ALTER TABLE subtopic_materials 
ADD COLUMN IF NOT EXISTS video_thumbnail_url TEXT NULL;

-- Add video poster URL
ALTER TABLE subtopic_materials 
ADD COLUMN IF NOT EXISTS video_poster_url TEXT NULL;

-- Add flag for DRM requirement (for hybrid approach)
ALTER TABLE subtopic_materials 
ADD COLUMN IF NOT EXISTS requires_drm BOOLEAN DEFAULT FALSE 
COMMENT 'TRUE = Use VdoCipher, FALSE = Use HLS';

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_vdocipher_video_id 
ON subtopic_materials(vdocipher_video_id);

CREATE INDEX IF NOT EXISTS idx_video_status 
ON subtopic_materials(video_status);

-- Show results
SELECT 
    COLUMN_NAME, 
    DATA_TYPE, 
    IS_NULLABLE, 
    COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'subtopic_materials' 
AND COLUMN_NAME LIKE '%video%' OR COLUMN_NAME LIKE '%vdocipher%';

