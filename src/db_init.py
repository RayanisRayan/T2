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
        # leased_until and lease_version are a solution for worker crashes
        # a lease_until makes it so that workers have a set duration to work within
        # if longer time is taken another worker will claim it
        # lease_version will hanle race conditions if somehow
        # multiple workers claimed the same ticket after 
        # lease was up and then both managed to geenrate an
        # update
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                subject TEXT,
                body TEXT NOT NULL,
                status processing_state NOT NULL DEFAULT 'pending',
                category categories,
                summary TEXT,
                priority priorities,
                leased_until TIMESTAMPTZ,
                lease_version BIGINT NOT NULL DEFAULT 0 
            );
        """)


print("Database initialized successfully.")

conn.close()