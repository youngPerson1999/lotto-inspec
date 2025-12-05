UPDATE users u
LEFT JOIN email_verification_tokens t ON t.user_id = u.id
SET u.is_verified = 1
WHERE u.is_verified = 0 AND t.id IS NULL;
