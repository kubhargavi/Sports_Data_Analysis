import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv
import matplotlib.pyplot as plt

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_URL_C = os.getenv("DATABASE_URL_C")
DATABASE_URL_T = os.getenv("DATABASE_URL_T")

def fetch_data(query, db_url):
    conn = psycopg2.connect(db_url)
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()

queries = {
    "reddit_posts": """
        SELECT 'reddit_posts' AS table_name, COUNT(*) AS count FROM (
            SELECT 
                id,
                title,
                post_id,
                content,
                subreddit,
                deleted::text AS deleted,  -- Cast boolean to text
                crawl_count,
                timestamp::timestamp AS timestamp,  -- Cast timestamp
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
                deleted::text AS deleted,
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
                deleted::text AS deleted,
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
        ) combined_reddit;
    """,
    "chan_posts": """
        SELECT 'chan_posts' AS table_name, COUNT(*) AS count FROM (
            SELECT 
                id,
                board,
                thread_id,
                subject,
                description,
                time::timestamp AS time,  -- Cast timestamp
                deleted::text AS deleted,  -- Cast boolean to text
                crawl_count,
                insertion_time,
                replies_history::text AS replies_history,  -- Cast jsonb to text
                images_history::text AS images_history,    -- Cast jsonb to text
                update_history,
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
                deleted::text AS deleted,
                crawl_count,
                insertion_time,
                replies_history::text AS replies_history,
                images_history::text AS images_history,
                update_history,
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
                deleted::text AS deleted,
                crawl_count,
                insertion_time,
                replies_history::text AS replies_history,
                images_history::text AS images_history,
                update_history,
                toxicity_class,
                toxicity_confidence
            FROM chan_2_posts
        ) combined_chan;
    """,
    "reddit_comments": """
        SELECT 'reddit_comments' AS table_name, COUNT(*) AS count FROM (
            SELECT * FROM reddit_comments
            UNION ALL
            SELECT * FROM reddit_2_comments
        ) combined_reddit_comments;
    """,
    "chan_comments": """
        SELECT 'chan_comments' AS table_name, COUNT(*) AS count FROM (
            SELECT * FROM chan_comments
            UNION ALL
            SELECT * FROM chan_2_comments
        ) combined_chan_comments;
    """,
    "toxicity_cache": "SELECT 'toxicity_cache' AS table_name, COUNT(*) AS count FROM toxicity_cache;"
}

summary = []
for name, query in queries.items():
    if name in ["reddit_posts", "chan_posts"]:
        db_url = DATABASE_URL
    elif name in ["reddit_comments", "chan_comments"]:
        db_url = DATABASE_URL_C
    else:  
        db_url = DATABASE_URL_T

    try:
        data = fetch_data(query, db_url)
        summary.append(data)
    except Exception as e:
        print(f"Error fetching data for {name}: {e}")

if summary:
    final_summary = pd.concat(summary)

    fig, ax = plt.subplots(figsize=(2, 2))
    ax.axis("tight")
    ax.axis("off")
    table = ax.table(
        cellText=final_summary.values,
        colLabels=final_summary.columns,
        loc="center",
        cellLoc="center"
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.auto_set_column_width(col=list(range(len(final_summary.columns))))

    for (row, col), cell in table.get_celld().items():
        if row == 0:  
            cell.set_text_props(weight="bold")  
            cell.set_facecolor("lightgray")  
        cell.set_edgecolor("black")  

    
    plt.savefig("dataset_summary_table.png", bbox_inches="tight", dpi=300)
    print("Table image saved as 'dataset_summary_table.png'.")
else:
    print("No data to summarize.")