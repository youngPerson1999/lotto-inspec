ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_verified TINYINT(1) NOT NULL DEFAULT 0
        AFTER password_hash;
