import os

from sqlalchemy import create_engine, text


DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no esta configurada.")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def init_db():
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    role VARCHAR(20) NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS uploaded_sources (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    file_hash VARCHAR(64) UNIQUE NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.commit()


def save_message(role, message):
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO chat_history (role, message)
                VALUES (:role, :message)
                """
            ),
            {"role": role, "message": message},
        )
        conn.commit()


def get_history(limit=80):
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT role, message
                FROM chat_history
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return list(reversed(result.fetchall()))


def save_source(name, file_hash, content):
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO uploaded_sources (name, file_hash, content)
                VALUES (:name, :file_hash, :content)
                ON CONFLICT (file_hash)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    content = EXCLUDED.content
                """
            ),
            {"name": name, "file_hash": file_hash, "content": content},
        )
        conn.commit()


def get_sources(limit=20):
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT name, file_hash, content, created_at
                FROM uploaded_sources
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return result.fetchall()


def clear_history():
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM chat_history"))
        conn.commit()
