#!/usr/bin/env python3

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib import request, error
from urllib.parse import quote


DEFAULT_URL = "http://localhost:8000/tickets/"
DEFAULT_TIMEOUT = 30
VALIDATION_WAIT = 30

VALID_CATEGORIES = {
    "billing",
    "technical",
    "account",
    "other",
}

VALID_PRIORITIES = {
    "low",
    "medium",
    "high",
}

VALID_EXPECTED_STATUSES = {
    "classified",
    "failed",
}


def load_tickets(csv_path: str) -> list[dict]:
    tickets = []

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {
            "id",
            "subject",
            "body",
            "expected_status",
        }

        if reader.fieldnames is None:
            raise ValueError("CSV file has no header.")

        missing = required_columns - set(reader.fieldnames)

        if missing:
            raise ValueError(
                f"CSV is missing required column(s): "
                f"{', '.join(sorted(missing))}"
            )

        for row_number, row in enumerate(reader, start=2):
            ticket_id = (row.get("id") or "").strip()
            subject = row.get("subject") or ""
            body = row.get("body") or ""
            expected_status = (
                row.get("expected_status") or ""
            ).strip().lower()

            if not ticket_id:
                raise ValueError(
                    f"Row {row_number}: id is empty."
                )

            if not body.strip():
                raise ValueError(
                    f"Row {row_number} ({ticket_id}): body is empty."
                )

            if expected_status not in VALID_EXPECTED_STATUSES:
                raise ValueError(
                    f"Row {row_number} ({ticket_id}): "
                    f"invalid expected_status={expected_status!r}. "
                    f"Expected one of "
                    f"{sorted(VALID_EXPECTED_STATUSES)}."
                )

            tickets.append(
                {
                    "id": ticket_id,
                    "subject": subject,
                    "body": body,
                    "expected_status": expected_status,
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
                response_body = (
                    json.loads(raw_body)
                    if raw_body
                    else None
                )
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
        raw_body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        try:
            response_body = (
                json.loads(raw_body)
                if raw_body
                else None
            )
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


def get_ticket(
    ticket_id: str,
    base_url: str,
    timeout: int,
) -> dict:

    ticket_url = (
        f"{base_url.rstrip('/')}/{quote(ticket_id)}"
    )

    req = request.Request(
        url=ticket_url,
        headers={
            "Accept": "application/json",
        },
        method="GET",
    )

    started = time.perf_counter()

    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw_body = response.read().decode("utf-8")
            elapsed = time.perf_counter() - started

            try:
                response_body = (
                    json.loads(raw_body)
                    if raw_body
                    else None
                )
            except json.JSONDecodeError:
                response_body = raw_body

            return {
                "id": ticket_id,
                "success": 200 <= response.status < 300,
                "status": response.status,
                "elapsed": elapsed,
                "response": response_body,
            }

    except error.HTTPError as exc:
        elapsed = time.perf_counter() - started
        raw_body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        try:
            response_body = (
                json.loads(raw_body)
                if raw_body
                else None
            )
        except json.JSONDecodeError:
            response_body = raw_body

        return {
            "id": ticket_id,
            "success": False,
            "status": exc.code,
            "elapsed": elapsed,
            "response": response_body,
        }

    except Exception as exc:
        elapsed = time.perf_counter() - started

        return {
            "id": ticket_id,
            "success": False,
            "status": None,
            "elapsed": elapsed,
            "response": str(exc),
        }


def validate_ticket(
    result: dict,
    expected_status: str,
) -> tuple[bool, list[str]]:

    errors = []

    if not result["success"]:
        errors.append(
            f"GET request failed with status={result['status']}"
        )
        return False, errors

    ticket = result["response"]

    if not isinstance(ticket, dict):
        errors.append(
            "Response is not a JSON object."
        )
        return False, errors

    status = ticket.get("status")

    # First validate the expected terminal state.
    if status != expected_status:
        errors.append(
            f"Expected status={expected_status!r}, "
            f"got {status!r}"
        )
        return False, errors

    category = ticket.get("category")
    priority = ticket.get("priority")
    summary = ticket.get("summary")

    # Successfully classified tickets should contain
    # valid inference output.
    if expected_status == "classified":

        if category not in VALID_CATEGORIES:
            errors.append(
                f"Invalid category: {category!r}"
            )

        if priority not in VALID_PRIORITIES:
            errors.append(
                f"Invalid priority: {priority!r}"
            )

        if (
            not isinstance(summary, str)
            or not summary.strip()
        ):
            errors.append(
                "Summary is missing or empty."
            )

    # Failed tickets should fail closed and should not
    # contain a classification result.
    elif expected_status == "failed":

        if category is not None:
            errors.append(
                f"Failed ticket contains category={category!r}"
            )

        if priority is not None:
            errors.append(
                f"Failed ticket contains priority={priority!r}"
            )

        if summary is not None:
            errors.append(
                f"Failed ticket contains summary={summary!r}"
            )

    return len(errors) == 0, errors


def countdown(seconds: int) -> None:
    print()
    print(
        f"Waiting {seconds} seconds "
        f"for asynchronous classification..."
    )

    for remaining in range(seconds, 0, -1):
        print(
            f"\rValidation starts in {remaining:2d}s",
            end="",
            flush=True,
        )
        time.sleep(1)

    print("\rStarting validation...          ")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Send customer-support tickets from a CSV file "
            "and validate their expected asynchronous state."
        )
    )

    parser.add_argument(
        "csv_file",
        help=(
            "Path to the CSV file containing id, subject, "
            "body, and expected_status columns."
        ),
    )

    parser.add_argument(
        "-n",
        "--concurrency",
        type=int,
        default=1,
        help=(
            "Maximum number of concurrent HTTP requests. "
            "Default: 1."
        ),
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
        help=(
            f"Per-request timeout in seconds. "
            f"Default: {DEFAULT_TIMEOUT}."
        ),
    )

    args = parser.parse_args()

    if args.concurrency < 1:
        parser.error(
            "-n/--concurrency must be at least 1."
        )

    if args.timeout < 1:
        parser.error(
            "--timeout must be at least 1 second."
        )

    try:
        tickets = load_tickets(args.csv_file)
    except (OSError, ValueError) as exc:
        print(
            f"Failed to load CSV: {exc}",
            file=sys.stderr,
        )
        return 1

    if not tickets:
        print("No tickets found in CSV.")
        return 0

    tickets_by_id = {
        ticket["id"]: ticket
        for ticket in tickets
    }

    # ---------------------------------------------------------
    # Phase 1: Submit Tickets
    # ---------------------------------------------------------

    print(
        f"Sending {len(tickets)} tickets to {args.url} "
        f"with concurrency={args.concurrency}"
    )

    started = time.perf_counter()
    results = []

    with ThreadPoolExecutor(
        max_workers=args.concurrency
    ) as executor:

        futures = {
            executor.submit(
                send_ticket,
                ticket,
                args.url,
                args.timeout,
            ): ticket
            for ticket in tickets
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            status = (
                result["status"]
                if result["status"] is not None
                else "ERROR"
            )

            outcome = (
                "OK"
                if result["success"]
                else "FAIL"
            )

            print(
                f"[{outcome}] {result['id']} "
                f"status={status} "
                f"time={result['elapsed']:.3f}s "
                f"response={result['response']}"
            )

    submission_elapsed = (
        time.perf_counter() - started
    )

    successful_results = [
        result
        for result in results
        if result["success"]
    ]

    successful = len(successful_results)
    failed = len(results) - successful

    print()
    print("Submission complete")
    print(f"  Total:      {len(results)}")
    print(f"  Successful: {successful}")
    print(f"  Failed:     {failed}")
    print(
        f"  Elapsed:    "
        f"{submission_elapsed:.3f}s"
    )

    if not successful_results:
        print()
        print(
            "No successfully created tickets "
            "available for validation."
        )
        return 2

    # ---------------------------------------------------------
    # Phase 2: Wait for Workers
    # ---------------------------------------------------------

    countdown(VALIDATION_WAIT)

    # ---------------------------------------------------------
    # Phase 3: Validate Expected Behavior
    # ---------------------------------------------------------

    ticket_ids = [
        result["id"]
        for result in successful_results
    ]

    print(
        f"Validating {len(ticket_ids)} tickets..."
    )

    validation_results = []

    with ThreadPoolExecutor(
        max_workers=args.concurrency
    ) as executor:

        futures = {
            executor.submit(
                get_ticket,
                ticket_id,
                args.url,
                args.timeout,
            ): ticket_id
            for ticket_id in ticket_ids
        }

        for future in as_completed(futures):
            result = future.result()

            expected_status = (
                tickets_by_id[result["id"]]
                ["expected_status"]
            )

            valid, validation_errors = (
                validate_ticket(
                    result,
                    expected_status,
                )
            )

            validation_results.append(
                {
                    "id": result["id"],
                    "valid": valid,
                    "expected_status": expected_status,
                    "errors": validation_errors,
                    "response": result["response"],
                }
            )

            if valid:
                ticket = result["response"]

                if expected_status == "classified":
                    print(
                        f"[PASS] {result['id']} "
                        f"status={ticket['status']} "
                        f"category={ticket['category']} "
                        f"priority={ticket['priority']} "
                        f"summary={ticket['summary']!r}"
                    )

                else:
                    print(
                        f"[PASS] {result['id']} "
                        f"status={ticket['status']} "
                        f"expected={expected_status}"
                    )

            else:
                print(
                    f"[FAIL] {result['id']} "
                    f"expected={expected_status}"
                )

                for validation_error in validation_errors:
                    print(
                        f"       - {validation_error}"
                    )

                print(
                    f"       response={result['response']}"
                )

    validation_successful = sum(
        result["valid"]
        for result in validation_results
    )

    validation_failed = (
        len(validation_results)
        - validation_successful
    )

    # ---------------------------------------------------------
    # Final Summary
    # ---------------------------------------------------------

    expected_classified = sum(
        1
        for ticket in tickets
        if ticket["expected_status"] == "classified"
    )

    expected_failed = sum(
        1
        for ticket in tickets
        if ticket["expected_status"] == "failed"
    )

    total_elapsed = (
        time.perf_counter() - started
    )

    print()
    print("=" * 50)
    print("Final Test Results")
    print("=" * 50)

    print()
    print("Submission:")
    print(
        f"  Successful: {successful}/"
        f"{len(results)}"
    )
    print(
        f"  Failed:     {failed}/"
        f"{len(results)}"
    )

    print()
    print("Expected Behavior:")
    print(
        f"  Classified: {expected_classified}"
    )
    print(
        f"  Safe Failures: {expected_failed}"
    )

    print()
    print("Behavior Validation:")
    print(
        f"  Passed:     {validation_successful}/"
        f"{len(validation_results)}"
    )
    print(
        f"  Failed:     {validation_failed}/"
        f"{len(validation_results)}"
    )

    print()
    print(
        f"Total elapsed: {total_elapsed:.3f}s"
    )

    if failed > 0 or validation_failed > 0:
        return 2

    print()
    print("All expected behaviors passed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())