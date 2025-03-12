import psycopg2
import csv
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

QUERY = """
SELECT
    date_trunc('hour', timestamp) AS hour,
    SUM((comments_history->-1->>'value')::INTEGER) AS num_comments
FROM
    reddit_1_posts
WHERE
    subreddit = 'politics'
    AND comments_history IS NOT NULL
    AND timestamp >= '2024-11-01 00:00:00'
    AND timestamp <= '2024-11-14 23:59:59'
GROUP BY
    hour
ORDER BY
    hour;
"""

OUTPUT_FILE = "r-politics-comments-per-hour.csv"

def export_comments_to_csv():
    try:
        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()

        cursor.execute(QUERY)
        rows = cursor.fetchall()

        with open(OUTPUT_FILE, mode='w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(['hour', 'num_comments'])
            for row in rows:
                csv_writer.writerow(row)

        print(f"Data successfully exported to {OUTPUT_FILE}")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

if __name__ == "__main__":
    export_comments_to_csv()
