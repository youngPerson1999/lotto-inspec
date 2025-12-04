CREATE TABLE IF NOT EXISTS user_recommendations (
    id INT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(64) NOT NULL,
    strategy VARCHAR(64) NOT NULL,
    numbers JSON NOT NULL,
    draw_no INT NOT NULL,
    evaluation JSON DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    evaluated_at DATETIME DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_draw_strategy (user_id, draw_no, strategy),
    KEY ix_user_recommendations_user_id (user_id),
    KEY ix_user_recommendations_draw_no (draw_no),
    CONSTRAINT fk_user_recommendations_users
        FOREIGN KEY (user_id) REFERENCES users (user_id)
        ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
