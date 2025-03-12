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

chan_query = """
SELECT
    board,
    COUNT(*) FILTER (WHERE toxicity_class = 'normal') AS normal_posts,
    COUNT(*) FILTER (WHERE toxicity_class = 'flag') AS flagged_posts
FROM (
    SELECT 
        id,
        board,
        thread_id,
        subject,
        description,
        time::timestamp AS time,
        deleted::text AS deleted,
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
        deleted::text AS deleted,
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
        deleted::text AS deleted,
        replies_history,
        images_history,
        update_history,
        insertion_time,
        crawl_count,
        toxicity_class,
        toxicity_confidence
    FROM chan_2_posts
) combined_chan
GROUP BY board
ORDER BY board;
"""

chan_data = fetch_data(chan_query)

plt.figure(figsize=(5, 1)) 
plt.axis('off')
plt.title("Toxicity Distribution by Board (4chan) for posts", fontsize=20, fontweight="bold", pad=30)

chan_table = plt.table(
    cellText=chan_data.values,
    colLabels=chan_data.columns,
    loc='center',
    cellLoc='center',
    colLoc='center'
)

chan_table.auto_set_font_size(False)
chan_table.set_fontsize(14)  
chan_table.scale(1.5, 1.5)  
chan_table.auto_set_column_width(col=list(range(len(chan_data.columns))))
for (row, col), cell in chan_table.get_celld().items():
    cell.set_edgecolor('black')
    if row == 0: 
        cell.set_text_props(fontweight='bold', fontsize=16)
        cell.set_facecolor('#4caf50') 
        cell.set_text_props(color='white') 
    else:
        cell.set_facecolor('#f9f9f9' if row % 2 == 0 else '#ffffff')


plt.savefig("chan_toxicity_table_enhanced.png", bbox_inches="tight", dpi=300)
plt.show()
