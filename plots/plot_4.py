import psycopg2
import matplotlib.pyplot as plt
import os
from dotenv import load_dotenv
import datetime

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

def fetch_4chan_comments_data():
  
    query = """
    SELECT 
        time_bucket('1 hour', time) AS hour_bucket,
        SUM((replies_history->-1->>'value')::int) AS total_comments
    FROM 
        chan_1_posts
    WHERE 
        board = 'pol'
        AND time >= '2024-11-01 00:00:00' 
        AND time < '2024-11-15 00:00:00'
    GROUP BY 
        hour_bucket
    ORDER BY 
        hour_bucket;
    """
    try:

        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        cursor.execute(query)
        data = cursor.fetchall()
        return data
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def plot_comments_per_hour(data):

    if not data:
        print("No data to plot.")
        return


    hours = [row[0] for row in data]
    comments = [row[1] for row in data]


    plt.figure(figsize=(12, 6))
    plt.plot(hours, comments, marker='o', linestyle='-', color='b')
    plt.title("Number of Comments per Hour on 4chan /pol/ Board (Nov 1 - Nov 14, 2024)")
    plt.xlabel("Time (Hourly)")
    plt.ylabel("Total Comments")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("4chan_comments_per_hour.png")
    plt.show()

if __name__ == "__main__":
    data = fetch_4chan_comments_data()
    plot_comments_per_hour(data)
    print("Plot saved as '4chan_comments_per_hour.png'")
