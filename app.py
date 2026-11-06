from flask import Flask, jsonify, send_file, request, render_template_string, url_for
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, timedelta
from uuid import uuid4
import csv
import hashlib
import io
import secrets
import os

from db import get_db_connection

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent

# Demo-only OTP storage. Replace with a verified provider and persistent challenge
# storage before production. Values are hashed and expire after five minutes.
_DEMO_OTPS = {}
_DEMO_PAYMENT_TOKENS = {}

ALLOWED_PAYMENT_METHODS = {
    "UPI",
    "CARD",
    "NET_BANKING",
    "CASH",
    "BANK_TRANSFER",
    "OTHER"
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def to_float(value):
    return float(value) if value is not None else 0.0


def get_payment_status(amount_paid, payable_amount):
    if amount_paid >= payable_amount:
        return "Paid"
    elif amount_paid > 0:
        return "Part Paid"
    return "Unpaid"


def validate_amount(value):
    if value is None or isinstance(value, bool):
        raise ValueError("Payment amount is required.")

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Enter a valid payment amount.")

    if not amount.is_finite():
        raise ValueError("Payment amount must be a finite number.")

    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Payment amount cannot have more than two decimal places.")

    return amount


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return send_file(BASE_DIR / "index.html")


# ============================================================
# 1. DATABASE HEALTH CHECK
# ============================================================

@app.route("/api/health")
def health_check():
    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            database = cursor.fetchone()[0]

        return jsonify({
            "status": "success",
            "message": "Flask and PostgreSQL are connected",
            "database": database
        })

    except Exception:
        app.logger.exception("Database health check failed")

        return jsonify({
            "status": "error",
            "message": "Database connection failed."
        }), 500

    finally:
        if connection:
            connection.close()


# ============================================================
# 2. GET ALL STUDENTS
# ============================================================

@app.route("/api/students")
def get_students():
    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    s.admission_number,
                    s.full_name,
                    b.batch_name,
                    COALESCE(fee_summary.total_payable, 0) AS total_payable,
                    COALESCE(fee_summary.amount_paid, 0) AS amount_paid,
                    fee_summary.next_due_date

                FROM students s

                JOIN batches b
                    ON b.batch_id = s.batch_id

                JOIN student_fee_accounts fa
                    ON fa.student_id = s.student_id

                LEFT JOIN LATERAL (
                    SELECT
                        SUM(
                            GREATEST(
                                COALESCE(fi.instalment_amount, 0) -
                                COALESCE(fi.discount_amount, 0),
                                0
                            )
                        ) AS total_payable,

                        SUM(COALESCE(payment_summary.amount_paid, 0))
                            AS amount_paid,

                        MIN(fi.due_date) FILTER (
                            WHERE GREATEST(
                                COALESCE(fi.instalment_amount, 0) -
                                COALESCE(fi.discount_amount, 0),
                                0
                            ) > COALESCE(payment_summary.amount_paid, 0)
                        ) AS next_due_date

                    FROM fee_instalments fi

                    LEFT JOIN LATERAL (
                        SELECT COALESCE(SUM(p.amount), 0) AS amount_paid
                        FROM payments p
                        WHERE p.instalment_id = fi.instalment_id
                          AND p.payment_status = 'SUCCESS'
                    ) payment_summary ON TRUE

                    WHERE fi.fee_account_id = fa.fee_account_id
                ) fee_summary ON TRUE

                ORDER BY s.admission_number;
            """)

            rows = cursor.fetchall()
            students = []

            for row in rows:
                total_payable = to_float(row[3])
                amount_paid = to_float(row[4])
                outstanding_balance = max(0, total_payable - amount_paid)

                students.append({
                    "admission_number": row[0],
                    "full_name": row[1],
                    "batch_name": row[2],
                    "total_fee": total_payable,
                    "total_payable": total_payable,
                    "amount_paid": amount_paid,
                    "outstanding_balance": outstanding_balance,
                    "due_date": row[5].isoformat() if row[5] else None,
                    "status": get_payment_status(
                        amount_paid,
                        total_payable
                    )
                })

        return jsonify({
            "status": "success",
            "count": len(students),
            "students": students
        })

    except Exception:
        app.logger.exception("Could not retrieve students")

        return jsonify({
            "status": "error",
            "message": "Could not retrieve student records."
        }), 500

    finally:
        if connection:
            connection.close()


# ============================================================
# 3. INDIVIDUAL STUDENT FEE LEDGER
# ============================================================

@app.route("/api/students/<admission_number>/ledger")
def get_student_ledger(admission_number):
    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:

            cursor.execute("""
                SELECT
                    s.student_id,
                    s.admission_number,
                    s.full_name,
                    b.batch_name,
                    fa.total_fee,
                    fa.discount_amount,
                    fa.final_fee,

                    fi.instalment_id,
                    fi.instalment_number,
                    fi.instalment_amount,
                    fi.discount_amount,
                    fi.due_date,

                    COALESCE(
                        SUM(p.amount) FILTER (
                            WHERE p.payment_status = 'SUCCESS'
                        ), 0
                    ) AS amount_paid

                FROM students s

                JOIN batches b
                    ON b.batch_id = s.batch_id

                JOIN student_fee_accounts fa
                    ON fa.student_id = s.student_id

                LEFT JOIN fee_instalments fi
                    ON fi.fee_account_id = fa.fee_account_id

                LEFT JOIN payments p
                    ON p.instalment_id = fi.instalment_id

                WHERE s.admission_number = %s

                GROUP BY
                    s.student_id,
                    s.admission_number,
                    s.full_name,
                    b.batch_name,
                    fa.total_fee,
                    fa.discount_amount,
                    fa.final_fee,
                    fi.instalment_id,
                    fi.instalment_number,
                    fi.instalment_amount,
                    fi.discount_amount,
                    fi.due_date

                ORDER BY fi.instalment_number;
            """, (admission_number,))

            rows = cursor.fetchall()

            if not rows:
                return jsonify({
                    "status": "error",
                    "message": "Student not found."
                }), 404

            first = rows[0]

            instalments = []
            instalment_ids = []

            for row in rows:

                if row[7] is None:
                    continue

                instalment_id = row[7]
                instalment_ids.append(instalment_id)

                instalment_amount = to_float(row[9])
                instalment_discount = to_float(row[10])
                amount_paid = to_float(row[12])

                payable_amount = max(
                    0,
                    instalment_amount - instalment_discount
                )

                balance = max(
                    0,
                    payable_amount - amount_paid
                )

                instalments.append({
                    "instalment_id": instalment_id,
                    "instalment_number": row[8],
                    "instalment_amount": instalment_amount,
                    "discount": instalment_discount,
                    "payable_amount": payable_amount,
                    "due_date": row[11].isoformat(),
                    "amount_paid": amount_paid,
                    "outstanding_balance": balance,
                    "status": get_payment_status(
                        amount_paid,
                        payable_amount
                    ),
                    "payments": []
                })

            # Retrieve all payment transactions for these instalments
            if instalment_ids:

                cursor.execute("""
                    SELECT
                        instalment_id,
                        transaction_id,
                        amount,
                        payment_method,
                        payment_status,
                        paid_at,
                        cgst_amount,
                        sgst_amount

                    FROM payments

                    WHERE instalment_id = ANY(%s)

                    ORDER BY paid_at DESC NULLS LAST, payment_id DESC;
                """, (instalment_ids,))

                payment_rows = cursor.fetchall()

                payment_map = {
                    item["instalment_id"]: item
                    for item in instalments
                }

                for payment in payment_rows:

                    item = payment_map.get(payment[0])

                    if item is None:
                        continue

                    item["payments"].append({
                        "transaction_id": payment[1],
                        "amount": to_float(payment[2]),
                        "payment_method": payment[3],
                        "payment_status": payment[4],
                        "paid_at": (
                            payment[5].isoformat()
                            if payment[5] else None
                        ),
                        "cgst_amount": to_float(payment[6]),
                        "sgst_amount": to_float(payment[7])
                    })

        return jsonify({
            "status": "success",

            "student": {
                "admission_number": first[1],
                "full_name": first[2],
                "batch_name": first[3],
                "total_fee": to_float(first[4]),
                "account_discount": to_float(first[5]),
                "final_fee": to_float(first[6])
            },

            "instalments": instalments,
            "instalment_count": len(instalments)
        })

    except Exception:
        app.logger.exception("Could not retrieve student ledger")

        return jsonify({
            "status": "error",
            "message": "Could not retrieve student fee ledger."
        }), 500

    finally:
        if connection:
            connection.close()


# ============================================================
# 4. RECORD PAYMENT
# ============================================================

@app.route("/api/payments", methods=["POST"])
def record_payment():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "A valid JSON request body is required."
        }), 400

    # Validate instalment ID
    try:
        instalment_id = int(data.get("instalment_id"))

        if instalment_id <= 0:
            raise ValueError

    except (TypeError, ValueError):
        return jsonify({
            "status": "error",
            "message": "A valid instalment_id is required."
        }), 400

    # Validate payment amount
    try:
        amount = validate_amount(data.get("amount"))

    except ValueError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    # Validate payment method
    payment_method = str(
        data.get("payment_method", "")
    ).strip().upper()

    if payment_method not in ALLOWED_PAYMENT_METHODS:
        return jsonify({
            "status": "error",
            "message": "Invalid payment method. Choose UPI, CARD, NET_BANKING, CASH, BANK_TRANSFER or OTHER."
        }), 400

    # Optional gateway reference
    gateway_reference = data.get("gateway_reference")

    if gateway_reference is not None:
        gateway_reference = str(gateway_reference).strip() or None

        if gateway_reference and len(gateway_reference) > 200:
            return jsonify({
                "status": "error",
                "message": "Gateway reference cannot exceed 200 characters."
            }), 400

    connection = None

    try:
        connection = get_db_connection()

        # Keep the row lock, payment insert and balance calculation
        # inside one PostgreSQL transaction.
        with connection.transaction():

            with connection.cursor() as cursor:

                # Lock the instalment to prevent concurrent overpayments.
                cursor.execute("""
                    SELECT
                        fi.instalment_id,
                        fi.instalment_amount,
                        fi.discount_amount,
                        s.admission_number

                    FROM fee_instalments fi
                    JOIN student_fee_accounts fa ON fa.fee_account_id = fi.fee_account_id
                    JOIN students s ON s.student_id = fa.student_id

                    WHERE fi.instalment_id = %s

                    FOR UPDATE OF fi;
                """, (instalment_id,))

                instalment = cursor.fetchone()

                if instalment is None:
                    return jsonify({
                        "status": "error",
                        "message": "Instalment not found."
                    }), 404

                admission_number = str(data.get("admission_number", "")).strip()
                verification_token = str(data.get("otp_verification_token", "")).strip()
                if admission_number != str(instalment[3]) or not verification_token:
                    return jsonify({
                        "status": "error",
                        "message": "Verify the selected parent's demo OTP before making a payment."
                    }), 403
                token_record = _DEMO_PAYMENT_TOKENS.get(admission_number)
                token_hash = hashlib.sha256(verification_token.encode("utf-8")).hexdigest()
                if (not token_record or token_record[1] <= datetime.now()
                        or not secrets.compare_digest(token_record[0], token_hash)):
                    return jsonify({
                        "status": "error",
                        "message": "Parent OTP verification is missing or expired. Verify again."
                    }), 403
                # One-time payment authorization token.
                _DEMO_PAYMENT_TOKENS.pop(admission_number, None)

                instalment_amount = Decimal(str(instalment[1]))
                instalment_discount = Decimal(str(instalment[2]))

                payable_amount = max(
                    Decimal("0.00"),
                    instalment_amount - instalment_discount
                )

                # Calculate previous successful payments.
                cursor.execute("""
                    SELECT COALESCE(SUM(amount), 0)

                    FROM payments

                    WHERE instalment_id = %s
                      AND payment_status = 'SUCCESS';
                """, (instalment_id,))

                amount_paid = Decimal(
                    str(cursor.fetchone()[0])
                )

                outstanding = max(
                    Decimal("0.00"),
                    payable_amount - amount_paid
                )

                if outstanding <= 0:
                    return jsonify({
                        "status": "error",
                        "message": "This instalment is already fully paid.",
                        "outstanding_balance": float(outstanding)
                    }), 409

                if amount > outstanding:
                    return jsonify({
                        "status": "error",
                        "message": "Payment exceeds the outstanding balance.",
                        "outstanding_balance": float(outstanding),
                        "maximum_payment": float(outstanding)
                    }), 409

                # Generate a unique transaction ID.
                transaction_id = (
                    "PAY-"
                    + date.today().strftime("%Y%m%d")
                    + "-"
                    + uuid4().hex[:12].upper()
                )

                # Save the successful payment.
                cursor.execute("""
                    INSERT INTO payments (
                        instalment_id,
                        transaction_id,
                        amount,
                        payment_method,
                        payment_status,
                        gateway_reference,
                        paid_at
                    )

                    VALUES (
                        %s, %s, %s, %s,
                        'SUCCESS', %s, CURRENT_TIMESTAMP
                    )

                    RETURNING
                        payment_id,
                        transaction_id,
                        amount,
                        payment_method,
                        payment_status,
                        paid_at;
                """, (
                    instalment_id,
                    transaction_id,
                    amount,
                    payment_method,
                    gateway_reference
                ))

                payment = cursor.fetchone()

                # Calculate the new balance and status.
                new_paid = amount_paid + amount

                new_outstanding = max(
                    Decimal("0.00"),
                    payable_amount - new_paid
                )

                new_status = get_payment_status(
                    new_paid,
                    payable_amount
                )

                # Stop instalment reminders only after that instalment is fully paid.
                if new_outstanding <= 0:
                    cursor.execute("""
                        UPDATE reminder_logs
                        SET delivery_status = 'CANCELLED'
                        WHERE instalment_id = %s
                          AND delivery_status = 'QUEUED'
                    """, (instalment_id,))
                    cursor.execute("""
                        SELECT COALESCE(SUM(GREATEST(fi.instalment_amount - fi.discount_amount - COALESCE(paid.amount_paid, 0), 0)), 0)
                        FROM students s
                        JOIN student_fee_accounts fa ON fa.student_id = s.student_id
                        JOIN fee_instalments fi ON fi.fee_account_id = fa.fee_account_id
                        LEFT JOIN LATERAL (SELECT COALESCE(SUM(p.amount), 0) amount_paid FROM payments p WHERE p.instalment_id = fi.instalment_id AND p.payment_status = 'SUCCESS') paid ON TRUE
                        WHERE s.admission_number = %s
                    """, (admission_number,))
                    if Decimal(str(cursor.fetchone()[0])) <= 0:
                        cursor.execute("""
                            UPDATE reminder_logs rl SET delivery_status = 'CANCELLED'
                            FROM fee_instalments fi
                            JOIN student_fee_accounts fa ON fa.fee_account_id = fi.fee_account_id
                            JOIN students st ON st.student_id = fa.student_id
                            WHERE rl.instalment_id = fi.instalment_id
                              AND st.admission_number = %s
                              AND rl.delivery_status = 'QUEUED'
                        """, (admission_number,))

        # PostgreSQL transaction has committed successfully.

        return jsonify({
            "status": "success",
            "message": "Payment recorded successfully.",

            "payment": {
                "payment_id": payment[0],
                "transaction_id": payment[1],
                "instalment_id": instalment_id,
                "amount": to_float(payment[2]),
                "payment_method": payment[3],
                "payment_status": payment[4],
                "paid_at": (
                    payment[5].isoformat()
                    if payment[5] else None
                )
            },

            "instalment": {
                "amount_paid": float(new_paid),
                "outstanding_balance": float(new_outstanding),
                "status": new_status
            },

            "receipt_url": url_for(
                "payment_receipt",
                transaction_id=transaction_id
            )
        }), 201

    except Exception:
        app.logger.exception("Payment recording failed")

        return jsonify({
            "status": "error",
            "message": "Payment could not be recorded."
        }), 500

    finally:
        if connection:
            connection.close()


# ============================================================
# 5. GENERATE PAYMENT RECEIPT
# ============================================================

@app.route("/api/payments/<transaction_id>/receipt")
def payment_receipt(transaction_id):

    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:

            # Retrieve receipt information from the stored transaction.
            cursor.execute("""
                SELECT
                    p.payment_id,
                    p.transaction_id,
                    p.amount,
                    p.payment_method,
                    p.payment_status,
                    p.gateway_reference,
                    p.cgst_amount,
                    p.sgst_amount,
                    p.paid_at,

                    s.admission_number,
                    s.full_name,

                    b.batch_name,

                    fi.instalment_number,

                    c.centre_name,
                    c.city

                FROM payments p

                JOIN fee_instalments fi
                    ON fi.instalment_id = p.instalment_id

                JOIN student_fee_accounts fa
                    ON fa.fee_account_id = fi.fee_account_id

                JOIN students s
                    ON s.student_id = fa.student_id

                LEFT JOIN batches b
                    ON b.batch_id = s.batch_id

                LEFT JOIN centres c
                    ON c.centre_id = s.centre_id

                WHERE p.transaction_id = %s;
            """, (transaction_id,))

            row = cursor.fetchone()

        if row is None:
            return jsonify({
                "status": "error",
                "message": "Payment transaction not found."
            }), 404

        if row[4] != "SUCCESS":
            return jsonify({
                "status": "error",
                "message": "Receipt is available only for successful payments."
            }), 409

        receipt_html = """
        <!DOCTYPE html>
        <html lang="en">

        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">

            <title>Payment Receipt - {{ transaction_id }}</title>

            <style>
                body {
                    font-family: Arial, sans-serif;
                    background: #f4f4f4;
                    margin: 0;
                    padding: 30px 15px;
                    color: #222;
                }

                .receipt {
                    max-width: 620px;
                    margin: auto;
                    background: white;
                    padding: 32px;
                    border-radius: 12px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                }

                h1 {
                    margin: 0 0 6px;
                    font-size: 25px;
                }

                .muted {
                    color: #666;
                    font-size: 13px;
                }

                .success {
                    display: inline-block;
                    margin: 20px 0;
                    padding: 8px 14px;
                    border-radius: 20px;
                    background: #e7f7ed;
                    color: #16733b;
                    font-weight: bold;
                    font-size: 13px;
                }

                .amount {
                    font-size: 32px;
                    font-weight: bold;
                    margin: 8px 0 24px;
                }

                table {
                    width: 100%;
                    border-collapse: collapse;
                }

                td {
                    padding: 12px 0;
                    border-bottom: 1px solid #eee;
                }

                td:first-child {
                    color: #666;
                }

                td:last-child {
                    text-align: right;
                    font-weight: 600;
                    overflow-wrap: anywhere;
                }

                .footer {
                    margin-top: 25px;
                    color: #777;
                    font-size: 12px;
                    line-height: 1.5;
                }

                button {
                    margin-top: 22px;
                    padding: 11px 18px;
                    border: none;
                    border-radius: 6px;
                    background: #f05a24;
                    color: white;
                    cursor: pointer;
                }

                @media print {
                    body {
                        background: white;
                        padding: 0;
                    }

                    .receipt {
                        box-shadow: none;
                    }

                    button {
                        display: none;
                    }
                }
            </style>
        </head>

        <body>

            <main class="receipt">

                <h1>{{ centre_name or "Coaching Institute" }}</h1>

                <div class="muted">{{ city or "" }}</div>

                <div class="success">
                    PAYMENT SUCCESSFUL
                </div>

                <div class="muted">Amount received</div>

                <div class="amount">
                    ₹{{ "%.2f"|format(amount) }}
                </div>

                <table>

                    <tr>
                        <td>Transaction ID</td>
                        <td>{{ transaction_id }}</td>
                    </tr>

                    <tr>
                        <td>Payment date</td>
                        <td>{{ paid_at }}</td>
                    </tr>

                    <tr>
                        <td>Student name</td>
                        <td>{{ student_name }}</td>
                    </tr>

                    <tr>
                        <td>Admission number</td>
                        <td>{{ admission_number }}</td>
                    </tr>

                    <tr>
                        <td>Batch</td>
                        <td>{{ batch_name or "—" }}</td>
                    </tr>

                    <tr>
                        <td>Instalment number</td>
                        <td>{{ instalment_number }}</td>
                    </tr>

                    <tr>
                        <td>Payment method</td>
                        <td>{{ payment_method or "—" }}</td>
                    </tr>

                    <tr>
                        <td>Gateway reference</td>
                        <td>{{ gateway_reference or "—" }}</td>
                    </tr>

                    <tr>
                        <td>CGST</td>
                        <td>₹{{ "%.2f"|format(cgst) }}</td>
                    </tr>

                    <tr>
                        <td>SGST</td>
                        <td>₹{{ "%.2f"|format(sgst) }}</td>
                    </tr>

                    <tr>
                        <td>Payment status</td>
                        <td>{{ payment_status }}</td>
                    </tr>

                </table>

                <div class="footer">
                    This receipt confirms the successful payment
                    recorded in the institute fee system.
                    It is not a GST tax invoice.
                </div>

                <button onclick="window.print()">
                    Print Receipt
                </button>

            </main>

        </body>
        </html>
        """

        return render_template_string(
            receipt_html,

            transaction_id=row[1],
            amount=to_float(row[2]),

            paid_at=(
                row[8].strftime("%d %b %Y, %I:%M %p")
                if row[8] else "—"
            ),

            student_name=row[10],
            admission_number=row[9],
            batch_name=row[11],
            instalment_number=row[12],

            payment_method=row[3],
            gateway_reference=row[5],

            cgst=to_float(row[6]),
            sgst=to_float(row[7]),

            payment_status=row[4],

            centre_name=row[13],
            city=row[14]
        )

    except Exception:
        app.logger.exception("Receipt generation failed")

        return jsonify({
            "status": "error",
            "message": "Could not generate payment receipt."
        }), 500

    finally:
        if connection:
            connection.close()



# ============================================================
# MVP EXTENSION APIs
# ============================================================

def _json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _student_exists(cursor, admission_number):
    cursor.execute(
        "SELECT admission_number, full_name FROM students WHERE admission_number = %s",
        (admission_number,)
    )
    return cursor.fetchone()


def _refund_calculation(data):
    try:
        paid = Decimal(str(data.get("amount_paid")))
        total_days = int(data.get("total_course_days"))
        attended_days = int(data.get("attended_days"))
        deductions = Decimal(str(data.get("deductions", data.get("approved_deductions", 0))))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Enter valid paid amount, course days, attended days and deductions.")

    if not paid.is_finite() or not deductions.is_finite():
        raise ValueError("Refund values must be finite numbers.")
    if paid < 0 or deductions < 0 or total_days <= 0:
        raise ValueError("Paid amount and deductions cannot be negative; course days must be positive.")
    if attended_days < 0 or attended_days > total_days:
        raise ValueError("Attended days must be between zero and total course days.")
    if paid != paid.quantize(Decimal("0.01")) or deductions != deductions.quantize(Decimal("0.01")):
        raise ValueError("Amounts cannot have more than two decimal places.")

    unused_ratio = Decimal(total_days - attended_days) / Decimal(total_days)
    gross_refund = paid * unused_ratio
    estimate = max(Decimal("0.00"), gross_refund - deductions).quantize(Decimal("0.01"))
    return paid, total_days, attended_days, deductions, estimate


@app.route("/api/parent/demo-otp", methods=["POST"])
def create_parent_demo_otp():
    data = _json_body()
    admission = str(data.get("admission_number", "")).strip()
    if not admission:
        return jsonify({"status": "error", "message": "Admission number is required."}), 400
    if os.getenv("APP_ENV", "development").lower() == "production":
        return jsonify({"status": "error", "message": "Demo OTP is disabled in production. Configure a verified OTP provider."}), 403
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            if not _student_exists(cursor, admission):
                return jsonify({"status": "error", "message": "Student not found."}), 404
        otp = f"{secrets.randbelow(1000000):06d}"
        _DEMO_OTPS[admission] = (hashlib.sha256(otp.encode()).hexdigest(), datetime.now() + timedelta(minutes=5))
        return jsonify({"status": "success", "message": "Demo OTP generated. It expires in 5 minutes.", "demo_otp": otp})
    except Exception:
        app.logger.exception("Demo OTP generation failed")
        return jsonify({"status": "error", "message": "Could not generate demo OTP."}), 500
    finally:
        if connection:
            connection.close()

@app.route("/api/parent/verify-demo-otp", methods=["POST"])
def verify_parent_demo_otp():
    data = _json_body()
    admission = str(data.get("admission_number", "")).strip()
    otp = str(data.get("otp", "")).strip()
    if not admission or not (len(otp) == 6 and otp.isdigit()):
        return jsonify({"status": "error", "message": "Enter the admission number and a valid 6-digit OTP."}), 400
    record = _DEMO_OTPS.get(admission)
    supplied_hash = hashlib.sha256(otp.encode()).hexdigest()
    if not record or record[1] <= datetime.now() or not secrets.compare_digest(record[0], supplied_hash):
        return jsonify({"status": "error", "message": "OTP is invalid or expired. Generate a new OTP."}), 400
    _DEMO_OTPS.pop(admission, None)
    token = secrets.token_urlsafe(32)
    _DEMO_PAYMENT_TOKENS[admission] = (hashlib.sha256(token.encode()).hexdigest(), datetime.now() + timedelta(minutes=30))
    return jsonify({"status": "success", "verified": True, "admission_number": admission, "verification_token": token, "message": "Demo OTP verified successfully. Payment access enabled for this demo session."})

@app.route("/api/reminders", methods=["GET", "POST"])
def reminders_api():
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            if request.method == "GET":
                admission = request.args.get("admission_number", "").strip()
                if not admission:
                    return jsonify({"status": "error", "message": "Admission number is required."}), 400
                cursor.execute("""
                    SELECT rl.reminder_id, s.admission_number, rl.message, rl.language,
                           rl.delivery_channel, rl.delivery_status, rl.scheduled_at
                    FROM reminder_logs rl
                    JOIN student_guardians sg ON sg.guardian_user_id = rl.guardian_user_id
                    JOIN students s ON s.student_id = sg.student_id
                    WHERE s.admission_number = %s
                    ORDER BY rl.scheduled_at DESC LIMIT 100
                """, (admission,))
                rows = cursor.fetchall()
                return jsonify({"status": "success", "reminders": [{
                    "id": r[0], "admission_number": r[1], "message": r[2],
                    "language": r[3], "channel": r[4],
                    "status": "SIMULATED" if r[5] == "QUEUED" else r[5],
                    "created_at": r[6].isoformat() if r[6] else None
                } for r in rows]})

            data = _json_body()
            admission = str(data.get("admission_number", "")).strip()
            language = str(data.get("language", "Hindi / English")).strip()
            if language not in ("Hindi", "English", "Hindi / English"):
                return jsonify({"status": "error", "message": "Choose Hindi, English or Hindi / English."}), 400
            cursor.execute("""
                SELECT s.student_id, s.full_name,
                       COALESCE(SUM(GREATEST(fi.instalment_amount-fi.discount_amount-COALESCE(paid.amount_paid,0),0)),0)
                FROM students s JOIN student_fee_accounts fa ON fa.student_id=s.student_id
                LEFT JOIN fee_instalments fi ON fi.fee_account_id=fa.fee_account_id
                LEFT JOIN LATERAL (SELECT COALESCE(SUM(amount),0) amount_paid FROM payments WHERE instalment_id=fi.instalment_id AND payment_status='SUCCESS') paid ON TRUE
                WHERE s.admission_number=%s GROUP BY s.student_id,s.full_name
            """, (admission,))
            row = cursor.fetchone()
            if not row:
                return jsonify({"status": "error", "message": "Student not found."}), 404
            amount = max(0, to_float(row[2]))
            if amount <= 0:
                return jsonify({"status": "error", "message": "No outstanding balance. Reminder not generated."}), 409
            cursor.execute("SELECT guardian_user_id FROM student_guardians WHERE student_id=%s ORDER BY guardian_user_id LIMIT 1", (row[0],))
            guardian = cursor.fetchone()
            if not guardian:
                return jsonify({"status": "error", "message": "No linked parent/guardian account exists for this student."}), 409
            message = f"Dear Parent, outstanding fee is ₹{amount:.2f}. Please pay by the due date. / अभिभावक जी, बकाया फीस ₹{amount:.2f} है। कृपया समय पर भुगतान करें।"
            cursor.execute("""
                INSERT INTO reminder_logs (guardian_user_id, reminder_type, language, message, delivery_channel, delivery_status, scheduled_at)
                VALUES (%s, 'OVERDUE', %s, %s, 'MOCK', 'QUEUED', CURRENT_TIMESTAMP)
                RETURNING reminder_id, scheduled_at
            """, (guardian[0], 'hi' if language == 'Hindi' else ('en' if language == 'English' else 'hi'), message))
            saved = cursor.fetchone()
        connection.commit()
        return jsonify({"status": "success", "message": "Bilingual reminder queued in simulation only; no message was sent.", "reminder": {"id": saved[0], "admission_number": admission, "amount": amount, "language": language, "status": "SIMULATED", "created_at": saved[1].isoformat()}}), 201
    except Exception:
        app.logger.exception("Reminder API failed")
        return jsonify({"status": "error", "message": "Could not process reminder request."}), 500
    finally:
        if connection:
            connection.close()

@app.route("/api/reminders/run-due", methods=["POST"])
def run_due_reminders():
    connection = None
    generated = 0
    try:
        connection = get_db_connection()
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT s.student_id, s.admission_number, fi.instalment_id, fi.due_date,
                           GREATEST(fi.instalment_amount-fi.discount_amount-COALESCE(paid.amount_paid,0),0) balance,
                           (CURRENT_DATE-fi.due_date) days_overdue
                    FROM students s JOIN student_fee_accounts fa ON fa.student_id=s.student_id
                    JOIN fee_instalments fi ON fi.fee_account_id=fa.fee_account_id
                    LEFT JOIN LATERAL (SELECT COALESCE(SUM(amount),0) amount_paid FROM payments WHERE instalment_id=fi.instalment_id AND payment_status='SUCCESS') paid ON TRUE
                    WHERE GREATEST(fi.instalment_amount-fi.discount_amount-COALESCE(paid.amount_paid,0),0)>0
                      AND (fi.due_date-CURRENT_DATE IN (3,0) OR CURRENT_DATE-fi.due_date IN (1,7,30))
                    ORDER BY fi.due_date
                """)
                for row in cursor.fetchall():
                    student_id, admission, instalment_id, due_date, balance, overdue = row
                    cursor.execute("SELECT guardian_user_id FROM student_guardians WHERE student_id=%s ORDER BY guardian_user_id LIMIT 1", (student_id,))
                    guardian = cursor.fetchone()
                    if not guardian:
                        continue
                    reminder_type = 'BEFORE_DUE' if (due_date-date.today()).days > 0 else ('DUE_TODAY' if due_date == date.today() else 'OVERDUE')
                    cursor.execute("""
                        SELECT 1 FROM reminder_logs WHERE guardian_user_id=%s AND reminder_type=%s
                          AND scheduled_at::date=CURRENT_DATE AND message LIKE %s LIMIT 1
                    """, (guardian[0], reminder_type, f'%{instalment_id}%'))
                    if cursor.fetchone():
                        continue
                    message = f"Dear Parent, instalment due {due_date:%d-%b-%Y}; outstanding ₹{to_float(balance):.2f}. / अभिभावक जी, किस्त की अंतिम तिथि {due_date:%d-%b-%Y}; बकाया ₹{to_float(balance):.2f}।"
                    cursor.execute("""
                        INSERT INTO reminder_logs (instalment_id, guardian_user_id, reminder_type, language, message, delivery_channel, delivery_status, scheduled_at)
                        VALUES (%s,%s,%s,'hi',%s,'MOCK','QUEUED',CURRENT_TIMESTAMP)
                    """, (instalment_id, guardian[0], reminder_type, message))
                    generated += 1
        return jsonify({"status": "success", "generated": generated, "message": f"Generated {generated} due-date reminder record(s). Simulation only; no messages were sent."})
    except Exception:
        app.logger.exception("Scheduled reminder generation failed")
        return jsonify({"status": "error", "message": "Could not generate scheduled reminders."}), 500
    finally:
        if connection:
            connection.close()

