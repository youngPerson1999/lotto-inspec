CREATE TABLE IF NOT EXISTS recommendation_snapshots (
    id INT NOT NULL AUTO_INCREMENT,
    strategy VARCHAR(64) NOT NULL,
    draw_no INT DEFAULT NULL,
    result JSON NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_strategy_draw_no (strategy, draw_no)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
