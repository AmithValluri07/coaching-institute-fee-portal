
"""
Coaching Institute Fee Tracking System
File: refund_engine.py

Responsibilities:
- Calculate a pro-rata refund when a student leaves a course.
- Calculate consumed and unused course fees.
- Apply only explicitly configured deductions.
- Calculate the refund processing deadline.

IMPORTANT:
The client brief specifies a pro-rata refund within 10 days.
It does not specify an administrative fee or other deduction.

Therefore, administrative_fee defaults to zero.
Any deduction must be configured according to the institute's
published and legally reviewed refund policy.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict


ZERO = Decimal("0.00")
TWO_PLACES = Decimal("0.01")


# -------------------------------------------------------------------
# Validation utilities
# -------------------------------------------------------------------

def money(value: Any, field_name: str = "amount") -> Decimal:
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


def parse_date(value: Any, field_name: str) -> date:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ValueError(
            f"{field_name} must be a valid date in YYYY-MM-DD format."
        )


# -------------------------------------------------------------------
# Pro-rata refund calculation
# -------------------------------------------------------------------

def calculate_pro_rata_refund(
    total_fee: Any,
    course_start_date: Any,
    course_end_date: Any,
    student_leaving_date: Any,
    paid_amount: Any,
    administrative_fee: Any = 0,
    request_date: Any = None,
    refund_deadline_days: int = 10,
) -> Dict[str, Any]:
    """
    Calculate the unused portion of a course fee.

    Formula:

        Daily fee = Total course fee / Total course days

        Consumed fee = Daily fee * Elapsed course days

        Unused fee = Total course fee - Consumed fee

        Refund = Minimum of:
            Paid amount - consumed fee - approved deductions
            Unused fee

    The refund cannot exceed the amount actually paid.

    Date convention:
        Course start date is counted as day 1.
        Leaving date is treated as the first unused day.
        Elapsed days = leaving date - course start date.

    The date convention is an implementation assumption and
    should be confirmed against the institute's published policy.
    """

    # Validate amounts.
    total_fee = money(total_fee, "total_fee")
    paid_amount = money(paid_amount, "paid_amount")
    administrative_fee = money(
        administrative_fee,
        "administrative_fee"
    )

    # Validate dates.
    start_date = parse_date(
        course_start_date,
        "course_start_date"
    )

    end_date = parse_date(
        course_end_date,
        "course_end_date"
    )

    leaving_date = parse_date(
        student_leaving_date,
        "student_leaving_date"
    )

    submitted_date = parse_date(
        request_date if request_date is not None else leaving_date,
        "request_date"
    )

    if total_fee <= ZERO:
        raise ValueError("Total course fee must be greater than zero.")

    if paid_amount > total_fee:
        raise ValueError("Paid amount cannot exceed total course fee.")

    if administrative_fee > paid_amount:
        raise ValueError(
            "Administrative fee cannot exceed the amount paid."
        )

    if end_date <= start_date:
        raise ValueError(
            "Course end date must be after course start date."
        )

    if leaving_date < start_date:
        raise ValueError(
            "Student leaving date cannot be before course start date."
        )

    if leaving_date > end_date:
        raise ValueError(
            "Student leaving date cannot be after course end date."
        )

    if submitted_date < leaving_date:
        raise ValueError(
            "Refund request date cannot be before the leaving date."
        )

    if refund_deadline_days < 0:
        raise ValueError(
            "Refund deadline days cannot be negative."
        )

    # Calculate course duration.
    total_course_days = (end_date - start_date).days

    elapsed_days = (leaving_date - start_date).days

    elapsed_days = min(
        max(elapsed_days, 0),
        total_course_days
    )

    remaining_days = total_course_days - elapsed_days

    # Calculate consumed and unused course fees.
    consumed_fee = (
        total_fee * Decimal(elapsed_days)
        / Decimal(total_course_days)
    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    unused_fee = max(
        ZERO,
        total_fee - consumed_fee
    )

    # Calculate the amount remaining after consumed fees.
    refundable_after_consumption = max(
        ZERO,
        paid_amount - consumed_fee - administrative_fee
    )

    # Do not refund more than the unused fee or the amount paid.
    refund_amount = min(
        refundable_after_consumption,
        unused_fee,
        paid_amount
    )

    refund_amount = refund_amount.quantize(
        TWO_PLACES,
        rounding=ROUND_HALF_UP
    )

    # Calculate refund processing deadline.
    refund_deadline = (
        submitted_date + timedelta(days=refund_deadline_days)
    )

    return {
        "total_course_fee": total_fee,
        "paid_amount": paid_amount,
        "course_start_date": start_date.isoformat(),
        "course_end_date": end_date.isoformat(),
        "student_leaving_date": leaving_date.isoformat(),
        "refund_request_date": submitted_date.isoformat(),
        "total_course_days": total_course_days,
        "elapsed_days": elapsed_days,
        "remaining_days": remaining_days,
        "consumed_fee": consumed_fee,
        "unused_fee": unused_fee,
        "administrative_fee": administrative_fee,
        "refundable_after_consumption": refundable_after_consumption,
        "refund_amount": refund_amount,
        "refund_deadline": refund_deadline.isoformat(),
        "refund_deadline_days": refund_deadline_days,
        "refund_status": (
            "REFUND_DUE"
            if refund_amount > ZERO
            else "NO_REFUND_CALCULATED"
        ),
    }


# -------------------------------------------------------------------
# Demonstration
# -------------------------------------------------------------------

def print_refund_summary(result: Dict[str, Any]) -> None:

    print("\nSTUDENT FEE REFUND SUMMARY")
    print("=" * 60)

    print(f"Course fee          : ₹{result['total_course_fee']:,.2f}")
    print(f"Amount paid         : ₹{result['paid_amount']:,.2f}")

    print(f"Course start        : {result['course_start_date']}")
    print(f"Course end          : {result['course_end_date']}")
    print(f"Leaving date        : {result['student_leaving_date']}")

    print(f"Total course days   : {result['total_course_days']}")
    print(f"Elapsed days        : {result['elapsed_days']}")
    print(f"Remaining days      : {result['remaining_days']}")

    print(f"\nConsumed fee        : ₹{result['consumed_fee']:,.2f}")
    print(f"Unused fee          : ₹{result['unused_fee']:,.2f}")

    print(
        f"Administrative fee  : "
        f"₹{result['administrative_fee']:,.2f}"
    )

    print(
        f"Refund amount       : "
        f"₹{result['refund_amount']:,.2f}"
    )

    print(f"Request date        : {result['refund_request_date']}")
    print(f"Refund deadline     : {result['refund_deadline']}")
    print(f"Refund status       : {result['refund_status']}")

    print("=" * 60)


# -------------------------------------------------------------------
# Main execution
# -------------------------------------------------------------------

if __name__ == "__main__":

    # Demonstration values only.
    # The administrative deduction is zero because the client
    # brief does not specify an administrative fee.

    refund = calculate_pro_rata_refund(
        total_fee="120000.00",
        course_start_date="2026-07-01",
        course_end_date="2027-04-30",
        student_leaving_date="2026-11-02",
        paid_amount="15000.00",
        administrative_fee="0.00",
        request_date="2026-11-02",
        refund_deadline_days=10,
    )

    print_refund_summary(refund)
