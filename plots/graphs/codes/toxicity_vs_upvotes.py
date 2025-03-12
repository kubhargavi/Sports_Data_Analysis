import os
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import pearsonr
from dotenv import load_dotenv
import psycopg2

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

# Query to fetch toxicity and upvotes
reddit_query = """
    SELECT
        toxicity_confidence,
        upvotes
    FROM (
        SELECT * FROM reddit_comments
        UNION ALL
        SELECT * FROM reddit_2_comments
    ) combined_reddit
    WHERE toxicity_confidence IS NOT NULL
      AND upvotes IS NOT NULL
      AND upvotes > 0; -- Ignore zero or negative upvotes
"""

# Fetch data
try:
    reddit_data = fetch_data(reddit_query)
except Exception as e:
    print(f"An error occurred: {e}")
    exit()

# Check if data exists
if reddit_data.empty:
    print("No data found for toxicity and upvotes correlation analysis.")
    exit()

# Calculate correlation
toxicity_confidence = reddit_data['toxicity_confidence']
upvotes = reddit_data['upvotes']
correlation, p_value = pearsonr(toxicity_confidence, upvotes)

print(f"Pearson Correlation Coefficient: {correlation:.2f}")
print(f"P-value: {p_value:.2e}")

# Scatter plot
plt.figure(figsize=(10, 6))
plt.scatter(toxicity_confidence, upvotes, alpha=0.6, edgecolor='k', s=50)
plt.title("Correlation Between Toxicity Confidence and Upvotes (Reddit)", fontsize=14)
plt.xlabel("Toxicity Confidence", fontsize=12)
plt.ylabel("Upvotes", fontsize=12)
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("toxicity_vs_upvotes.png")
plt.show()
