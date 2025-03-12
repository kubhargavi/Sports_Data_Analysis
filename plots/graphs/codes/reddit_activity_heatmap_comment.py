import os
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import pearsonr
from dotenv import load_dotenv
import psycopg2
import seaborn as sns

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL_C")  # Comments database

# Helper function to fetch data
def fetch_data(query):
    conn = psycopg2.connect(DATABASE_URL)
    try:
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()

reddit_heatmap_query = """
    SELECT 
        EXTRACT(DOW FROM timestamp) AS day_of_week,
        EXTRACT(HOUR FROM timestamp) AS hour_of_day,
        COUNT(*) AS comment_count
    FROM (
        SELECT * FROM reddit_comments
        UNION ALL
        SELECT * FROM reddit_2_comments
    ) combined_reddit
    WHERE timestamp >= '2024-10-01'
    GROUP BY day_of_week, hour_of_day
    ORDER BY day_of_week, hour_of_day;
"""

# Fetch data
try:
    reddit_activity = fetch_data(reddit_heatmap_query)
except Exception as e:
    print(f"An error occurred: {e}")
    exit()

# Check if data exists
if reddit_activity.empty:
    print("No data found for Reddit activity heatmap.")
    exit()

# Create pivot table
reddit_activity_pivot = reddit_activity.pivot_table(
    index="day_of_week", columns="hour_of_day", values="comment_count", fill_value=0
)

# Plot heatmap
plt.figure(figsize=(12, 8))
sns.heatmap(
    reddit_activity_pivot,
    cmap="YlGnBu",
    linewidths=0.5,
    cbar_kws={'label': 'Comment Count'},
    square=True
)
plt.title("Reddit Comment Activity Heatmap (Daily & Hourly)", fontsize=14)
plt.xlabel("Hour of Day", fontsize=12)
plt.ylabel("Day of Week", fontsize=12)
plt.tight_layout()
plt.savefig("reddit_activity_heatmap.png")
plt.show()