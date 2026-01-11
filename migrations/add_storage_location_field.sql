-- Add storage_location field to subtopic_materials table
ALTER TABLE subtopic_materials 
ADD COLUMN storage_location ENUM('local', 'b2') DEFAULT 'local' 
COMMENT 'Indicates where the HLS files are stored: local or b2';

-- Update existing records to have storage_location = 'b2' if they have B2 paths
UPDATE subtopic_materials 
SET storage_location = 'b2' 
WHERE material_path LIKE 'hls/%' AND material_path != '';

-- Update records with empty paths to be 'local'
UPDATE subtopic_materials 
SET storage_location = 'local' 
WHERE material_path = '' OR material_path IS NULL;