@app.route("/api/academics/<admission_number>")
def get_academics(admission_number):
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT student_id FROM students WHERE admission_number=%s", (admission_number,))
            student = cursor.fetchone()
            if not student:
                return jsonify({"status":"error","message":"Student not found."}),404
            student_id = student[0]
            cursor.execute("SELECT attendance_date, attendance_status FROM attendance_records WHERE student_id=%s ORDER BY attendance_date DESC LIMIT 365", (student_id,))
            attendance_rows = cursor.fetchall()
            total=len(attendance_rows); present=sum(1 for r in attendance_rows if r[1]=='PRESENT')
            cursor.execute("SELECT test_name,test_date,marks_obtained,maximum_marks,rank_position FROM test_results WHERE student_id=%s ORDER BY test_date DESC,test_name LIMIT 100", (student_id,))
            test_rows=cursor.fetchall()
        return jsonify({"status":"success","attendance_summary":{"total":total,"present":present,"percentage":round(present*100/total,2) if total else 0},"attendance":[{"date":r[0].isoformat(),"status":r[1],"remarks":None} for r in attendance_rows],"tests":[{"test_name":r[0],"date":r[1].isoformat(),"subject":"","score":to_float(r[2]),"max_score":to_float(r[3]),"rank_position":r[4],"remarks":None} for r in test_rows]})
    except Exception:
        app.logger.exception("Academic records retrieval failed")
        return jsonify({"status":"error","message":"Could not retrieve academic records."}),500
    finally:
        if connection: connection.close()




