import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Get the DATABASE_URL from the .env file
DATABASE_URL = os.getenv('DATABASE_URL')

try:
    # Connect to the PostgreSQL database
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()
    print("Connection to the database established successfully.")

    # Optionally, execute a simple query
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()
    print(f"Database version: {db_version[0]}")

except Exception as e:
    print(f"Failed to connect to the database: {e}")

finally:
    # Close the connection if it was established
    if 'connection' in locals() and connection:
        cursor.close()
        connection.close()
