-- ============================================================
-- COACHING INSTITUTE FEE TRACKING SYSTEM
-- File: schema.sql
-- Database: PostgreSQL
-- ============================================================

-- Run this schema on a new PostgreSQL database.
-- Do not run repeatedly on an existing production database
-- without reviewing migrations and existing records.

-- ============================================================
-- 1. CENTRES
-- ============================================================

CREATE TABLE centres (
    centre_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    centre_code VARCHAR(30) UNIQUE NOT NULL,
    centre_name VARCHAR(150) NOT NULL,
    city VARCHAR(100) NOT NULL,
    address TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 2. APPLICATION USERS
-- ============================================================

CREATE TABLE users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20) UNIQUE,
    password_hash TEXT,
    preferred_language VARCHAR(5) NOT NULL DEFAULT 'en'
        CHECK (preferred_language IN ('en', 'hi')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (email IS NOT NULL OR phone IS NOT NULL)
);


-- ============================================================
-- 3. USER ROLES
-- ============================================================

CREATE TABLE user_roles (
    user_id BIGINT NOT NULL REFERENCES users(user_id)
        ON DELETE CASCADE,

    role VARCHAR(40) NOT NULL
        CHECK (
            role IN (
                'PARENT',
                'ACCOUNTS_EXECUTIVE',
                'COUNSELLOR',
                'CENTRE_MANAGER',
                'ADMIN'
            )
        ),

    centre_id BIGINT REFERENCES centres(centre_id),

    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (user_id, role, centre_id)
);


-- ============================================================
-- 4. OTP AUTHENTICATION CHALLENGES
-- ============================================================