def _import_academic_csv(kind):
    if 'file' not in request.files or not request.files['file'].filename:
        return jsonify({"status":"error","message":"Choose a CSV file."}),400
    try:
        stream=io.StringIO(request.files['file'].stream.read().decode('utf-8-sig'))
        reader=csv.DictReader(stream)
        required=(['admission_number','record_date','attendance_status'] if kind=='attendance' else ['admission_number','test_name','test_date','score','max_score'])
        if not reader.fieldnames or any(x not in reader.fieldnames for x in required):
            return jsonify({"status":"error","message":"CSV headers do not match the required template."}),400
        connection=get_db_connection(); imported=0; skipped=[]
        with connection.transaction():
            with connection.cursor() as cursor:
                for line,item in enumerate(reader,start=2):
                    try:
                        admission=(item.get('admission_number') or '').strip()
                        cursor.execute("SELECT student_id FROM students WHERE admission_number=%s",(admission,)); st=cursor.fetchone()
                        if not st: raise ValueError('Unknown admission number')
                        if kind=='attendance':
                            d=date.fromisoformat((item.get('record_date') or '').strip()); status=(item.get('attendance_status') or '').strip().upper()
                            if status not in ('PRESENT','ABSENT','LEAVE'): raise ValueError('attendance_status must be PRESENT, ABSENT or LEAVE')
                            cursor.execute("INSERT INTO attendance_records(student_id,attendance_date,attendance_status) VALUES(%s,%s,%s) ON CONFLICT(student_id,attendance_date) DO UPDATE SET attendance_status=EXCLUDED.attendance_status",(st[0],d,status))
                        else:
                            name=(item.get('test_name') or '').strip(); d=date.fromisoformat((item.get('test_date') or '').strip()); score=Decimal((item.get('score') or '').strip()); maximum=Decimal((item.get('max_score') or '').strip())
                            if not name or maximum<=0 or score<0 or score>maximum: raise ValueError('Invalid test name or score range')
                            cursor.execute("INSERT INTO test_results(student_id,test_name,test_date,marks_obtained,maximum_marks) VALUES(%s,%s,%s,%s,%s)",(st[0],name,d,score,maximum))
                        imported+=1
                    except Exception as exc: skipped.append(f'Row {line}: {exc}')
        connection.close()
        return jsonify({"status":"success","imported":imported,"skipped":skipped[:20],"message":f"Imported {imported} {kind} record(s); skipped {len(skipped)} invalid row(s)."})
    except UnicodeDecodeError: return jsonify({"status":"error","message":"CSV must be UTF-8 encoded."}),400
    except Exception:
        app.logger.exception("Academic CSV import failed")
        return jsonify({"status":"error","message":"Could not import academic CSV."}),500
    finally:
        try: connection.close()
        except Exception: pass




