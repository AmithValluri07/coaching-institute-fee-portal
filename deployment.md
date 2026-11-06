# Deployment & Setup Guide

## Coaching Institute Fee Tracking & Parent Portal System

### 1. Project Links

- **GitHub Repository:** https://github.com/AmithValluri07/coaching-institute-fee-portal
- **Live Application:** https://coaching-institute-fee-portal.onrender.com

### 2. Technology Stack

- Backend: Python, Flask
- Database: PostgreSQL
- Database Hosting: Supabase
- Application Hosting: Render
- Database Driver: Psycopg 3
- Production Server: Gunicorn
- Frontend: HTML, CSS, JavaScript, Bootstrap

### 3. Prerequisites

For local execution, install:

- Python 3.10 or later
- Git
- Visual Studio Code (recommended)
- PostgreSQL database access
- A modern web browser

### 4. Local Setup Instructions

**Step 1: Clone the repository**

```bash
git clone https://github.com/AmithValluri07/coaching-institute-fee-portal.git
cd coaching-institute-fee-portal
```

Alternatively, open the downloaded project folder in Visual Studio Code.

**Step 2: Create a virtual environment**

```bash
py -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

**Step 3: Install dependencies**

```bash
pip install -r requirements.txt
```

**Step 4: Configure environment variables**

Create a `.env` file in the project root directory.

Configure the following variables with your own PostgreSQL database credentials:

```env
DB_HOST=your_database_host
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_database_username
DB_PASSWORD=your_database_password
DB_SSLMODE=require
```

Do not commit the `.env` file or expose database credentials publicly.

**Step 5: Start the application**

```bash
python app.py
```

Open the local application in your browser at:

http://127.0.0.1:5000

### 5. Database Configuration

The application uses PostgreSQL hosted on Supabase.

The database contains the project tables for:

- Students and guardians
- Centres and batches
- Fee plans and instalments
- Payments and refunds
- Attendance and test results
- Reminder logs and audit logs
- AI risk queue and counsellor tasks
- User roles and authentication-related records

The database must be configured and populated before running the application.

For a fresh database setup, use the supplied database schema and migrations as applicable.

### 6. Production Deployment

The application is deployed using Render, with Supabase PostgreSQL as its database provider.

**Hosting configuration:**

- Repository: GitHub
- Branch: `main`
- Runtime: Python 3
- Build command:

```bash
pip install -r requirements.txt
```

- Start command:

```bash
gunicorn app:app --bind 0.0.0.0:$PORT
```

**Required Render environment variables:**

| Variable | Description |
|---|---|
| DB_HOST | PostgreSQL server hostname |
| DB_PORT | PostgreSQL port |
| DB_NAME | Database name |
| DB_USER | Database username |
| DB_PASSWORD | Database password |
| DB_SSLMODE | PostgreSQL SSL mode (`require`) |

Environment variable values are configured privately in the Render dashboard and are not stored in the public repository.

### 7. Live Application

The deployed application can be accessed at:

https://coaching-institute-fee-portal.onrender.com

The application uses the Supabase PostgreSQL database for its live data.

**Note:** The Render free instance may spin down after inactivity. The first request after inactivity can take additional time to load.

### 8. Project Modules

The repository includes modular components for:

- Fee ledger management
- Refund calculations
- Reminder management
- AI-based fee risk assessment
- Database operations
- Flask application routes and user interface

### 9. Reviewer Instructions

1. Open the live application URL.
2. Explore the available application features.
3. Review student fee records and instalment balances.
4. Verify payment and other available workflows using the provided demo functionality.

The application is connected to the hosted PostgreSQL database. No local database installation is required to access the deployed application.

### 10. Security Notes

- Database credentials are maintained as environment variables.
- The `.env` file must not be committed to GitHub.
- No production payment gateway or live SMS/WhatsApp integration should be assumed unless explicitly enabled.
- Demo payment functionality should be treated as a simulation, not a real financial transaction.

