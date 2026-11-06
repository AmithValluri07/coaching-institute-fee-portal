
import os
import psycopg
from dotenv import load_dotenv

# Load environment variables from .env locally
load_dotenv()


def get_db_connection():
    """Create and return a secure PostgreSQL database connection."""
    try:
        connection = psycopg.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "coaching_institute"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD"),
            sslmode=os.getenv("DB_SSLMODE", "require")
        )
        return connection

    except psycopg.Error as error:
        print(f"Database connection failed: {error}")
        raise


def test_db_connection():
    """Test whether PostgreSQL is reachable."""
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), version();")
            result = cursor.fetchone()

            print("Database connected successfully!")
            print("Database:", result[0])
            print("PostgreSQL:", result[1].split(",")[0])

    finally:
        connection.close()


if __name__ == "__main__":
    test_db_connection()