@app.route("/api/import/attendance", methods=["POST"])
def import_attendance():
    return _import_academic_csv('attendance')


@app.route("/api/import/test-scores", methods=["POST"])
def import_test_scores():
    return _import_academic_csv('test-scores')


@app.route("/api/refunds/estimate", methods=["POST"])
def estimate_refund_api():
    try:
        _, total_days, attended_days, deductions, estimate = _refund_calculation(_json_body())
        return jsonify({"status": "success", "estimated_refund": float(estimate), "policy_note": "Illustrative pro-rata estimate: paid amount × unutilised course days ÷ total course days, less approved deductions. Final amount must follow the institute's published written refund policy and staff approval."})
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@app.route("/api/refunds/requests", methods=["POST"])
def submit_refund_request():
    data=_json_body(); admission=str(data.get('admission_number','')).strip()
    if not admission: return jsonify({"status":"error","message":"Admission number is required."}),400
    try: paid,total_days,attended_days,deductions,estimate=_refund_calculation(data)
    except ValueError as exc: return jsonify({"status":"error","message":str(exc)}),400
    connection=None
    try:
        connection=get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT s.student_id,fa.fee_account_id FROM students s JOIN student_fee_accounts fa ON fa.student_id=s.student_id WHERE s.admission_number=%s ORDER BY fa.created_at DESC LIMIT 1",(admission,))
            student=cursor.fetchone()
            if not student: return jsonify({"status":"error","message":"Student or fee account not found."}),404
            leaving_date=date.fromisoformat(str(data.get('leaving_date') or date.today().isoformat()))
            request_date=date.today(); deadline=request_date+timedelta(days=10)
            consumed=max(Decimal('0.00'),paid-estimate-deductions)
            cursor.execute("""
                INSERT INTO refund_requests(fee_account_id,request_date,leaving_date,total_course_days,elapsed_days,consumed_fee,paid_amount,approved_deductions,calculated_refund,refund_deadline,refund_status)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'REQUESTED')
                RETURNING refund_request_id,refund_deadline,refund_status
            """,(student[1],request_date,leaving_date,total_days,attended_days,consumed,paid,deductions,estimate,deadline))
            row=cursor.fetchone()
        connection.commit()
        return jsonify({"status":"success","message":"Refund request submitted for staff review. No refund has been issued.","refund_case":{"id":row[0],"estimated_refund":float(estimate),"submitted_at":request_date.isoformat(),"review_deadline":row[1].isoformat(),"status":row[2]}}),201
    except Exception:
        app.logger.exception("Refund request submission failed")
        return jsonify({"status":"error","message":"Could not submit refund request."}),500
    finally:
        if connection: connection.close()

