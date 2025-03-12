import psycopg2
import matplotlib.pyplot as plt
import datetime
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

def fetch_hourly_comments_data():
   
    query = """
    SELECT 
        time_bucket('1 hour', timestamp) AS hour,
        SUM((comments_history->-1->>'value')::int) AS total_comments
    FROM reddit_1_posts
    WHERE subreddit = 'politics'
    AND timestamp BETWEEN '2024-11-01 00:00:00' AND '2024-11-14 23:59:59'
    GROUP BY hour
    ORDER BY hour;
    """
    try:

        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()

     
        cursor.execute(query)
        rows = cursor.fetchall()

        hours = [row[0] for row in rows]
        comments_count = [row[1] for row in rows]

        cursor.close()
        connection.close()
        return hours, comments_count

    except Exception as e:
        print(f"Error fetching data: {e}")
        return [], []

def plot_hourly_comments(hours, comments_count):

    plt.figure(figsize=(12, 7))
    plt.plot(hours, comments_count, marker='o', linestyle='-', color='purple')
    plt.title("Number of Comments per Hour in r/politics (Nov 1 - Nov 14, 2024)")
    plt.xlabel("Date and Hour")
    plt.ylabel("Number of Comments")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.savefig("hourly_comments_plot.png")
    print("Plot saved as 'hourly_comments_plot.png'")
    plt.show()

if __name__ == "__main__":
    hours, comments_count = fetch_hourly_comments_data()
    if hours and comments_count:
        plot_hourly_comments(hours, comments_count)
