from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel,Field
from typing import Literal
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
    id: str = Field(min_length=1)
    subject: str | None = None
    body: str = Field(min_length=1)

@app.post("/tickets/", status_code=201)
def create_ticket(ticket: Ticket):
    if ticket.subject is None:
        try:
            created_ticket = conn.execute(
                """
                INSERT INTO tickets (id,body,status)
                VALUES (%s,%s,%s)
                RETURNING id,status,subject,body;
                """,
                ( ticket.id , ticket.body,'pending')
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate Ticket - Ticket ID {ticket.id} already exists"
            )

    else:  
        try:
            created_ticket = conn.execute(
                """
                INSERT INTO tickets (id,subject, body,status)
                VALUES (%s,%s, %s,%s)
                RETURNING id,status,subject,body;
                """,
                (ticket.id ,ticket.subject, ticket.body,'pending')
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate Ticket - Ticket ID {ticket.id} already exists"
            )

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
def get_tickets(
    category: Literal["billing", "technical", "account", "other"] | None = None,
    priority: Literal["low", "medium", "high"] | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    query = """
        SELECT *
        FROM tickets
    """

    conditions = []
    params = []

    if category is not None:
        conditions.append("category = %s")
        params.append(category)

    if priority is not None:
        conditions.append("priority = %s")
        params.append(priority)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += """
        ORDER BY id
        LIMIT %s
        OFFSET %s
    """

    params.extend([limit, offset])

    tickets = conn.execute(
        query,
        params
    ).fetchall()

    return tickets
