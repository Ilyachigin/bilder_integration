PRAGMA auto_vacuum = FULL;

CREATE TABLE IF NOT EXISTS merchant_tokens (
    gateway_token TEXT PRIMARY KEY,
    bearer_token TEXT NOT NULL,
    public_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