@app.route("/api/counsellor/tasks", methods=["GET", "POST"])
def counsellor_tasks():
    connection=None
    try:
        connection=get_db_connection()
        with connection.transaction():
            with connection.cursor() as cursor:
                if request.method=='GET':
                    cursor.execute("""
                        SELECT ct.task_id,s.admission_number,r.risk_level,r.risk_score,ct.task_description,ct.task_status,ct.created_at,ct.is_false_positive
                        FROM counsellor_tasks ct JOIN students s ON s.student_id=ct.student_id
                        LEFT JOIN ai_risk_queue r ON r.risk_id=ct.risk_id
                        ORDER BY ct.created_at DESC LIMIT 200
                    """)
                    rows=cursor.fetchall()
                    return jsonify({"status":"success","tasks":[{"id":r[0],"task_id":r[0],"admission_number":r[1],"risk_level":r[2] or 'REVIEW',"risk_score":round(float(r[3] or 0)*100,1),"reason":r[4],"status":'FALSE_FLAG' if r[7] else r[5],"created_at":r[6].isoformat() if r[6] else None} for r in rows]})
                data=_json_body(); admission=str(data.get('admission_number','')).strip()
                if not admission: return jsonify({"status":"error","message":"Admission number is required."}),400
                cursor.execute("SELECT student_id FROM students WHERE admission_number=%s",(admission,)); student=cursor.fetchone()
                if not student: return jsonify({"status":"error","message":"Student not found."}),404
                student_id=student[0]
                cursor.execute("""
                    SELECT COALESCE(MAX(CURRENT_DATE-fi.due_date) FILTER(WHERE fi.due_date<CURRENT_DATE AND GREATEST(fi.instalment_amount-fi.discount_amount-COALESCE(paid.amount_paid,0),0)>0),0),
                           COALESCE(SUM(GREATEST(fi.instalment_amount-fi.discount_amount-COALESCE(paid.amount_paid,0),0)),0)
                    FROM student_fee_accounts fa LEFT JOIN fee_instalments fi ON fi.fee_account_id=fa.fee_account_id
                    LEFT JOIN LATERAL(SELECT COALESCE(SUM(amount),0) amount_paid FROM payments WHERE instalment_id=fi.instalment_id AND payment_status='SUCCESS') paid ON TRUE
                    WHERE fa.student_id=%s
                """,(student_id,)); fee=cursor.fetchone(); overdue=int(fee[0] or 0); outstanding=to_float(fee[1])
                cursor.execute("SELECT COUNT(*),COUNT(*) FILTER(WHERE attendance_status='ABSENT') FROM attendance_records WHERE student_id=%s AND attendance_date>=CURRENT_DATE-INTERVAL '30 days'",(student_id,)); attendance=cursor.fetchone(); total=int(attendance[0] or 0); absent=int(attendance[1] or 0)
                score=0.0; factors=[]
                if overdue>=30: score+=0.35; factors.append({"factor":"overdue_days","value":overdue,"weight":0.35})
                elif overdue>=7: score+=0.20; factors.append({"factor":"overdue_days","value":overdue,"weight":0.20})
                if total and absent/total>=0.30: score+=0.35; factors.append({"factor":"absence_rate","value":round(absent/total,3),"weight":0.35})
                elif total and absent/total>=0.15: score+=0.20; factors.append({"factor":"absence_rate","value":round(absent/total,3),"weight":0.20})
                if outstanding>0: score+=0.10; factors.append({"factor":"outstanding_balance","value":outstanding,"weight":0.10})
                score=min(score,1.0); level='HIGH' if score>=0.60 else ('MEDIUM' if score>=0.30 else 'LOW')
                reason='; '.join([f"Fee overdue {overdue} days" if overdue else '',f"{absent}/{total} absences in last 30 days" if total else '',f"Outstanding ₹{outstanding:.2f}" if outstanding else ''])
                reason='; '.join(x for x in reason.split('; ') if x) or 'No significant fee or attendance warning; routine counsellor review.'
                cursor.execute("INSERT INTO ai_risk_queue(student_id,risk_score,risk_level,assessment_type,contributing_factors,explanation,review_status) VALUES(%s,%s,%s,'RULE_BASED',%s::jsonb,%s::jsonb,'PENDING') RETURNING risk_id",(student_id,score,level,__import__('json').dumps(factors),__import__('json').dumps({"reason":reason})))
                risk_id=cursor.fetchone()[0]
                cursor.execute("INSERT INTO counsellor_tasks(student_id,risk_id,task_description,task_status) VALUES(%s,%s,%s,'OPEN') RETURNING task_id,created_at,task_status",(student_id,risk_id,reason))
                task=cursor.fetchone()
        return jsonify({"status":"success","message":"Counsellor review task created. No fee action or parent message was triggered.","task":{"id":task[0],"task_id":task[0],"admission_number":admission,"risk_level":level,"risk_score":round(score*100,1),"reason":reason,"status":task[2],"created_at":task[1].isoformat()}}),201
    except Exception:
        app.logger.exception("Counsellor task API failed")
        return jsonify({"status":"error","message":"Could not process counsellor task."}),500
    finally:
        if connection: connection.close()

