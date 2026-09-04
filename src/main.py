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
        # sequance creation: unimportant since it is just to match ticket structure
        cursor.execute("""
            CREATE SEQUENCE IF NOT EXISTS ticket_id_seq
            START 1001;
        """)
        # enums
        # block scripts to handle duplicate enums in case of restart
        cursor.execute("""
                    DO $$
                    BEGIN
                        CREATE TYPE processing_state as ENUM ('pending','processing','classified','failed');
                    EXCEPTION
                        WHEN duplicate_object THEN null;
                    END $$;
                """)
        cursor.execute("""
                    DO $$
                    BEGIN
                    CREATE TYPE categories as ENUM ('billing', 'technical', 'account', 'other');
                    EXCEPTION
                        WHEN duplicate_object THEN null;
                    END $$;
        """)
        cursor.execute("""
                    DO $$
                    BEGIN
                    CREATE TYPE priorities as ENUM  ('low', 'medium', 'high');
                    EXCEPTION
                        WHEN duplicate_object THEN null;
                    END $$;
        """)
        # table
        # was gonna go with 2 tables, but since relationship between the proposed tables (ticket and inference) would be 1 to 1 we can just merge them 
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY
                    DEFAULT ('t-' || nextval('ticket_id_seq')::TEXT),
                subject TEXT,
                body TEXT NOT NULL,
                status processing_state NOT NULL,
                category categories,
                priority priorities
            );
        """)
        # incase of restart and system shutting down with tickets mid processing
        # We clean them up by updating all mid pricessing tickets to be pending again
        cursor.execute("""
                    UPDATE tickets 
                    SET status='pending'
                    WHERE status='processing'
            """)

print("Database initialized successfully.")

conn.close()