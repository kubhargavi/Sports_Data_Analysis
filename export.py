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

# Queries to fetch data from Reddit and 4chan tables
reddit_query = """
    SELECT
        id,
        title,
        post_id,
        content,
        subreddit,
        deleted::text AS deleted,  -- Cast boolean to text
        crawl_count,
        timestamp::timestamp AS timestamp,
        insertion_time,
        upvotes_history,
        downvotes_history,
        comments_history,
        update_history,
        toxicity_class,
        toxicity_confidence
    FROM reddit_1_posts_copy_2
    UNION ALL
    SELECT
        id,
        title,
        post_id,
        content,
        subreddit,
        deleted::text AS deleted,  -- Cast boolean to text
        crawl_count,
        timestamp::timestamp AS timestamp,
        insertion_time,
        upvotes_history,
        downvotes_history,
        comments_history,
        update_history,
        toxicity_class,
        toxicity_confidence
    FROM reddit_posts_copy
    UNION ALL
    SELECT
        id,
        title,
        post_id,
        content,
        subreddit,
        deleted::text AS deleted,  -- Cast boolean to text
        crawl_count,
        timestamp::timestamp AS timestamp,
        insertion_time,
        upvotes_history,
        downvotes_history,
        comments_history,
        update_history,
        toxicity_class,
        toxicity_confidence
    FROM reddit_2_posts;
"""

chan_query = """
    SELECT
        id,
        board,
        thread_id,
        subject,
        description,
        time::timestamp AS time,
        deleted::text AS deleted,  -- Cast boolean to text
        replies_history,
        images_history,
        update_history,
        insertion_time,
        crawl_count,
        toxicity_class,
        toxicity_confidence
    FROM chan_1_posts_copy_2
    UNION ALL
    SELECT
        id,
        board,
        thread_id,
        subject,
        description,
        time::timestamp AS time,
        deleted::text AS deleted,  -- Cast boolean to text
        replies_history,
        images_history,
        update_history,
        insertion_time,
        crawl_count,
        toxicity_class,
        toxicity_confidence
    FROM chan_posts_copy
    UNION ALL
    SELECT
        id,
        board,
        thread_id,
        subject,
        description,
        time::timestamp AS time,
        deleted::text AS deleted,  -- Cast boolean to text
        replies_history,
        images_history,
        update_history,
        insertion_time,
        crawl_count,
        toxicity_class,
        toxicity_confidence
    FROM chan_2_posts;
"""

# Fetch and combine data
try:
    reddit_data = fetch_data(reddit_query)
    chan_data = fetch_data(chan_query)

    # Aggregate post counts
    reddit_counts = len(reddit_data)
    chan_counts = len(chan_data)

    # Plot the data
    plt.figure(figsize=(10, 6))
    plt.bar(["Reddit", "4chan"], [reddit_counts, chan_counts], color=["blue", "orange"])
    plt.title("Number of Posts in Reddit vs 4chan Datasets")
    plt.ylabel("Number of Posts")
    plt.xlabel("Platform")
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.savefig("figure_1_dataset_comparison.png")
    plt.show()

    print("Figure saved as 'figure_1_dataset_comparison.png'.")
except Exception as e:
    print(f"An error occurred: {e}")
