import os
import psycopg


conn = psycopg.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "ticket_db"),
    user=os.getenv("DB_USER", "ticket_user"),
    password=os.getenv("DB_PASSWORD", "ticket_password")
)


with conn:
    with conn.cursor() as cursor:

        cursor.execute("""
            CREATE SEQUENCE IF NOT EXISTS ticket_id_seq
            START 1001;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY
                    DEFAULT ('t-' || nextval('ticket_id_seq')::TEXT),

                subject TEXT NOT NULL,
                body TEXT NOT NULL
            );
        """)


print("Database initialized successfully.")

conn.close()