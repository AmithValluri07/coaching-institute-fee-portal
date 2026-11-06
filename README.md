# Coaching Institute Fee Tracking System

Flask + PostgreSQL MVP for student fee ledgers, parent fee view, simulated payment records, reminders, academic uploads, refund estimates, counsellor tasks and CSV exports.

## Existing working features
- PostgreSQL-backed student list and instalment ledger.
- Payment recording with row locking, amount validation and prevention of overpayment.
- Successful-payment-only fee aggregation.
- Printable payment receipt with stored CGST/SGST fields.
- Demo parent OTP verification with a short-lived payment authorization token.
- Persistent simulated bilingual reminder log, due-date reminder generation, and stop-after-payment handling.
- Attendance and test-score CSV imports plus parent academic summaries.
- Illustrative pro-rata refund estimator and stored 10-day staff-review cases.
- Explainable counsellor review tasks with false-flag handling.
- Centre, batch and outstanding-ageing dashboard summaries.
- Tally-oriented and full payment CSV exports.
- Unmatched bank/UPI payment queue with instalment reconciliation.

## Setup
1. Use Python 3.10+.
2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   # Windows: .venv\\Scripts\\activate
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and set `DATABASE_URL` to the same PostgreSQL database already used by your project. Load environment variables in your deployment environment (or use `python-dotenv` in your local launcher).
4. Run the complete `migrations/001_mvp_extensions.sql` in pgAdmin Query Tool against that database. If you ran an earlier copy of this migration, run the updated file again; its create/alter statements are idempotent.
5. Run `python app.py` and open `http://127.0.0.1:5000`.

The original project used an existing `db.py` module. This package includes a standard psycopg 3 connection helper; if your local `db.py` already contains working connection settings, retain those settings or move them to `DATABASE_URL` rather than replacing them with placeholders.

## Demo-only boundaries
- `/api/parent/demo-otp` generates an OTP in the API response only in development mode. It does not send SMS. Set `APP_ENV=production` to disable the demo OTP response.
- The payment button records a simulated successful payment. It is not a payment gateway. Do not use for real money.
- Reminder records are logged as `SIMULATED`; no SMS, WhatsApp or email is sent. The due-date generator checks 3 days before, on the due date, and 1/7/30 days overdue when manually triggered. Configure a scheduled worker and messaging provider before production. A fully paid instalment stops its instalment-specific simulated reminders; general student reminders stop when the student has no outstanding dues.
- Refund estimate uses the transparent configurable formula shown in the response. The institute's actual written refund policy and deductions must replace the illustrative inputs before approving refunds.
- The risk flag is a simple explainable heuristic for counsellor review only. It never changes fee balances or contacts parents.
- Refund estimate is illustrative only because the exact approved institute refund formula was not supplied. Refund requests are stored for staff review; no refund is issued automatically.
- Unmatched-payment reconciliation is a staff demo workflow. It creates a ledger payment only after the operator supplies a valid target instalment ID and the amount does not exceed its outstanding balance.
- GST amounts in receipts are read from the existing payment fields; configure the institute's tax rules and invoice details with an accountant before treating these as tax invoices. Current receipt explicitly identifies itself as a payment receipt, not a GST tax invoice.

## CSV upload formats
Attendance CSV headers:
`admission_number,record_date,attendance_status,remarks`

Allowed attendance statuses: `PRESENT`, `ABSENT`, `LATE`, `LEAVE`.

Test score CSV headers:
`admission_number,test_name,test_date,subject,score,max_score,remarks`

Dates should use `YYYY-MM-DD`. Existing records with the same unique key are updated on re-import.

## API additions
- `POST /api/parent/demo-otp` and `POST /api/parent/verify-demo-otp` (the verified token is required for demo payments)
- `GET/POST /api/reminders` and `POST /api/reminders/run-due`
- `GET /api/academics/<admission_number>`
- `POST /api/import/attendance` and `POST /api/import/test-scores` (multipart field: `file`)
- `POST /api/refunds/estimate` and `POST /api/refunds/requests` (stores a staff-review case with a 10-day review deadline)
- `GET/POST /api/counsellor/tasks` and `POST /api/counsellor/tasks/<id>/false-flag`
- `GET /api/dashboard/summary`
- `GET /api/exports/tally.csv` and `GET /api/exports/payments.csv`
- `GET/POST /api/payments/unmatched` and `POST /api/payments/unmatched/<id>/match`

## Important before deployment
Add real parent/guardian contact mapping and verifiable parental consent for minors, production OTP provider, payment gateway callbacks with signature verification, scheduled reminder worker with payment cancellation, staff authentication/role-based authorization, audit logs, secure secret management, rate limiting, backup/restore, and the institute's approved refund/GST policy. This is a prototype/MVP extension, not a production-hardened system.

Sample CSV files are in `templates/attendance_template.csv` and `templates/test_scores_template.csv`.
