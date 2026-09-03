from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg
import os


conn = psycopg.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "ticket_db"),
    user=os.getenv("DB_USER", "ticket_user"),
    password=os.getenv("DB_PASSWORD", "ticket_password"),
    row_factory=psycopg.rows.dict_row,
    autocommit=True
)


app = FastAPI()


class Ticket(BaseModel):
    subject: str | None = None
    body: str | None = None

@app.post("/tickets/", status_code=201)
# TODO error handling
def create_ticket(ticket: Ticket):

    created_ticket = conn.execute(
        """
        INSERT INTO tickets (subject, body,status)
        VALUES (%s, %s,%s)
        RETURNING id,status,subject,body;
        """,
        (ticket.subject, ticket.body,'pending')
    ).fetchone()

    return created_ticket

@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):

    ticket = conn.execute(
        """
        SELECT *
        FROM tickets
        WHERE id = %s;
        """,
        (ticket_id,)
    ).fetchone()

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    return ticket

@app.get("/tickets/")
def get_tickets():

    tickets = conn.execute(
        """
        SELECT *
        FROM tickets
        ORDER BY id;
        """
    ).fetchall()

    return tickets