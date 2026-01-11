ALTER TABLE subtopic_materials
ADD COLUMN processing_status VARCHAR(20) DEFAULT 'completed',
ADD COLUMN processing_progress INTEGER DEFAULT 100,
ADD COLUMN processing_error TEXT; 