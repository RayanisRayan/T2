#!/usr/bin/env python3

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib import request, error


DEFAULT_URL = "http://localhost:8000/tickets/"
DEFAULT_TIMEOUT = 30


def load_tickets(csv_path: str) -> list[dict]:
    tickets = []

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {"id", "subject", "body"}

        if reader.fieldnames is None:
            raise ValueError("CSV file has no header.")

        missing = required_columns - set(reader.fieldnames)

        if missing:
            raise ValueError(
                f"CSV is missing required column(s): {', '.join(sorted(missing))}"
            )

        for row_number, row in enumerate(reader, start=2):
            ticket_id = (row.get("id") or "").strip()
            subject = row.get("subject") or ""
            body = row.get("body") or ""

            if not ticket_id:
                raise ValueError(f"Row {row_number}: id is empty.")

            if not body.strip():
                raise ValueError(
                    f"Row {row_number} ({ticket_id}): body is empty."
                )

            tickets.append(
                {
                    "id": ticket_id,
                    "subject": subject,
                    "body": body,
                }
            )

    return tickets


def send_ticket(ticket: dict, url: str, timeout: int) -> dict:
    payload = {
        "id": ticket["id"],
        "subject": ticket["subject"] or None,
        "body": ticket["body"],
    }

    encoded_payload = json.dumps(payload).encode("utf-8")

    req = request.Request(
        url=url,
        data=encoded_payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    started = time.perf_counter()

    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw_body = response.read().decode("utf-8")
            elapsed = time.perf_counter() - started

            try:
                response_body = json.loads(raw_body) if raw_body else None
            except json.JSONDecodeError:
                response_body = raw_body

            return {
                "id": ticket["id"],
                "success": 200 <= response.status < 300,
                "status": response.status,
                "elapsed": elapsed,
                "response": response_body,
            }

    except error.HTTPError as exc:
        elapsed = time.perf_counter() - started
        raw_body = exc.read().decode("utf-8", errors="replace")

        try:
            response_body = json.loads(raw_body) if raw_body else None
        except json.JSONDecodeError:
            response_body = raw_body

        return {
            "id": ticket["id"],
            "success": False,
            "status": exc.code,
            "elapsed": elapsed,
            "response": response_body,
        }

    except Exception as exc:
        elapsed = time.perf_counter() - started

        return {
            "id": ticket["id"],
            "success": False,
            "status": None,
            "elapsed": elapsed,
            "response": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send customer-support tickets from a CSV file to the ticket API."
    )

    parser.add_argument(
        "csv_file",
        help="Path to the CSV file containing id, subject, and body columns.",
    )

    parser.add_argument(
        "-n",
        "--concurrency",
        type=int,
        default=1,
        help="Maximum number of concurrent HTTP requests. Default: 1.",
    )

    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Ticket API endpoint. Default: {DEFAULT_URL}",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Per-request timeout in seconds. Default: {DEFAULT_TIMEOUT}.",
    )

    args = parser.parse_args()

    if args.concurrency < 1:
        parser.error("-n/--concurrency must be at least 1.")

    if args.timeout < 1:
        parser.error("--timeout must be at least 1 second.")

    try:
        tickets = load_tickets(args.csv_file)
    except (OSError, ValueError) as exc:
        print(f"Failed to load CSV: {exc}", file=sys.stderr)
        return 1

    if not tickets:
        print("No tickets found in CSV.")
        return 0

    print(
        f"Sending {len(tickets)} tickets to {args.url} "
        f"with concurrency={args.concurrency}"
    )

    started = time.perf_counter()
    results = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = {
            executor.submit(send_ticket, ticket, args.url, args.timeout): ticket
            for ticket in tickets
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            status = result["status"] if result["status"] is not None else "ERROR"
            outcome = "OK" if result["success"] else "FAIL"

            print(
                f"[{outcome}] {result['id']} "
                f"status={status} "
                f"time={result['elapsed']:.3f}s "
                f"response={result['response']}"
            )

    total_elapsed = time.perf_counter() - started
    successful = sum(result["success"] for result in results)
    failed = len(results) - successful

    print()
    print("Run complete")
    print(f"  Total:      {len(results)}")
    print(f"  Successful: {successful}")
    print(f"  Failed:     {failed}")
    print(f"  Elapsed:    {total_elapsed:.3f}s")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
