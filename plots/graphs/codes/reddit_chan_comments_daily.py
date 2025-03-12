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

reddit_query = """
    SELECT 
        subreddit,
        time_bucket('1 day', timestamp) AS day,
        SUM((comments_history->-1->>'value')::int) AS total_comments
    FROM (
        SELECT
            id,
            title,
            post_id,
            content,
            subreddit,
            deleted::text AS deleted,  -- Ensure consistent type
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
            deleted::text AS deleted,  -- Ensure consistent type
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
            deleted::text AS deleted,  -- Ensure consistent type
            crawl_count,
            timestamp::timestamp AS timestamp,
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
    GROUP BY subreddit, day
    ORDER BY day;
"""

chan_query = """
    SELECT 
        board,
        time_bucket('1 day', time) AS day,
        SUM((replies_history->-1->>'value')::int) AS total_replies
    FROM (
        SELECT
            id,
            board,
            thread_id,
            subject,
            description,
            time,
            deleted::text AS deleted,  -- Ensure consistent type
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
            time,
            deleted::text AS deleted,  -- Ensure consistent type
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
            time,
            deleted::text AS deleted,  -- Ensure consistent type
            replies_history,
            images_history,
            update_history,
            insertion_time,
            crawl_count,
            toxicity_class,
            toxicity_confidence
        FROM chan_2_posts
    ) combined_chan
    WHERE time >= '2024-10-01'
    GROUP BY board, day
    ORDER BY day;
"""

try:
    reddit_data = fetch_data(reddit_query)
    chan_data = fetch_data(chan_query)

    plt.figure(figsize=(12, 6))
    for subreddit in reddit_data['subreddit'].unique():
        subset = reddit_data[reddit_data['subreddit'] == subreddit]
        plt.plot(subset['day'], subset['total_comments'], label=subreddit)
    plt.title("Daily Number of Comments on Reddit by Subreddit (Since October)", fontsize=16)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Number of Comments", fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.legend(title="Subreddit", fontsize=10)
    plt.tight_layout()
    plt.savefig("reddit_comments_daily.png")
    plt.show()

    plt.figure(figsize=(12, 6))
    for board in chan_data['board'].unique():
        subset = chan_data[chan_data['board'] == board]
        plt.plot(subset['day'], subset['total_replies'], label=board)
    plt.title("Daily Number of Comments on Chan by Board (Since October)", fontsize=16)
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Number of Comments", fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.legend(title="Board", fontsize=10)
    plt.tight_layout()
    plt.savefig("chan_comments_daily.png")
    plt.show()

    print("Plots saved as 'reddit_comments_daily.png' and 'chan_comments_daily.png'.")

except Exception as e:
    print(f"An error occurred: {e}")