@app.route("/api/counsellor/tasks/<int:task_id>/false-flag", methods=["POST"])
def mark_task_false_flag(task_id):
    connection=None
    try:
        connection=get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("UPDATE counsellor_tasks SET is_false_positive=TRUE,counsellor_note=COALESCE(counsellor_note,'') || %s WHERE task_id=%s AND task_status IN ('OPEN','IN_PROGRESS') RETURNING task_id",("\nMarked as false positive by reviewer.",task_id))
            row=cursor.fetchone()
            if not row: return jsonify({"status":"error","message":"Open counsellor task not found or already reviewed."}),404
            cursor.execute("UPDATE ai_risk_queue SET review_status='FALSE_POSITIVE' WHERE risk_id=(SELECT risk_id FROM counsellor_tasks WHERE task_id=%s)",(task_id,))
        connection.commit()
        return jsonify({"status":"success","message":f"Task #{task_id} marked as a false flag."})
    except Exception:
        app.logger.exception("False-flag update failed")
        return jsonify({"status":"error","message":"Could not update counsellor task."}),500
    finally:
        if connection: connection.close()

@app.route("/api/dashboard/summary")
def dashboard_summary():
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(c.centre_name, 'Unassigned') AS centre,
                       COUNT(DISTINCT s.student_id) AS students,
                       COALESCE(SUM(GREATEST(fi.instalment_amount - fi.discount_amount - COALESCE(paid.amount_paid, 0), 0)), 0) AS outstanding
                FROM students s
                JOIN student_fee_accounts fa ON fa.student_id = s.student_id
                LEFT JOIN centres c ON c.centre_id = s.centre_id
                LEFT JOIN fee_instalments fi ON fi.fee_account_id = fa.fee_account_id
                LEFT JOIN LATERAL (SELECT COALESCE(SUM(p.amount), 0) amount_paid FROM payments p WHERE p.instalment_id = fi.instalment_id AND p.payment_status = 'SUCCESS') paid ON TRUE
                GROUP BY c.centre_name ORDER BY centre
            """)
            centres = [{"centre": r[0], "students": r[1], "outstanding": to_float(r[2])} for r in cursor.fetchall()]
            cursor.execute("""
                SELECT COALESCE(b.batch_name, 'Unassigned') AS batch,
                       COUNT(DISTINCT s.student_id) AS students,
                       COALESCE(SUM(GREATEST(fi.instalment_amount - fi.discount_amount - COALESCE(paid.amount_paid, 0), 0)), 0) AS outstanding
                FROM students s
                JOIN student_fee_accounts fa ON fa.student_id = s.student_id
                LEFT JOIN batches b ON b.batch_id = s.batch_id
                LEFT JOIN fee_instalments fi ON fi.fee_account_id = fa.fee_account_id
                LEFT JOIN LATERAL (SELECT COALESCE(SUM(p.amount), 0) amount_paid FROM payments p WHERE p.instalment_id = fi.instalment_id AND p.payment_status = 'SUCCESS') paid ON TRUE
                GROUP BY b.batch_name ORDER BY batch
            """)
            batches = [{"batch": r[0], "students": r[1], "outstanding": to_float(r[2])} for r in cursor.fetchall()]
            cursor.execute("""
                SELECT
                    CASE
                        WHEN fi.due_date >= CURRENT_DATE THEN 'Not yet due'
                        WHEN CURRENT_DATE - fi.due_date BETWEEN 1 AND 30 THEN '1-30 days'
                        WHEN CURRENT_DATE - fi.due_date BETWEEN 31 AND 60 THEN '31-60 days'
                        ELSE 'Over 60 days'
                    END AS ageing_bucket,
                    COUNT(DISTINCT s.student_id) AS students,
                    COALESCE(SUM(GREATEST(fi.instalment_amount - fi.discount_amount - COALESCE(paid.amount_paid, 0), 0)), 0) AS outstanding
                FROM students s
                JOIN student_fee_accounts fa ON fa.student_id = s.student_id
                JOIN fee_instalments fi ON fi.fee_account_id = fa.fee_account_id
                LEFT JOIN LATERAL (SELECT COALESCE(SUM(p.amount), 0) amount_paid FROM payments p WHERE p.instalment_id = fi.instalment_id AND p.payment_status = 'SUCCESS') paid ON TRUE
                WHERE GREATEST(fi.instalment_amount - fi.discount_amount - COALESCE(paid.amount_paid, 0), 0) > 0
                GROUP BY ageing_bucket
                ORDER BY CASE ageing_bucket WHEN 'Not yet due' THEN 1 WHEN '1-30 days' THEN 2 WHEN '31-60 days' THEN 3 ELSE 4 END
            """)
            ageing = [{"bucket": r[0], "students": r[1], "outstanding": to_float(r[2])} for r in cursor.fetchall()]
        return jsonify({"status": "success", "centres": centres, "batches": batches, "ageing": ageing})
    except Exception:
        app.logger.exception("Dashboard summary failed")
        return jsonify({"status": "error", "message": "Could not load centre and batch summary."}), 500
    finally:
        if connection:
            connection.close()


def _csv_response(filename, headers, rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    from flask import Response
    return Response('\ufeff' + output.getvalue(), mimetype='text/csv; charset=utf-8', headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.route("/api/exports/payments.csv")
def export_payments_csv():
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.payment_id, p.transaction_id, s.admission_number, s.full_name,
                       fi.instalment_number, p.amount, p.payment_method, p.payment_status,
                       p.gateway_reference, p.paid_at
                FROM payments p
                JOIN fee_instalments fi ON fi.instalment_id = p.instalment_id
                JOIN student_fee_accounts fa ON fa.fee_account_id = fi.fee_account_id
                JOIN students s ON s.student_id = fa.student_id
                ORDER BY p.paid_at DESC NULLS LAST, p.payment_id DESC
            """)
            rows = cursor.fetchall()
        return _csv_response('coaching-payments.csv', ['Payment ID','Transaction ID','Admission Number','Student Name','Instalment Number','Amount','Payment Method','Payment Status','Gateway Reference','Paid At'], [[*r[:9], r[9].isoformat() if r[9] else ''] for r in rows])
    except Exception:
        app.logger.exception("Payment CSV export failed")
        return jsonify({"status": "error", "message": "Could not export payment records."}), 500
    finally:
        if connection:
            connection.close()


