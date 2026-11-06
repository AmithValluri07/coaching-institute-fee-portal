# Technical Design Document (TDD): Coaching Institute Fee Tracking & Parent Portal
**Client**: Company A, Jaipur  
**Scope**: Engineering & Medical Entrance Coaching (4 Centres, 2,600 Students, 140 Staff, ₹30–34 Cr Annual Revenue)

* **GitHub Repository**: [Insert your public GitHub URL here]
* **Live Demo / Deployed App**: [Insert live deployment URL here, if applicable]

---

## 1. System Architecture & Tech Stack
* **Architecture Choice**: Modular Monolith combining a lightweight single-page frontend with isolated Python business logic engines and a relational database. This ensures high reliability, ease of local deployment, and low maintenance overhead for 140 staff members.
* **Frontend**: Single-page application using HTML5, Tailwind CSS, and vanilla JavaScript for minimal asset weight, lightning-fast load times on low-end mobile devices, and zero heavy framework compilation dependencies.
* **Backend & Business Logic**: Modular Python scripts (`py`) handling transactional ledgers, MoE pro-rata refunds, automated WhatsApp/SMS queues, and AI risk scoring.
* **Database Relational Schema**: PostgreSQL / SQLite structured schema mapping Centres, Batches, Students, Fee Instalments, Payments (GST-compliant), and AI Risk Logs.

---

## 2. Core Business Logic & Data Model

### A. Data Model (`schema.sql`)
* **Centres**: Manages the 4 Jaipur branches (`centre_id`, `city`, `address`).
* **Batches**: Maps JEE/NEET morning and evening streams (`batch_id`, `start_date`, `end_date`).
* **Students**: Stores student demographics and DPDP Act 2023 parental consent flags (`student_id`, `dpdp_consent_verified`).
* **Fee Instalments**: Tracks individual instalment breakdowns, paid amounts, running balances, and ageing status (*Paid*, *Part Paid*, *Overdue*).
* **Payments & GST**: Records transactions with explicit CGST and SGST tax splits (`cgst`, `sgst`, `gateway_response_status`).
* **AI Risk Queue**: Logs automated risk scores and counsellor review statuses.

### B. Main Flows & Algorithms
* **Instalment Ledger Engine (`ledger_engine.py`)**: Computes running balances ($\text{Total} - \text{Paid}$) and evaluates days overdue against system dates to assign ageing labels.
* **MoE 2024 Pro-Rata Refund Engine (`refund_engine.py`)**: 
  - *Compliance*: Adheres strictly to Ministry of Education 2024 guidelines requiring pro-rata refund calculations and disbursement within 10 days.
  - *Formula*: $\text{Net Refund} = \text{Paid Amount} - \left( \frac{\text{Elapsed Days}}{\text{Total Course Days}} \times \text{Total Course Fee} \right) - \text{Non-Refundable Admin Fee}$
* **Reminders & Webhook Simulator (`reminder_engine.py`)**: Evaluates pre-due, on-due, and post-due intervals for automated bilingual (Hindi/English) notices. Listens to gateway webhooks (`/webhook/payment-success`) to instantly zero out balances and halt reminders.

---

## 3. AI Mechanism & Safety Guardrails
* **AI Dropout-Risk Engine (`ai_risk_engine.py`)**: Evaluates multi-variable student signals (payment delay $> 15$ days, attendance $< 75\%$, and declining mock test trends).
* **Hard Safety Guardrail**: To prevent erroneous penalties or automated parental distress, AI risk scores are architecturally restricted from triggering direct parent messages or fee blocks. They **strictly populate the Counsellor Task Queue** for human review and manual verification.

---

## 4. UI/UX & Design Decisions
* **Visual Aesthetic**: Crafted with a premium dark black (`#09090b`), dark grey card layout (`#18181b`), and vibrant safety-orange accents (`#f97316`) to provide a professional enterprise SaaS experience.
* **The 5-Second Dues Rule**: The Parent Portal is designed so parents can comprehend their exact financial standing within five seconds: total outstanding amount, next instalment due date, and a prominent gateway payment button.
* **Accessibility & Localization**: Features an instant Hindi/English bilingual toggle to accommodate non-English speaking parents on low-end mobile devices.
* **DPDP Act 2023 & GST**: Explicit verifiable parental consent tags and clear GST receipt breakdowns are visibly integrated.

---

## 5. Limitations & Future Scope
* **Current Scope Cuts**: Advanced multi-tenant role-based access control (RBAC) granular permissions and direct SMS/WhatsApp API gateway integrations are mocked via local simulation scripts for this initial release.
* **Next Steps**: Integrate live SMS/WhatsApp webhooks (Twilio/Interakt), implement automated Tally Prime XML daily cron syncs, and deploy native mobile wrappers for parent notifications.