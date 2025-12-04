CREATE TABLE IF NOT EXISTS user_tickets (
    id INT NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(64) NOT NULL,
    draw_no INT NOT NULL,
    numbers JSON NOT NULL,
    evaluation JSON NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_user_tickets_user_id (user_id),
    KEY ix_user_tickets_draw_no (draw_no),
    KEY ix_user_tickets_created_at (created_at),
    CONSTRAINT fk_user_tickets_users
        FOREIGN KEY (user_id) REFERENCES users (user_id)
        ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
