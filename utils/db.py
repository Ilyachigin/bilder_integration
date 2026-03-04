import sqlite3
from datetime import datetime, timedelta, UTC
from typing import Any


class DatabaseStorage:

    def __init__(self, db_path="merchant_data.db"):#db_path="/usr/src/app/data/merchant_data.db"):
        self.db_path = db_path

    def insert_token(self, gateway_token: str, bearer_token: str, public_key: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO merchant_tokens (gateway_token, bearer_token, public_key, created_at)
                VALUES (?, ?, ?, ?);
            """, (gateway_token, bearer_token, public_key, datetime.now(UTC)))
            conn.commit()

    def get_token(self, gateway_token: str) -> tuple[tuple[Any, Any] | None, None]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                               SELECT bearer_token, public_key
                               FROM merchant_tokens
                               WHERE gateway_token = ?;
                               """, (gateway_token,)).fetchone()
            return (row[0], row[1]) if row else (None, None)

    def get_public_key(self, gateway_token: str) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                               SELECT public_key
                               FROM merchant_tokens
                               WHERE gateway_token = ?;
                               """, (gateway_token,)).fetchone()
            return row[0] if row else None

    def delete_old_tokens(self, days=14):
        cutoff = datetime.now(UTC) - timedelta(days=days)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM merchant_tokens
                WHERE created_at < ?;
            """, (cutoff,))
            conn.commit()