@app.route("/api/exports/tally.csv")
def export_tally_csv():
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.transaction_id, p.paid_at, s.admission_number, s.full_name,
                       p.amount, p.payment_method, p.cgst_amount, p.sgst_amount
                FROM payments p
                JOIN fee_instalments fi ON fi.instalment_id = p.instalment_id
                JOIN student_fee_accounts fa ON fa.fee_account_id = fi.fee_account_id
                JOIN students s ON s.student_id = fa.student_id
                WHERE p.payment_status = 'SUCCESS'
                ORDER BY p.paid_at, p.payment_id
            """)
            rows = cursor.fetchall()
        return _csv_response('coaching-tally-export.csv', ['Voucher Type','Voucher Date','Voucher Number','Party Name','Admission Number','Ledger Name','Amount','Payment Mode','CGST','SGST'], [['Receipt', r[1].strftime('%Y%m%d') if r[1] else '', r[0], r[3], r[2], 'Course Fees', to_float(r[4]), r[5], to_float(r[6]), to_float(r[7])] for r in rows])
    except Exception:
        app.logger.exception("Tally CSV export failed")
        return jsonify({"status": "error", "message": "Could not export Tally records."}), 500
    finally:
        if connection:
            connection.close()


# ============================================================
# UNMATCHED BANK PAYMENT RECONCILIATION QUEUE
# ============================================================

@app.route("/api/payments/unmatched", methods=["GET", "POST"])
def unmatched_payments_api():
    connection=None
    try:
        connection=get_db_connection()
        with connection.cursor() as cursor:
            if request.method=='GET':
                cursor.execute("SELECT unmatched_payment_id,transaction_id,student_reference,instalment_reference,amount,reason,review_status,created_at FROM unmatched_payments WHERE review_status='PENDING' ORDER BY created_at DESC LIMIT 200")
                rows=cursor.fetchall()
                return jsonify({"status":"success","payments":[{"id":r[0],"external_reference":r[1],"payer_name":r[2],"instalment_reference":r[3],"amount":to_float(r[4]),"notes":r[5],"status":"UNMATCHED" if r[6]=='PENDING' else r[6],"created_at":r[7].isoformat() if r[7] else None} for r in rows]})
            data=_json_body(); reference=str(data.get('external_reference',data.get('transaction_id',''))).strip(); payer=str(data.get('payer_name','')).strip() or None; notes=str(data.get('notes','')).strip() or 'Awaiting manual bank/UPI reconciliation.'
            amount=validate_amount(data.get('amount'))
            if not reference or len(reference)>200: return jsonify({"status":"error","message":"A bank/UPI reference (max 200 characters) is required."}),400
            cursor.execute("INSERT INTO unmatched_payments(transaction_id,student_reference,instalment_reference,amount,reason,review_status) VALUES(%s,%s,%s,%s,%s,'PENDING') RETURNING unmatched_payment_id,created_at",(reference,payer,data.get('instalment_reference'),amount,notes))
            row=cursor.fetchone()
        connection.commit()
        return jsonify({"status":"success","message":"Payment added to the unmatched reconciliation queue.","payment":{"id":row[0],"external_reference":reference,"payer_name":payer,"amount":float(amount),"status":"UNMATCHED","created_at":row[1].isoformat()}}),201
    except Exception as exc:
        if 'unique' in str(exc).lower() or 'duplicate' in str(exc).lower(): return jsonify({"status":"error","message":"This bank/UPI reference is already in the queue or matched."}),409
        app.logger.exception("Unmatched payment queue failed")
        return jsonify({"status":"error","message":"Could not process unmatched payment."}),500
    finally:
        if connection: connection.close()


@app.route("/api/payments/unmatched/<int:unmatched_id>/match", methods=["POST"])
def match_unmatched_payment(unmatched_id):
    data=_json_body()
    try:
        instalment_id=int(data.get('instalment_id'))
        if instalment_id<=0: raise ValueError
    except (TypeError,ValueError): return jsonify({"status":"error","message":"A valid instalment ID is required."}),400
    method=str(data.get('payment_method','BANK_TRANSFER')).strip().upper()
    if method not in ALLOWED_PAYMENT_METHODS: return jsonify({"status":"error","message":"Invalid payment method."}),400
    connection=None
    try:
        connection=get_db_connection()
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SELECT unmatched_payment_id,transaction_id,amount FROM unmatched_payments WHERE unmatched_payment_id=%s AND review_status='PENDING' FOR UPDATE",(unmatched_id,)); unmatched=cursor.fetchone()
                if not unmatched: return jsonify({"status":"error","message":"Unmatched payment not found or already reconciled."}),404
                cursor.execute("SELECT fi.instalment_amount,fi.discount_amount,s.admission_number FROM fee_instalments fi JOIN student_fee_accounts fa ON fa.fee_account_id=fi.fee_account_id JOIN students s ON s.student_id=fa.student_id WHERE fi.instalment_id=%s FOR UPDATE OF fi",(instalment_id,)); inst=cursor.fetchone()
                if not inst: return jsonify({"status":"error","message":"Target instalment not found."}),404
                cursor.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE instalment_id=%s AND payment_status='SUCCESS'",(instalment_id,)); paid=Decimal(str(cursor.fetchone()[0])); balance=max(Decimal('0.00'),Decimal(str(inst[0]))-Decimal(str(inst[1]))-paid); amount=Decimal(str(unmatched[2]))
                if amount>balance: return jsonify({"status":"error","message":f"Bank payment exceeds instalment balance of ₹{balance:.2f}.","outstanding_balance":float(balance)}),409
                transaction_id='PAY-'+date.today().strftime('%Y%m%d')+'-'+uuid4().hex[:12].upper()
                cursor.execute("INSERT INTO payments(instalment_id,transaction_id,amount,payment_method,payment_status,gateway_reference,paid_at) VALUES(%s,%s,%s,%s,'SUCCESS',%s,CURRENT_TIMESTAMP)",(instalment_id,transaction_id,amount,method,unmatched[1]))
                cursor.execute("UPDATE unmatched_payments SET review_status='MATCHED',reviewed_at=CURRENT_TIMESTAMP WHERE unmatched_payment_id=%s",(unmatched_id,))
                if amount>=balance:
                    cursor.execute("UPDATE reminder_logs SET delivery_status='CANCELLED' WHERE instalment_id=%s AND delivery_status='QUEUED'",(instalment_id,))
        return jsonify({"status":"success","message":"Unmatched payment reconciled and recorded in the student ledger.","transaction_id":transaction_id}),200
    except Exception:
        app.logger.exception("Unmatched payment matching failed")
        return jsonify({"status":"error","message":"Could not reconcile unmatched payment."}),500
    finally:
        if connection: connection.close()




# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)