CREATE TABLE otp_challenges (
    otp_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    user_id BIGINT REFERENCES users(user_id)
        ON DELETE CASCADE,

    destination_hash TEXT NOT NULL,
    otp_hash TEXT NOT NULL,

    purpose VARCHAR(30) NOT NULL
        CHECK (
            purpose IN (
                'LOGIN',
                'PHONE_VERIFICATION',
                'CONSENT_VERIFICATION'
            )
        ),

    expires_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0
        CHECK (attempts >= 0),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 5. BATCHES
-- ============================================================

CREATE TABLE batches (
    batch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    centre_id BIGINT NOT NULL REFERENCES centres(centre_id),

    batch_code VARCHAR(40) NOT NULL,
    batch_name VARCHAR(150) NOT NULL,

    course_type VARCHAR(30) NOT NULL
        CHECK (course_type IN ('JEE', 'NEET', 'OTHER')),

    academic_year VARCHAR(20),

    start_date DATE,
    end_date DATE,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (centre_id, batch_code)
);


-- ============================================================
-- 6. STUDENTS
-- ============================================================

CREATE TABLE students (
    student_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    admission_number VARCHAR(40) UNIQUE NOT NULL,

    full_name VARCHAR(150) NOT NULL,

    centre_id BIGINT NOT NULL REFERENCES centres(centre_id),

    batch_id BIGINT REFERENCES batches(batch_id),

    date_of_birth DATE,

    admission_date DATE NOT NULL DEFAULT CURRENT_DATE,

    student_status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE'
        CHECK (
            student_status IN (
                'ACTIVE',
                'INACTIVE',
                'WITHDRAWN',
                'COMPLETED'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 7. PARENT / GUARDIAN RELATIONSHIPS
-- ============================================================

CREATE TABLE student_guardians (
    guardian_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    student_id BIGINT NOT NULL REFERENCES students(student_id)
        ON DELETE CASCADE,

    user_id BIGINT NOT NULL REFERENCES users(user_id)
        ON DELETE CASCADE,

    relationship VARCHAR(40),

    is_primary BOOLEAN NOT NULL DEFAULT FALSE,

    can_view_fees BOOLEAN NOT NULL DEFAULT TRUE,

    can_view_attendance BOOLEAN NOT NULL DEFAULT TRUE,

    can_view_scores BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (student_id, user_id)
);


-- ============================================================
-- 8. GUARDIAN CONSENT RECORDS
-- ============================================================

CREATE TABLE guardian_consents (
    consent_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    student_id BIGINT NOT NULL REFERENCES students(student_id),

    guardian_user_id BIGINT NOT NULL REFERENCES users(user_id),

    consent_type VARCHAR(50) NOT NULL
        CHECK (
            consent_type IN (
                'DATA_PROCESSING',
                'PORTAL_ACCESS',
                'COMMUNICATION'
            )
        ),

    consent_status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (
            consent_status IN (
                'PENDING',
                'VERIFIED',
                'REVOKED'
            )
        ),

    verification_method VARCHAR(50),

    verification_reference TEXT,

    policy_version VARCHAR(30),

    consent_given_at TIMESTAMPTZ,

    verified_at TIMESTAMPTZ,

    revoked_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (
        student_id,
        guardian_user_id,
        consent_type
    )
);


-- ============================================================
-- 9. FEE PLANS
-- ============================================================

CREATE TABLE fee_plans (
    fee_plan_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    plan_name VARCHAR(120) NOT NULL,

    course_type VARCHAR(30) NOT NULL,

    academic_year VARCHAR(20),

    total_fee NUMERIC(12, 2) NOT NULL
        CHECK (total_fee >= 0),

    number_of_instalments INTEGER NOT NULL DEFAULT 3
        CHECK (number_of_instalments > 0),

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 10. STUDENT FEE ACCOUNTS
-- ============================================================

CREATE TABLE student_fee_accounts (
    fee_account_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    student_id BIGINT NOT NULL REFERENCES students(student_id),

    fee_plan_id BIGINT REFERENCES fee_plans(fee_plan_id),

    total_fee NUMERIC(12, 2) NOT NULL
        CHECK (total_fee >= 0),

    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0
        CHECK (discount_amount >= 0),

    final_fee NUMERIC(12, 2)
        GENERATED ALWAYS AS (total_fee - discount_amount) STORED,

    account_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (
            account_status IN (
                'ACTIVE',
                'COMPLETED',
                'CANCELLED'
            )
        ),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (discount_amount <= total_fee)
);


-- ============================================================
-- 11. FEE INSTALMENTS
-- ============================================================

CREATE TABLE fee_instalments (
    instalment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    fee_account_id BIGINT NOT NULL
        REFERENCES student_fee_accounts(fee_account_id),

    instalment_number INTEGER NOT NULL
        CHECK (instalment_number > 0),

    instalment_amount NUMERIC(12, 2) NOT NULL
        CHECK (instalment_amount >= 0),

    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0
        CHECK (discount_amount >= 0),

    due_date DATE NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (fee_account_id, instalment_number),

    CHECK (discount_amount <= instalment_amount)
);


-- ============================================================
-- 12. PAYMENT TRANSACTIONS
-- ============================================================

CREATE TABLE payments (
    payment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    instalment_id BIGINT NOT NULL
        REFERENCES fee_instalments(instalment_id),

    transaction_id VARCHAR(150) UNIQUE NOT NULL,

    amount NUMERIC(12, 2) NOT NULL
        CHECK (amount > 0),

    payment_method VARCHAR(30)
        CHECK (
            payment_method IN (
                'UPI',
                'CARD',
                'NET_BANKING',
                'CASH',
                'BANK_TRANSFER',
                'OTHER'
            )
        ),

    payment_status VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (
            payment_status IN (
                'PENDING',
                'SUCCESS',
                'FAILED',
                'REFUNDED',
                'PARTIALLY_REFUNDED'
            )
        ),

    gateway_reference VARCHAR(200),

    gateway_payload JSONB,

    cgst_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,

    sgst_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,

    paid_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 13. UNMATCHED PAYMENT REVIEW QUEUE
-- ============================================================

CREATE TABLE unmatched_payments (
    unmatched_payment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    transaction_id VARCHAR(150) NOT NULL UNIQUE,

    student_reference VARCHAR(100),

    instalment_reference VARCHAR(100),

    amount NUMERIC(12, 2) NOT NULL
        CHECK (amount > 0),

    reason TEXT NOT NULL,

    review_status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (
            review_status IN (
                'PENDING',
                'MATCHED',
                'REJECTED'
            )
        ),

    reviewed_by BIGINT REFERENCES users(user_id),

    reviewed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 14. REMINDER HISTORY
-- ============================================================

CREATE TABLE reminder_logs (
    reminder_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    instalment_id BIGINT NOT NULL
        REFERENCES fee_instalments(instalment_id),

    guardian_user_id BIGINT REFERENCES users(user_id),

    reminder_type VARCHAR(20) NOT NULL
        CHECK (
            reminder_type IN (
                'BEFORE_DUE',
                'DUE_TODAY',
                'OVERDUE'
            )
        ),

    language VARCHAR(5) NOT NULL DEFAULT 'en'
        CHECK (language IN ('en', 'hi')),

    message TEXT NOT NULL,

    delivery_channel VARCHAR(20) NOT NULL DEFAULT 'MOCK'
        CHECK (
            delivery_channel IN (
                'MOCK',
                'SMS',
                'WHATSAPP',
                'EMAIL'
            )
        ),

    delivery_status VARCHAR(20) NOT NULL DEFAULT 'QUEUED'
        CHECK (
            delivery_status IN (
                'QUEUED',
                'SENT',
                'FAILED',
                'CANCELLED'
            )
        ),

    scheduled_at TIMESTAMPTZ,

    sent_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 15. ATTENDANCE RECORDS
-- ============================================================

CREATE TABLE attendance_records (
    attendance_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    student_id BIGINT NOT NULL REFERENCES students(student_id),

    attendance_date DATE NOT NULL,

    attendance_status VARCHAR(15) NOT NULL
        CHECK (
            attendance_status IN (
                'PRESENT',
                'ABSENT',
                'LEAVE'
            )
        ),

    marked_by BIGINT REFERENCES users(user_id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (student_id, attendance_date)
);


-- ============================================================
-- 16. TEST / EXAM RESULTS
-- ============================================================

CREATE TABLE test_results (
    result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    student_id BIGINT NOT NULL REFERENCES students(student_id),

    test_name VARCHAR(150) NOT NULL,

    test_date DATE NOT NULL,

    marks_obtained NUMERIC(8, 2) NOT NULL
        CHECK (marks_obtained >= 0),

    maximum_marks NUMERIC(8, 2) NOT NULL
        CHECK (maximum_marks > 0),

    rank_position INTEGER
        CHECK (rank_position IS NULL OR rank_position > 0),

    uploaded_by BIGINT REFERENCES users(user_id),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (marks_obtained <= maximum_marks)
);


-- ============================================================
-- 17. REFUND REQUESTS
-- ============================================================

CREATE TABLE refund_requests (
    refund_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    fee_account_id BIGINT NOT NULL
        REFERENCES student_fee_accounts(fee_account_id),

    request_date DATE NOT NULL DEFAULT CURRENT_DATE,

    leaving_date DATE NOT NULL,

    total_course_days INTEGER NOT NULL
        CHECK (total_course_days > 0),

    elapsed_days INTEGER NOT NULL
        CHECK (elapsed_days >= 0),

    consumed_fee NUMERIC(12, 2) NOT NULL DEFAULT 0
        CHECK (consumed_fee >= 0),

    paid_amount NUMERIC(12, 2) NOT NULL
        CHECK (paid_amount >= 0),

    approved_deductions NUMERIC(12, 2) NOT NULL DEFAULT 0
        CHECK (approved_deductions >= 0),

    calculated_refund NUMERIC(12, 2) NOT NULL DEFAULT 0
        CHECK (calculated_refund >= 0),

    refund_deadline DATE NOT NULL,

    refund_status VARCHAR(25) NOT NULL DEFAULT 'REQUESTED'
        CHECK (
            refund_status IN (
                'REQUESTED',
                'UNDER_REVIEW',
                'APPROVED',
                'REJECTED',
                'PROCESSED'
            )
        ),

    reviewed_by BIGINT REFERENCES users(user_id),

    reviewed_at TIMESTAMPTZ,

    processed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 18. AI / RULE-BASED RISK ASSESSMENTS
-- ============================================================

CREATE TABLE ai_risk_queue (
    risk_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    student_id BIGINT NOT NULL REFERENCES students(student_id),

    risk_score NUMERIC(5, 3) NOT NULL
        CHECK (risk_score >= 0 AND risk_score <= 1),

    risk_level VARCHAR(15) NOT NULL
        CHECK (
            risk_level IN (
                'LOW',
                'MEDIUM',
                'HIGH'
            )
        ),

    assessment_type VARCHAR(30) NOT NULL DEFAULT 'RULE_BASED',

    contributing_factors JSONB NOT NULL DEFAULT '{}'::JSONB,

    explanation JSONB NOT NULL DEFAULT '[]'::JSONB,

    review_status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (
            review_status IN (
                'PENDING',
                'REVIEWED',
                'DISMISSED',
                'FALSE_POSITIVE'
            )
        ),

    assessed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 19. COUNSELLOR TASKS
-- ============================================================

CREATE TABLE counsellor_tasks (
    task_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    student_id BIGINT NOT NULL REFERENCES students(student_id),

    risk_id BIGINT REFERENCES ai_risk_queue(risk_id),

    assigned_to BIGINT REFERENCES users(user_id),

    task_description TEXT NOT NULL,

    task_status VARCHAR(20) NOT NULL DEFAULT 'OPEN'
        CHECK (
            task_status IN (
                'OPEN',
                'IN_PROGRESS',
                'COMPLETED',
                'DISMISSED'
            )
        ),

    is_false_positive BOOLEAN NOT NULL DEFAULT FALSE,

    counsellor_note TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    completed_at TIMESTAMPTZ
);


-- ============================================================
-- 20. AUDIT LOGS
-- ============================================================

CREATE TABLE audit_logs (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    user_id BIGINT REFERENCES users(user_id),

    action VARCHAR(100) NOT NULL,

    entity_type VARCHAR(80) NOT NULL,

    entity_id VARCHAR(100),

    old_values JSONB,

    new_values JSONB,

    ip_address INET,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 21. INDEXES
-- ============================================================

CREATE INDEX idx_students_centre
    ON students(centre_id);

CREATE INDEX idx_students_batch
    ON students(batch_id);

CREATE INDEX idx_guardians_user
    ON student_guardians(user_id);

CREATE INDEX idx_instalments_due_date
    ON fee_instalments(due_date);

CREATE INDEX idx_payments_instalment
    ON payments(instalment_id);

CREATE INDEX idx_payments_status
    ON payments(payment_status);

CREATE INDEX idx_reminders_instalment
    ON reminder_logs(instalment_id);

CREATE INDEX idx_attendance_student_date
    ON attendance_records(student_id, attendance_date);

CREATE INDEX idx_test_results_student_date
    ON test_results(student_id, test_date);

CREATE INDEX idx_refunds_status
    ON refund_requests(refund_status);

CREATE INDEX idx_risk_student
    ON ai_risk_queue(student_id);

CREATE INDEX idx_counsellor_task_status
    ON counsellor_tasks(task_status);

CREATE INDEX idx_unmatched_payment_status
    ON unmatched_payments(review_status);


-- ============================================================
-- END OF SCHEMA
-- ============================================================
