-- Coaching Fee Portal MVP extension tables.
-- Run this complete, idempotent migration against the same PostgreSQL database used by app.py. Re-run after updates if an earlier version was applied.
-- Existing student/payment tables are intentionally not modified.

CREATE TABLE IF NOT EXISTS parent_demo_otps (
    otp_id BIGSERIAL PRIMARY KEY,
    admission_number VARCHAR(40) NOT NULL,
    otp_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_parent_demo_otps_lookup
    ON parent_demo_otps(admission_number, created_at DESC);

CREATE TABLE IF NOT EXISTS fee_reminder_events (
    reminder_id BIGSERIAL PRIMARY KEY,
    admission_number VARCHAR(40) NOT NULL,
    amount NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    language VARCHAR(20) NOT NULL CHECK (language IN ('Hindi','English','Hindi / English')),
    channel VARCHAR(20) NOT NULL DEFAULT 'DEMO',
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'SIMULATED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fee_reminder_admission
    ON fee_reminder_events(admission_number, created_at DESC);

CREATE TABLE IF NOT EXISTS student_attendance (
    attendance_id BIGSERIAL PRIMARY KEY,
    admission_number VARCHAR(40) NOT NULL,
    record_date DATE NOT NULL,
    attendance_status VARCHAR(10) NOT NULL CHECK (attendance_status IN ('PRESENT','ABSENT','LATE','LEAVE')),
    remarks TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(admission_number, record_date)
);

CREATE TABLE IF NOT EXISTS student_test_scores (
    test_score_id BIGSERIAL PRIMARY KEY,
    admission_number VARCHAR(40) NOT NULL,
    test_name VARCHAR(150) NOT NULL,
    test_date DATE NOT NULL,
    subject VARCHAR(100) NOT NULL,
    score NUMERIC(10,2) NOT NULL CHECK (score >= 0),
    max_score NUMERIC(10,2) NOT NULL CHECK (max_score > 0 AND score <= max_score),
    remarks TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(admission_number, test_name, test_date, subject)
);

CREATE TABLE IF NOT EXISTS counsellor_tasks (
    task_id BIGSERIAL PRIMARY KEY,
    admission_number VARCHAR(40) NOT NULL,
    risk_level VARCHAR(10) NOT NULL CHECK (risk_level IN ('LOW','MEDIUM','HIGH')),
    risk_score INTEGER NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    reason TEXT NOT NULL,
    task_status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (task_status IN ('OPEN','IN_PROGRESS','CLOSED','FALSE_FLAG')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_counsellor_tasks_status
    ON counsellor_tasks(task_status, created_at DESC);

ALTER TABLE fee_reminder_events ADD COLUMN IF NOT EXISTS instalment_id BIGINT;
ALTER TABLE fee_reminder_events ADD COLUMN IF NOT EXISTS schedule_key VARCHAR(30);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fee_reminder_instalment_schedule
    ON fee_reminder_events(instalment_id, schedule_key)
    WHERE instalment_id IS NOT NULL AND schedule_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS refund_cases (
    refund_case_id BIGSERIAL PRIMARY KEY,
    admission_number VARCHAR(40) NOT NULL,
    amount_paid NUMERIC(12,2) NOT NULL CHECK (amount_paid >= 0),
    total_course_days INTEGER NOT NULL CHECK (total_course_days > 0),
    attended_days INTEGER NOT NULL CHECK (attended_days >= 0 AND attended_days <= total_course_days),
    approved_deductions NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (approved_deductions >= 0),
    estimated_refund NUMERIC(12,2) NOT NULL CHECK (estimated_refund >= 0),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deadline_at TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '10 days'),
    case_status VARCHAR(20) NOT NULL DEFAULT 'PENDING_REVIEW'
);


-- Demo parent verification token used to authorize the parent-portal payment flow.
ALTER TABLE parent_demo_otps ADD COLUMN IF NOT EXISTS verification_token_hash CHAR(64);


-- Bank/UPI credits that have not yet been mapped to a student instalment.
CREATE TABLE IF NOT EXISTS unmatched_payments (
    unmatched_payment_id BIGSERIAL PRIMARY KEY,
    external_reference VARCHAR(200) NOT NULL UNIQUE,
    payer_name VARCHAR(200),
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    payment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'UNMATCHED' CHECK (status IN ('UNMATCHED','MATCHED','IGNORED')),
    notes TEXT,
    matched_transaction_id VARCHAR(80),
    matched_instalment_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_unmatched_payments_status_date
    ON unmatched_payments(status, payment_date DESC);