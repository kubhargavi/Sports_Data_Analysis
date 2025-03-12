import os
import pandas as pd
import matplotlib.pyplot as plt
import psycopg2
from dotenv import load_dotenv


load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def fetch_data(query):
    """Fetch data from the database using a query."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()

reddit_upvotes_over_time_query = """
SELECT
    time_bucket('1 day', timestamp) AS day,
    AVG((upvotes_history->-1->>'value')::int) AS avg_upvotes
FROM (
    SELECT
        id,
        title,
        post_id,
        content,
        subreddit,
        deleted::text AS deleted,  -- Cast boolean to text
        crawl_count,
        timestamp::timestamp AS timestamp,  -- Cast timestamp to ensure consistency
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
        timestamp::timestamp AS timestamp,  -- Cast timestamp to ensure consistency
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
        timestamp::timestamp AS timestamp,  -- Cast timestamp to ensure consistency
        insertion_time,
        upvotes_history,
        downvotes_history,
        comments_history,
        update_history,
        toxicity_class,
        toxicity_confidence
    FROM reddit_2_posts
) combined_reddit
WHERE timestamp >= '2024-10-01'
GROUP BY day
ORDER BY day;
"""

try:
    reddit_upvotes_over_time = fetch_data(reddit_upvotes_over_time_query)
    
    print("Reddit Upvotes Over Time Data:")
    print(reddit_upvotes_over_time)

    plt.figure(figsize=(12, 6))
    plt.plot(reddit_upvotes_over_time['day'], reddit_upvotes_over_time['avg_upvotes'], marker='o', linestyle='-', color='blue')
    plt.title('Average Upvotes Over Time (Reddit)', fontsize=16)
    plt.xlabel('Date', fontsize=14)
    plt.ylabel('Average Upvotes', fontsize=14)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.xticks(rotation=45, fontsize=10)
    plt.tight_layout()
    plt.savefig('reddit_upvotes_over_time.png')
    plt.show()

except Exception as e:
    print(f"An error occurred: {e}")