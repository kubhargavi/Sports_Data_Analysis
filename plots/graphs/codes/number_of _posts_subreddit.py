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

# Query to fetch subreddit and timestamp data for posts from October onwards
reddit_query = """
    SELECT
        subreddit,
        timestamp::date AS post_date  -- Extract only the date from timestamp
    FROM reddit_1_posts_copy_2
    WHERE subreddit IS NOT NULL AND timestamp >= '2024-10-01'
    UNION ALL
    SELECT
        subreddit,
        timestamp::date AS post_date
    FROM reddit_posts_copy
    WHERE subreddit IS NOT NULL AND timestamp >= '2024-10-01'
    UNION ALL
    SELECT
        subreddit,
        timestamp::date AS post_date
    FROM reddit_2_posts
    WHERE subreddit IS NOT NULL AND timestamp >= '2024-10-01';
"""

# Fetch data
try:
    reddit_data = fetch_data(reddit_query)

    # Group data by subreddit and date
    subreddit_daily_counts = reddit_data.groupby(['subreddit', 'post_date']).size().reset_index(name='post_count')

    # Pivot the data to create a table suitable for visualization
    subreddit_pivot = subreddit_daily_counts.pivot(index='post_date', columns='subreddit', values='post_count').fillna(0)

    # Plotting
    plt.figure(figsize=(14, 7))
    subreddit_pivot.plot(kind='line', figsize=(14, 7), marker='o', linewidth=1)

    plt.title("Number of Posts in Each Subreddit (October to Date)", fontsize=16)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Number of Posts", fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.legend(title='Subreddit', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig("figure_october_to_date_posts_per_subreddit.png")
    plt.show()

    print("Figure saved as 'figure_october_to_date_posts_per_subreddit.png'.")

except Exception as e:
    print(f"An error occurred: {e}")
