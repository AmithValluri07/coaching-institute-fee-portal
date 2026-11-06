# Technical Design Document (TDD): Coaching Institute Fee Tracking & Parent Portal

**GitHub Repository:** https://github.com/AmithValluri07/coaching-institute-fee-portal

**Live Demo:** (https://coaching-institute-fee-portal.onrender.com)

**Client:** Company A, Jaipur  
**Project:** Coaching Institute Fee Tracking & Parent Portal  
**Scope:** Engineering and Medical Entrance Coaching — 4 centres, approximately 2,600 students and 140 staff members.

---

## 1. System Architecture and Technology Choices

### 1.1 Architecture

The application follows a **modular monolithic architecture**. A single Flask application serves the frontend and exposes REST-style API endpoints. Business logic is separated into Python modules, and PostgreSQL stores the operational data.

This architecture was selected to keep the application straightforward to deploy, maintain and extend without introducing unnecessary microservice infrastructure.

### 1.2 Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | HTML5, Tailwind CSS, JavaScript | Responsive user interface and interactive screens |
| Backend | Python, Flask | API endpoints and application logic |
| Database | PostgreSQL | Persistent relational data storage |
| Database access | psycopg | PostgreSQL connectivity |
| AI decision support | Python rule-based engine | Student dropout-risk assessment |
| Data processing | Python CSV utilities | Bulk attendance and test-score imports |
| Version control | Git and GitHub | Source control and project history |

### 1.3 Backend Module Structure

- `app.py` — Flask application, API routes and integration of application modules.
- `db.py` — PostgreSQL database connection.
- `ledger_engine.py` — Instalment balances, payment validation and fee-status calculations.
- `refund_engine.py` — Pro-rata refund calculations.
- `reminder_engine.py` — Reminder timing and simulated payment/reminder workflows.
- `ai_risk_engine.py` — Rule-based student risk assessment and counsellor task logic.
- `schema.sql` — Relational database definitions.
- `index.html` — Main application interface.

---

## 2. Database Design and Data Model

PostgreSQL is used as the primary persistent database. The schema separates student information, fee accounts, instalments, payment transactions and operational review records.

### 2.1 Main Tables

| Table | Responsibility |
|---|---|
| `centres` | Coaching centre information |
| `users` | Application user records |
| `user_roles` | User-role associations |
| `otp_challenges` | OTP challenge records |
| `batches` | Student batch information |
| `students` | Student admission and profile records |
| `student_guardians` | Student-to-guardian relationships |
| `guardian_consents` | Guardian consent records |
| `fee_plans` | Fee plan definitions |
| `student_fee_accounts` | Student fee accounts and total fees |
| `fee_instalments` | Instalment amounts, discounts and due dates |
| `payments` | Payment transactions and payment status |
| `unmatched_payments` | Payments requiring manual reconciliation |
| `reminder_logs` | Reminder records and delivery status |
| `attendance_records` | Daily student attendance |
| `test_results` | Student test performance records |
| `refund_requests` | Refund requests and calculation details |
| `ai_risk_queue` | Risk assessment results and review status |
| `counsellor_tasks` | Tasks created for human review |
| `audit_logs` | Audit-related records |

### 2.2 Data Relationships

- A centre can contain multiple batches.
- A batch can contain multiple students.
- A student can have a fee account with multiple instalments.
- Each instalment can have multiple payment transactions.
- Attendance and test records are associated with individual students.
- Refund requests are associated with student fee accounts.
- Risk assessments are associated with students and can be linked to counsellor tasks.
- Unmatched payments are stored separately until they are reconciled.

Foreign keys and database constraints help maintain relationships and enforce valid data states.

---

## 3. Main Application Workflows

### 3.1 Student Fee Ledger

The fee ledger retrieves a student's fee account, instalments and payment history.

The ledger calculation considers:

- Instalment amount
- Discount amount
- Amount already paid
- Outstanding balance
- Due date

The application identifies payment states such as Paid, Part Paid, Due and Overdue.

### 3.2 Parent Portal and OTP

The parent-facing workflow provides access to relevant student fee information and payment actions through a demo OTP verification flow.

The intended workflow is:

1. Enter the student's admission reference.
2. Request a demo OTP.
3. Verify the OTP.
4. View fee details and outstanding instalments.
5. Select an instalment and initiate a demo payment.
6. View the transaction receipt after successful payment.

**Implementation limitation:** The OTP flow is for demonstration purposes. It is not a production-grade SMS OTP delivery or identity-verification service.

### 3.3 Payment Processing

The payment workflow validates the requested amount and payment method, checks the relevant instalment and its outstanding balance, and records successful demo transactions.

Important checks include:

- Positive payment amount.
- Valid instalment reference.
- Payment amount not exceeding the outstanding balance.
- Duplicate transaction prevention.
- Updating the outstanding balance after payment.
- Cancelling eligible queued reminders when an instalment is fully paid.

The application supports demonstration payments. A live payment gateway has not been integrated.

### 3.4 Payment Receipts

After a successful transaction, the application provides a receipt containing transaction and payment information for reference.

### 3.5 Fee Reminders

The reminder workflow evaluates instalment due dates and supports:

- Before-due reminders.
- Due-date reminders.
- Overdue reminders.
- English and Hindi message content.
- Avoiding repeated reminders for the same reminder event.
- Cancelling queued reminders when the instalment is fully paid.

**Implementation limitation:** Reminder generation is demonstrated within the application. Actual SMS, WhatsApp or email delivery requires external provider integration.

### 3.6 Attendance and Test Score Management

The application supports academic record management using attendance and test-result records.

Bulk CSV import templates are provided for attendance and test-score uploads. Imported records are associated with students and stored in the corresponding PostgreSQL tables.

### 3.7 Refund Processing

The refund workflow calculates a pro-rata estimate based on the course duration, elapsed days, amount paid and approved deductions.

The calculation is intended to support the refund policy described in the project requirements.

**Assumption:** The exact course-day counting convention and any permitted deductions must be confirmed against the institute's written refund policy. The ten-day refund timeline is treated as a project requirement, not as an independently verified legal-compliance claim.

### 3.8 Dashboard and Reporting

The dashboard provides fee-related summaries and supports centre/batch-level monitoring and payment ageing information.

CSV exports are provided for payment and Tally-oriented reporting.

### 3.9 Unmatched Payment Reconciliation

Payments that cannot be confidently associated with a student or instalment can be placed in an unmatched-payment queue.

An authorised reviewer can investigate and match a valid payment to the appropriate student and instalment. Reconciliation should preserve transaction traceability and prevent duplicate payment recording.

---

## 4. AI Risk Assessment and Safety

### 4.1 Risk Engine Approach

The project uses a **rule-based decision-support engine**, not a trained machine-learning prediction model.

The engine evaluates multiple student indicators:

- Overdue fee information.
- Missed instalments.
- Attendance percentage.
- Change in test performance.

The default factor weights are:

| Indicator | Weight |
|---|---:|
| Overdue fee | 0.30 |
| Missed instalments | 0.20 |
| Attendance | 0.25 |
| Test performance decline | 0.25 |
| **Total** | **1.00** |

The weighted indicators are combined into a risk score between 0 and 1.

### 4.2 Risk Classification

| Risk score | Classification |
|---|---|
| Below 0.30 | LOW |
| 0.30 to below 0.60 | MEDIUM |
| 0.60 or above | HIGH |

The engine also records contributing factors and explanations so that a reviewer can understand why a student was flagged.

### 4.3 Counsellor Review Workflow

Medium- and high-risk assessments can create counsellor review tasks.

The workflow supports:

1. Assessing student indicators.
2. Calculating a risk score.
3. Classifying the risk level.
4. Recording the assessment and explanation.
5. Creating a counsellor task where appropriate.
6. Preventing duplicate open tasks for the same student.
7. Allowing a reviewer to complete or dismiss a task.
8. Marking an incorrect assessment as a false positive.

### 4.4 Handling Incorrect or Uncertain Results

The risk score is an indicator for review, not proof that a student will drop out.

A counsellor must examine the available information before taking any action. Incorrect flags can be marked as false positives so that they are not treated as confirmed dropout cases.

**Safety guardrail:** The risk engine must not independently block classes, change fees, impose penalties, initiate refunds or send distressing messages to parents.

### 4.5 AI Implementation Limitation

The current engine uses predefined rules and sample indicators. It is not trained on historical dropout outcomes and does not claim predictive accuracy.

Persistent assessment and counsellor-task integration must be verified against the PostgreSQL database before being described as fully operational end to end.

---

## 5. UI and Design Decisions

### 5.1 Visual Design

The interface uses a dark visual theme with:

- Background: `#09090b`
- Card background: `#18181b`
- Orange accent: `#f97316`
- High-contrast text and clear status indicators.

The design aims to provide a professional dashboard while keeping important financial information visually prominent.

### 5.2 Key Screens

**Admin Dashboard**
- Centre and batch-level fee summaries.
- Outstanding dues and ageing information.
- Payment and reporting access.

**Parent Portal**
- Student fee information.
- Outstanding amount and instalment due dates.
- Payment action and receipt access.
- English/Hindi language toggle.

**Fee Ledger**
- Instalment-wise fee breakdown.
- Paid and outstanding amounts.
- Payment history and transaction status.

**Academic Records**
- Attendance and test-score information.
- Bulk CSV upload workflows.

**Counsellor and Review Workflows**
- Risk assessment information.
- Counsellor tasks.
- Unmatched payment review and reconciliation.

### 5.3 Mobile and Localization Considerations

The interface uses responsive HTML and CSS layouts to support smaller screens. A Hindi/English language toggle is included to make the parent-facing interface more accessible to users who prefer Hindi.

A key design objective is to make the outstanding amount, due date and payment action easy to identify without navigating through multiple screens.

---

## 6. Assumptions

The following assumptions were made where the project requirements did not specify every implementation detail:

1. PostgreSQL is the primary application database.
2. Payment gateway and OTP operations are demonstrated using test-mode application logic.
3. Reminder messages are generated or simulated; actual external delivery requires provider credentials and integration.
4. The AI risk engine is a rule-based decision-support mechanism rather than a trained predictive model.
5. Refund estimates use course duration, elapsed days, amount paid and approved deductions. The institute's written policy must determine the final calculation convention.
6. CSV templates define the expected structure for bulk academic uploads.
7. Sample student records are demonstration data and must not be interpreted as real student information.
8. The application is a prototype and does not claim production readiness or independently verified legal compliance.

---

## 7. Limitations and Future Improvements

### 7.1 Current Limitations

- No live payment gateway integration.
- No production SMS-based OTP delivery.
- No live WhatsApp, SMS or email reminder provider.
- AI assessment uses predefined rules and has no trained predictive model.
- Production-grade authentication, authorisation and granular role permissions require further verification and hardening.
- DPDP consent records and related workflows require a complete operational and legal review before production use.
- Production deployment, monitoring, backups and security testing remain necessary.
- End-to-end integration testing is required before treating every workflow as production-ready.

### 7.2 Future Improvements

1. Integrate a production payment gateway with secure webhook verification.
2. Add secure OTP delivery and stronger parent identity verification.
3. Integrate SMS, WhatsApp and email reminder providers.
4. Implement granular role-based access control for staff and administrators.
5. Complete verifiable parental-consent workflows and privacy controls.
6. Add automated monitoring, audit reporting and database backup procedures.
7. Evaluate the risk engine using historical outcomes before considering a trained ML model.
8. Improve automated testing, deployment pipelines and operational monitoring.
9. Integrate Tally Prime through a validated export or synchronisation workflow.

---

## 8. Conclusion

The Coaching Institute Fee Tracking and Parent Portal brings together fee ledger management, instalment tracking, payment demonstrations, receipts, reminder workflows, academic records, refund estimates, reporting and rule-based dropout-risk decision support in one application.

The modular design keeps the main business workflows separated while using a relational database for structured records. Human review is retained for sensitive AI risk decisions.

The current deliverable is a working prototype intended to demonstrate the proposed workflows. Production integrations, security hardening, policy validation and complete end-to-end testing are identified as further work.