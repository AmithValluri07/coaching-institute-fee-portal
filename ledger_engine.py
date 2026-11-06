
"""
Coaching Institute Fee Tracking System
File: ledger_engine.py

Responsibilities:
- Calculate payable amount after discounts.
- Calculate outstanding balance.
- Determine instalment payment status.
- Calculate overdue days or days remaining.
- Validate payment and fee inputs.

This module contains business logic only.
Database persistence is handled separately.
"""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Optional


# -------------------------------------------------------------------
# Money utilities
# -------------------------------------------------------------------

ZERO = Decimal("0.00")
TWO_PLACES = Decimal("0.01")


def money(value: Any, field_name: str = "amount") -> Decimal:
    """Convert a value to a valid non-negative monetary Decimal."""

    try:
        amount = Decimal(str(value)).quantize(
            TWO_PLACES,
            rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid monetary amount.")

    if not amount.is_finite():
        raise ValueError(f"{field_name} must be finite.")

    if amount < ZERO:
        raise ValueError(f"{field_name} cannot be negative.")

    return amount


# -------------------------------------------------------------------
# Date utilities
# -------------------------------------------------------------------

def parse_date(value: Any) -> date:
    """Accept a date object or YYYY-MM-DD string."""

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        raise ValueError("Date must be in YYYY-MM-DD format.")

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid date. Expected YYYY-MM-DD.")


# -------------------------------------------------------------------
# Fee ledger calculation
# -------------------------------------------------------------------

def calculate_ledger_status(
    instalment: Dict[str, Any],
    current_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Calculate the current financial status of one instalment.

    Required fields:
        student_id
        total_amount
        paid_amount
        due_date

    Optional fields:
        instalment_id
        discount_amount

    Status values:
        Paid
        Part Paid
        Overdue
        Due
    """

    if not isinstance(instalment, dict):
        raise ValueError("Instalment must be a dictionary.")

    required_fields = (
        "student_id",
        "total_amount",
        "paid_amount",
        "due_date"
    )

    for field in required_fields:
        if field not in instalment:
            raise ValueError(f"Missing required field: {field}")

    student_id = str(instalment["student_id"]).strip()

    if not student_id:
        raise ValueError("Student ID cannot be empty.")

    total_amount = money(
        instalment["total_amount"],
        "total_amount"
    )

    paid_amount = money(
        instalment["paid_amount"],
        "paid_amount"
    )

    discount_amount = money(
        instalment.get("discount_amount", 0),
        "discount_amount"
    )

    due_date = parse_date(instalment["due_date"])
    today = current_date or date.today()

    if not isinstance(today, date):
        raise ValueError("current_date must be a date object.")

    if discount_amount > total_amount:
        raise ValueError(
            "Discount cannot exceed the original instalment amount."
        )

    payable_amount = total_amount - discount_amount

    if paid_amount > payable_amount:
        raise ValueError(
            "Paid amount cannot exceed the payable instalment amount."
        )

    balance = payable_amount - paid_amount

    overdue_days = 0
    days_remaining = 0

    if balance == ZERO:
        status = "Paid"

    elif today > due_date:
        overdue_days = (today - due_date).days

        if paid_amount > ZERO:
            status = "Part Paid"
        else:
            status = "Overdue"

    elif today < due_date:
        days_remaining = (due_date - today).days
        status = "Due"

    else:
        status = "Due Today"

    return {
        "instalment_id": instalment.get("instalment_id"),
        "student_id": student_id,
        "total_amount": total_amount,
        "discount_amount": discount_amount,
        "payable_amount": payable_amount,
        "paid_amount": paid_amount,
        "balance": balance,
        "due_date": due_date.isoformat(),
        "status": status,
        "overdue_days": overdue_days,
        "days_remaining": days_remaining,
        "is_overdue": overdue_days > 0 and balance > ZERO,
        "is_fully_paid": balance == ZERO,
    }


# -------------------------------------------------------------------
# Payment validation
# -------------------------------------------------------------------

def validate_payment(
    instalment: Dict[str, Any],
    payment_amount: Any
) -> Dict[str, Decimal]:
    """
    Validate a new payment without changing the original record.

    The payment must be positive and cannot exceed the outstanding
    balance. Persistence should happen only after payment confirmation.
    """

    ledger = calculate_ledger_status(instalment)

    amount = money(payment_amount, "payment_amount")

    if amount <= ZERO:
        raise ValueError("Payment amount must be greater than zero.")

    if amount > ledger["balance"]:
        raise ValueError(
            f"Payment exceeds outstanding balance of "
            f"₹{ledger['balance']:.2f}."
        )

    remaining_balance = ledger["balance"] - amount
    updated_paid_amount = ledger["paid_amount"] + amount

    return {
        "payment_amount": amount,
        "previous_balance": ledger["balance"],
        "updated_paid_amount": updated_paid_amount,
        "remaining_balance": remaining_balance,
    }


# -------------------------------------------------------------------
# Sample data
# -------------------------------------------------------------------

SAMPLE_INSTALMENTS = [
    {
        "instalment_id": "INS-0412",
        "student_id": "STU-0412",
        "student_name": "Aarav Meena",
        "batch": "JEE 2027 Morning",
        "total_amount": "30000.00",
        "discount_amount": "0.00",
        "paid_amount": "30000.00",
        "due_date": "2026-10-10",
    },
    {
        "instalment_id": "INS-0587",
        "student_id": "STU-0587",
        "student_name": "Ishita Sharma",
        "batch": "JEE 2027 Evening",
        "total_amount": "30000.00",
        "discount_amount": "0.00",
        "paid_amount": "15000.00",
        "due_date": "2026-10-10",
    },
    {
        "instalment_id": "INS-0219",
        "student_id": "STU-0219",
        "student_name": "Mohit Gurjar",
        "batch": "NEET 2027 Morning",
        "total_amount": "40000.00",
        "discount_amount": "0.00",
        "paid_amount": "0.00",
        "due_date": "2026-11-15",
    },
]


# -------------------------------------------------------------------
# Demonstration
# -------------------------------------------------------------------

def print_sample_ledger(
    current_date: Optional[date] = None
) -> None:

    print("\nCOACHING INSTITUTE - FEE LEDGER")
    print("=" * 90)

    today = current_date or date.today()

    print(f"Calculation date: {today.isoformat()}")
    print("-" * 90)

    for student in SAMPLE_INSTALMENTS:
        ledger = calculate_ledger_status(student, today)

        print(f"\nStudent       : {student['student_name']}")
        print(f"Student ID    : {ledger['student_id']}")
        print(f"Batch         : {student['batch']}")
        print(f"Instalment    : ₹{ledger['total_amount']:,.2f}")
        print(f"Discount      : ₹{ledger['discount_amount']:,.2f}")
        print(f"Payable       : ₹{ledger['payable_amount']:,.2f}")
        print(f"Paid          : ₹{ledger['paid_amount']:,.2f}")
        print(f"Balance       : ₹{ledger['balance']:,.2f}")
        print(f"Due date      : {ledger['due_date']}")
        print(f"Status        : {ledger['status']}")
        print(f"Overdue days  : {ledger['overdue_days']}")

    print("\n" + "=" * 90)


if __name__ == "__main__":
    print_sample_ledger()
