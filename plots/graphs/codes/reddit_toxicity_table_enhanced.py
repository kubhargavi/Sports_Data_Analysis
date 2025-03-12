import os
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import psycopg2

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
    COUNT(*) FILTER (WHERE toxicity_class = 'normal') AS normal_posts,
    COUNT(*) FILTER (WHERE toxicity_class = 'flag') AS flagged_posts
FROM (
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
    FROM reddit_2_posts
) combined_reddit
GROUP BY subreddit
ORDER BY subreddit;
"""

reddit_data = fetch_data(reddit_query)

plt.figure(figsize=(10, 6)) 
plt.axis('off')
plt.title("Toxicity Distribution by Subreddit (Reddit) for posts", fontsize=20, fontweight="bold", pad=30)

reddit_table = plt.table(
    cellText=reddit_data.values,
    colLabels=reddit_data.columns,
    loc='center',
    cellLoc='center',
    colLoc='center'
)

reddit_table.auto_set_font_size(False)
reddit_table.set_fontsize(14) 
reddit_table.scale(1.5, 1.5)  
reddit_table.auto_set_column_width(col=list(range(len(reddit_data.columns))))
for (row, col), cell in reddit_table.get_celld().items():
    cell.set_edgecolor('black')
    if row == 0: 
        cell.set_text_props(fontweight='bold', fontsize=16)
        cell.set_facecolor('#4caf50')  
        cell.set_text_props(color='white') 
    else:
        cell.set_facecolor('#f9f9f9' if row % 2 == 0 else '#ffffff') 

plt.savefig("reddit_toxicity_table_enhanced.png", bbox_inches="tight", dpi=300)
plt.show()
