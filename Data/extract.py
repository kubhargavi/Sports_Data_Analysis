import os
import psycopg2
import pandas as pd
import json
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

# Check if the DATABASE_URL is loaded correctly
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    logging.error("Error: DATABASE_URL environment variable is not set")
    exit(1)
else:
    logging.info(f"Using DATABASE_URL: {DATABASE_URL}")

# Establish a connection to the database
try:
    connection = psycopg2.connect(DATABASE_URL)
    cursor = connection.cursor()
    logging.info("Database connection established successfully")
except Exception as e:
    logging.error(f"Error connecting to the database: {e}")
    exit(1)

# Query to fetch data
query = """
SELECT * FROM reddit_posts
"""

try:
    # Load data into a pandas DataFrame
    logging.info("Executing query to fetch data...")
    df = pd.read_sql_query(query, connection)
    
    if df.empty:
        logging.warning("No data found in the table.")
    else:
        logging.info(f"Fetched {len(df)} records from the database.")

    # 1. Export to CSV
    csv_path = 'reddit_posts.csv'
    df.to_csv(csv_path, index=False)
    logging.info(f"Data exported to CSV: {csv_path}")

    # 2. Export to JSON
    json_path = 'reddit_posts.json'
    df.to_json(json_path, orient='records', indent=2)
    logging.info(f"Data exported to JSON: {json_path}")

except Exception as e:
    logging.error(f"Error during data extraction or file export: {e}")
finally:
    # Clean up database resources
    if cursor:
        cursor.close()
    if connection:
        connection.close()
    logging.info("Database connection closed.")
