CREATE TABLE IF NOT EXISTS analysis_snapshots (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(128) NOT NULL,
    max_draw_no INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result JSON NOT NULL,
    metadata_json JSON NULL,
    PRIMARY KEY (id),
    KEY ix_analysis_snapshots_name (name),
    KEY ix_analysis_snapshots_created_at (created_at)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
