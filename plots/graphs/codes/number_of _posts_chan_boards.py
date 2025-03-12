import os
import pandas as pd
import matplotlib.pyplot as plt
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Helper function to fetch data
def fetch_data(query):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()

# Query to fetch board and timestamp data for posts from October onwards
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

# Fetch data
try:
    chan_data = fetch_data(chan_query)

    # Group data by board and date
    board_daily_counts = chan_data.groupby(['board', 'post_date']).size().reset_index(name='post_count')

    # Pivot the data to create a table suitable for visualization
    board_pivot = board_daily_counts.pivot(index='post_date', columns='board', values='post_count').fillna(0)

    # Plotting
    plt.figure(figsize=(14, 7))
    board_pivot.plot(kind='line', figsize=(14, 7), marker='o', linewidth=1)

    plt.title("Number of Posts in Each 4chan Board (October to Date)", fontsize=16)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Number of Posts", fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.legend(title='Board', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig("figure_october_to_date_posts_per_board.png")
    plt.show()

    print("Figure saved as 'figure_october_to_date_posts_per_board.png'.")

except Exception as e:
    print(f"An error occurred: {e}")
