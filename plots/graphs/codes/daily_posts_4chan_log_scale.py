import os
import pandas as pd
import matplotlib.pyplot as plt
import psycopg2
from dotenv import load_dotenv


load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def fetch_data(query):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()

chan_query = """
    SELECT
        board,
        time::date AS post_date  -- Extract only the date from time
    FROM chan_1_posts_copy_2
    WHERE board IS NOT NULL AND time >= '2024-10-01'
    UNION ALL
    SELECT
        board,
        time::date AS post_date
    FROM chan_posts_copy
    WHERE board IS NOT NULL AND time >= '2024-10-01'
    UNION ALL
    SELECT
        board,
        time::date AS post_date
    FROM chan_2_posts
    WHERE board IS NOT NULL AND time >= '2024-10-01';
"""

try:
    chan_data = fetch_data(chan_query)

    board_daily_counts = chan_data.groupby(['board', 'post_date']).size().reset_index(name='post_count')

    board_pivot = board_daily_counts.pivot(index='post_date', columns='board', values='post_count').fillna(0)

    plt.figure(figsize=(14, 7))
    board_pivot.plot(kind='line', marker='o', linewidth=1, figsize=(14, 7))

    plt.yscale("log")  
    plt.title("Number of Posts in each board", fontsize=16)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Number of Posts (Log Scale)", fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.legend(title='Board', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()

    # Save the figure
    plt.savefig("daily_posts_4chan_log_scale.png")
    plt.show()

    print("Figure saved as 'daily_posts_4chan_log_scale.png'.")

except Exception as e:
    print(f"An error occurred: {e}")