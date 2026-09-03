from multiprocessing import Process
import psycopg
import os





def worker(conn):
    print("here")
if __name__=="__main__":
    # define conn
    conn = psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "ticket_db"),
        user=os.getenv("DB_USER", "ticket_user"),
        password=os.getenv("DB_PASSWORD", "ticket_password"),
        row_factory=psycopg.rows.dict_row,
        autocommit=True
    )
    worker_number=int(os.getenv("WORKERS",4))
    for i in range(worker_number):
        p=Process(target=worker, args=(conn,))
        p.run()

        