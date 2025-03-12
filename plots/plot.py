import psycopg2
import matplotlib.pyplot as plt
import datetime
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

def fetch_submissions_data():
    query = """
    SELECT 
        time_bucket('1 day', timestamp) AS day,
        COUNT(post_id) AS submissions
    FROM reddit_1_posts
    WHERE subreddit = 'politics'
    AND timestamp BETWEEN '2024-11-01 00:00:00' AND '2024-11-14 23:59:59'
    GROUP BY day
    ORDER BY day;
    """
    try:

        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()


        cursor.execute(query)
        rows = cursor.fetchall()


        dates = [row[0] for row in rows]
        submissions = [row[1] for row in rows]

        cursor.close()
        connection.close()
        return dates, submissions

    except Exception as e:
        print(f"Error fetching data: {e}")
        return [], []

def plot_submissions(dates, submissions):
   
    plt.figure(figsize=(10, 6))
    plt.plot(dates, submissions, marker='o', linestyle='-', color='b')
    plt.title("Number of Submissions in r/politics (Nov 1 - Nov 14, 2024)")
    plt.xlabel("Date")
    plt.ylabel("Number of Submissions")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.savefig("submissions_plot.png")
    print("Plot saved as 'submissions_plot.png'")
    plt.show()

if __name__ == "__main__":
    dates, submissions = fetch_submissions_data()
    if dates and submissions:
        plot_submissions(dates, submissions)
