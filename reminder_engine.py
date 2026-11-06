
"""
Coaching Institute Fee Tracking System
File: reminder_engine.py

Responsibilities:
- Generate Hindi and English fee reminders.
- Evaluate upcoming and overdue instalments.
- Stop reminders when the balance is fully paid.
- Process simulated payment gateway webhooks.
- Send unmatched payments to an accounts review queue.

NOTE:
This is an in-memory simulation.
Production deployment must persist transactions and reminder
events in the application database.
"""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional


ZERO = Decimal("0.00")
TWO_PLACES = Decimal("0.01")


# -------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------

def money(value: Any, field_name: str = "amount") -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(
            TWO_PLACES,
            rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid amount.")

    if not amount.is_finite() or amount < ZERO:
        raise ValueError(f"{field_name} must be non-negative and finite.")

    return amount


def parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValueError("Invalid date. Expected YYYY-MM-DD.")


# -------------------------------------------------------------------
# Sample instalment records
# -------------------------------------------------------------------

reminders_db: Dict[str, Dict[str, Any]] = {
    "STU-0412": {
        "student_id": "STU-0412",
        "student_name": "Aarav Meena",
        "parent_name": "Rakesh Meena",
        "language": "en",
        "instalment_id": "INS-0412",
        "total_amount": Decimal("30000.00"),
        "paid_amount": Decimal("30000.00"),
        "due_date": date(2026, 10, 10),
        "reminders_enabled": True,
        "reminder_history": [],
    },
    "STU-0587": {
        "student_id": "STU-0587",
        "student_name": "Ishita Sharma",
        "parent_name": "Anita Sharma",
        "language": "hi",
        "instalment_id": "INS-0587",
        "total_amount": Decimal("30000.00"),
        "paid_amount": Decimal("15000.00"),
        "due_date": date(2026, 10, 10),
        "reminders_enabled": True,
        "reminder_history": [],
    },
    "STU-0219": {
        "student_id": "STU-0219",
        "student_name": "Mohit Gurjar",
        "parent_name": "Suresh Gurjar",
        "language": "en",
        "instalment_id": "INS-0219",
        "total_amount": Decimal("40000.00"),
        "paid_amount": Decimal("0.00"),
        "due_date": date(2026, 11, 15),
        "reminders_enabled": True,
        "reminder_history": [],
    },
}


# -------------------------------------------------------------------
# Payment and review queues
# -------------------------------------------------------------------

payment_transactions: Dict[str, Dict[str, Any]] = {}

unmatched_payment_queue: List[Dict[str, Any]] = []


# -------------------------------------------------------------------
# Reminder message templates
# -------------------------------------------------------------------

def generate_reminder_message(
    student: Dict[str, Any],
    balance: Decimal,
    due_date: date,
    reminder_type: str
) -> str:

    language = student.get("language", "en").lower()

    if language not in ("en", "hi"):
        language = "en"

    if language == "hi":

        messages = {
            "before": (
                f"प्रिय अभिभावक, {student['student_name']} की "
                f"₹{balance:,.2f} फीस {due_date.isoformat()} को देय है। "
                "कृपया समय पर भुगतान करें।"
            ),
            "due": (
                f"प्रिय अभिभावक, {student['student_name']} की "
                f"₹{balance:,.2f} फीस आज देय है। "
                "कृपया भुगतान करें।"
            ),
            "overdue": (
                f"प्रिय अभिभावक, {student['student_name']} की "
                f"₹{balance:,.2f} फीस बकाया है। "
                "कृपया जल्द भुगतान करें।"
            ),
        }

    else:

        messages = {
            "before": (
                f"Dear Parent, ₹{balance:,.2f} fee for "
                f"{student['student_name']} is due on "
                f"{due_date.isoformat()}. Please pay on time."
            ),
            "due": (
                f"Dear Parent, ₹{balance:,.2f} fee for "
                f"{student['student_name']} is due today. "
                "Please complete your payment."
            ),
            "overdue": (
                f"Dear Parent, ₹{balance:,.2f} fee for "
                f"{student['student_name']} is overdue. "
                "Please complete your payment."
            ),
        }

    return messages[reminder_type]


# -------------------------------------------------------------------
# Reminder evaluation
# -------------------------------------------------------------------

def evaluate_reminder_queue(
    current_date: Optional[date] = None,
    before_due_days: int = 3
) -> List[Dict[str, Any]]:
    """
    Evaluate reminder eligibility.

    Schedule:
        3 days before due date: pre-due reminder
        On due date: due reminder
        After due date: overdue reminder

    The function returns eligible messages.
    It does not send real SMS or WhatsApp messages.
    """

    today = current_date or date.today()

    if before_due_days < 0:
        raise ValueError("before_due_days cannot be negative.")

    generated_messages = []

    for student_id, student in reminders_db.items():

        total = money(student["total_amount"])
        paid = money(student["paid_amount"])
        balance = total - paid

        # Stop all future reminders when fully paid.
        if balance == ZERO:
            student["reminders_enabled"] = False
            continue

        if not student["reminders_enabled"]:
            continue

        due_date = parse_date(student["due_date"])
        days_until_due = (due_date - today).days

        if days_until_due == before_due_days:
            reminder_type = "before"

        elif days_until_due == 0:
            reminder_type = "due"

        elif days_until_due < 0:
            reminder_type = "overdue"

        else:
            continue

        # Avoid sending the same reminder repeatedly.
        reminder_key = (
            f"{student_id}:{due_date.isoformat()}:{reminder_type}"
        )

        if any(
            item["reminder_key"] == reminder_key
            for item in student["reminder_history"]
        ):
            continue

        message = generate_reminder_message(
            student,
            balance,
            due_date,
            reminder_type
        )

        event = {
            "student_id": student_id,
            "student_name": student["student_name"],
            "reminder_type": reminder_type,
            "language": student["language"],
            "balance": balance,
            "due_date": due_date.isoformat(),
            "message": message,
            "reminder_key": reminder_key,
            "delivery_status": "SIMULATED",
        }

        student["reminder_history"].append(event)
        generated_messages.append(event)

    return generated_messages


# -------------------------------------------------------------------
# Payment processing
# -------------------------------------------------------------------

def simulate_payment_webhook(
    student_id: str,
    txn_id: str,
    amount_paid: Any,
    instalment_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Simulate a payment gateway webhook.

    A payment only updates the instalment when:
    - Student exists.
    - Instalment matches.
    - Transaction ID is new.
    - Payment amount is valid.
    - Payment does not exceed the outstanding balance.

    Unmatched payments are placed in the accounts queue.
    """

    student_id = str(student_id).strip()
    txn_id = str(txn_id).strip()

    if not txn_id:
        raise ValueError("Transaction ID cannot be empty.")

    if txn_id in payment_transactions:
        raise ValueError("Duplicate transaction ID.")

    amount = money(amount_paid, "amount_paid")

    if amount <= ZERO:
        raise ValueError("Payment must be greater than zero.")

    student = reminders_db.get(student_id)

    if student is None:

        unmatched_payment_queue.append({
            "transaction_id": txn_id,
            "student_id": student_id,
            "amount": amount,
            "reason": "Student not found",
            "review_status": "PENDING",
        })

        return {
            "status": "UNMATCHED",
            "message": "Payment sent to accounts review queue.",
        }

    if (
        instalment_id is not None
        and instalment_id != student["instalment_id"]
    ):

        unmatched_payment_queue.append({
            "transaction_id": txn_id,
            "student_id": student_id,
            "instalment_id": instalment_id,
            "amount": amount,
            "reason": "Instalment mismatch",
            "review_status": "PENDING",
        })

        return {
            "status": "UNMATCHED",
            "message": "Instalment mismatch. Accounts review required.",
        }

    total = money(student["total_amount"])
    paid = money(student["paid_amount"])
    balance = total - paid

    if balance == ZERO:
        return {
            "status": "REJECTED",
            "message": "Instalment is already fully paid.",
        }

    if amount > balance:

        unmatched_payment_queue.append({
            "transaction_id": txn_id,
            "student_id": student_id,
            "amount": amount,
            "reason": "Payment exceeds outstanding balance",
            "review_status": "PENDING",
        })

        return {
            "status": "UNMATCHED",
            "message": "Excess payment requires accounts review.",
        }

    # Update only after all validation succeeds.
    new_paid_amount = paid + amount
    remaining_balance = total - new_paid_amount

    student["paid_amount"] = new_paid_amount

    payment_transactions[txn_id] = {
        "transaction_id": txn_id,
        "student_id": student_id,
        "instalment_id": student["instalment_id"],
        "amount_paid": amount,
        "status": "SUCCESS",
    }

    # Stop reminders only when the full balance is cleared.
    if remaining_balance == ZERO:
        student["reminders_enabled"] = False
        payment_status = "PAID"
    else:
        payment_status = "PART_PAID"

    return {
        "status": payment_status,
        "student_id": student_id,
        "transaction_id": txn_id,
        "amount_paid": amount,
        "total_paid": new_paid_amount,
        "remaining_balance": remaining_balance,
        "reminders_enabled": student["reminders_enabled"],
    }


# -------------------------------------------------------------------
# Accounts review
# -------------------------------------------------------------------

def get_unmatched_payment_queue() -> List[Dict[str, Any]]:
    """Return unmatched payments requiring manual review."""

    return unmatched_payment_queue.copy()


# -------------------------------------------------------------------
# Demonstration
# -------------------------------------------------------------------

def print_reminder_queue(
    current_date: Optional[date] = None
) -> None:

    messages = evaluate_reminder_queue(current_date)

    print("\nAUTOMATED REMINDER QUEUE")
    print("=" * 70)

    if not messages:
        print("No reminders scheduled for this date.")

    for item in messages:
        print(f"\nStudent : {item['student_name']}")
        print(f"Type    : {item['reminder_type']}")
        print(f"Amount  : ₹{item['balance']:,.2f}")
        print(f"Message : {item['message']}")

    print("\n" + "=" * 70)


if __name__ == "__main__":

    # Demonstrate reminder generation.
    print_reminder_queue(date(2026, 11, 2))

    # Demonstrate partial payment for Ishita.
    print("\nPROCESSING PARTIAL PAYMENT")

    result = simulate_payment_webhook(
        student_id="STU-0587",
        txn_id="TXN-ISHITA-001",
        amount_paid="5000.00",
        instalment_id="INS-0587"
    )

    print(result)

    # Demonstrate remaining balance after payment.
    print("\nUPDATED REMINDER ELIGIBILITY")

    result = simulate_payment_webhook(
        student_id="STU-0587",
        txn_id="TXN-ISHITA-002",
        amount_paid="10000.00",
        instalment_id="INS-0587"
    )

    print(result)

    # Demonstrate unmatched payment.
    print("\nUNMATCHED PAYMENT TEST")

    result = simulate_payment_webhook(
        student_id="STU-9999",
        txn_id="TXN-UNKNOWN-001",
        amount_paid="2000.00"
    )

    print(result)

    print("\nACCOUNTS REVIEW QUEUE")
    print(get_unmatched_payment_queue())
