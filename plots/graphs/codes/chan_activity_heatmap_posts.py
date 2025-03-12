import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from dotenv import load_dotenv
import psycopg2
from matplotlib.colors import LogNorm

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

# Corrected query for 4chan data
chan_query = """
    SELECT 
        COALESCE(time, insertion_time) AS timestamp  -- Use time or fallback to insertion_time
    FROM (
        SELECT 
            id,
            board,
            thread_id,
            subject,
            description,
            time, 
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
            time,
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
            time,
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
    WHERE COALESCE(time, insertion_time) >= '2024-10-01';
"""

# Fetch data
chan_data = fetch_data(chan_query)

# Prepare data for the heatmap
chan_data['timestamp'] = pd.to_datetime(chan_data['timestamp'])
chan_data['hour'] = chan_data['timestamp'].dt.hour
chan_data['day_of_week'] = chan_data['timestamp'].dt.dayofweek  # 0=Monday, 6=Sunday

# Group by hour and day of the week
grouped = chan_data.groupby(['day_of_week', 'hour']).size().reset_index(name='count')

# Pivot data for heatmap
heatmap_data = grouped.pivot(index='day_of_week', columns='hour', values='count').fillna(0)

# Plot heatmap
plt.figure(figsize=(12, 8))
plt.imshow(heatmap_data, cmap='magma', aspect='auto', interpolation='nearest', norm=LogNorm(vmin=1))

# Add labels and titles
plt.title("4chan Activity Heatmap (Posts)", fontsize=16)
plt.xlabel("Hour of Day", fontsize=12)
plt.ylabel("Day of Week", fontsize=12)

# Add colorbar
cbar = plt.colorbar()
cbar.set_label('Number of Posts (Log Scale)', fontsize=12)

# Customize ticks
plt.xticks(np.arange(24), [str(h) for h in range(24)])
plt.yticks(np.arange(7), ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])

# Show plot
plt.tight_layout()
plt.savefig("chan_activity_heatmap.png")
plt.show()
