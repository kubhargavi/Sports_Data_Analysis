import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
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

# Queries to fetch data
reddit_query = """
    SELECT
        toxicity_class
    FROM reddit_1_posts_copy_2
    WHERE toxicity_class IS NOT NULL
    UNION ALL
    SELECT
        toxicity_class
    FROM reddit_posts_copy
    WHERE toxicity_class IS NOT NULL
    UNION ALL
    SELECT
        toxicity_class
    FROM reddit_2_posts
    WHERE toxicity_class IS NOT NULL;
"""

chan_query = """
    SELECT
        toxicity_class
    FROM chan_1_posts_copy_2
    WHERE toxicity_class IS NOT NULL
    UNION ALL
    SELECT
        toxicity_class
    FROM chan_posts_copy
    WHERE toxicity_class IS NOT NULL
    UNION ALL
    SELECT
        toxicity_class
    FROM chan_2_posts
    WHERE toxicity_class IS NOT NULL;
"""

# Fetch data
try:
    reddit_data = fetch_data(reddit_query)
    chan_data = fetch_data(chan_query)

    # Add platform information
    reddit_data['platform'] = 'Reddit'
    chan_data['platform'] = '4chan'

    # Combine data for visualization
    combined_data = pd.concat([reddit_data, chan_data], ignore_index=True)

    # Count occurrences for each platform and toxicity class
    class_counts = combined_data.groupby(['platform', 'toxicity_class']).size().reset_index(name='count')

    # Normalize counts for relative frequency
    total_counts = class_counts.groupby('platform')['count'].transform('sum')
    class_counts['relative_frequency'] = class_counts['count'] / total_counts

    # Create the bar plot with relative frequencies
    plt.figure(figsize=(12, 6))
    sns.barplot(
        data=class_counts,
        x='toxicity_class',
        y='relative_frequency',
        hue='platform',
        palette='viridis'
    )
    plt.title('Normalized Toxicity Class Distribution Across Reddit and 4chan')
    plt.xlabel('Toxicity Class')
    plt.ylabel('Relative Frequency')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.legend(title='Platform')
    plt.savefig('figure_toxicity_class_distribution_normalized.png')
    plt.show()

    # Create the bar plot with a logarithmic scale for raw counts
    plt.figure(figsize=(12, 6))
    sns.barplot(
        data=class_counts,
        x='toxicity_class',
        y='count',
        hue='platform',
        palette='viridis'
    )
    plt.yscale('log')
    plt.title('Logarithmic Toxicity Class Distribution Across Reddit and 4chan')
    plt.xlabel('Toxicity Class')
    plt.ylabel('Log Count')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.legend(title='Platform')
    plt.savefig('figure_toxicity_class_distribution_log.png')
    plt.show()

    print("Figures saved as 'figure_toxicity_class_distribution_normalized.png' and 'figure_toxicity_class_distribution_log.png'.")

except Exception as e:
    print(f"An error occurred: {e}")
