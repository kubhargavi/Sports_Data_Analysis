import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from flask import Flask, render_template, request
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

load_dotenv()

DB_URL = os.getenv('DATABASE_URL')      # crawler
DB_URL_C = os.getenv('DATABASE_URL_C')  # comments
DB_URL_T = os.getenv('DATABASE_URL_T')  # toxicity

app = Flask(__name__)

def query_db(db_url, query, params=None):
    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(query, params if params else ())
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

dataset_summary_queries = {
    "reddit_posts": """
        SELECT 'reddit_posts' AS table_name, COUNT(*) AS count FROM (
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
                time::timestamp AS time,
                deleted::text AS deleted,
                crawl_count,
                insertion_time,
                replies_history::text AS replies_history,
                images_history::text AS images_history,
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

def get_dataset_summary():
    summary = []
    summary += query_db(DB_URL, dataset_summary_queries["reddit_posts"])
    summary += query_db(DB_URL, dataset_summary_queries["chan_posts"])
    summary += query_db(DB_URL_C, dataset_summary_queries["reddit_comments"])
    summary += query_db(DB_URL_C, dataset_summary_queries["chan_comments"])
    summary += query_db(DB_URL_T, dataset_summary_queries["toxicity_cache"])
    return summary

@app.route('/')
def index():
    return render_template('index.html')

#Dataset Analysis
@app.route('/datasets_analysis', methods=['GET', 'POST'])
def datasets_analysis():
    dataset_summary = get_dataset_summary()

    reddit_toxicity_query = """
        SELECT toxicity_class FROM reddit_1_posts_copy_2 WHERE toxicity_class IS NOT NULL
        UNION ALL
        SELECT toxicity_class FROM reddit_posts_copy WHERE toxicity_class IS NOT NULL
        UNION ALL
        SELECT toxicity_class FROM reddit_2_posts WHERE toxicity_class IS NOT NULL;
    """

    chan_toxicity_query = """
        SELECT toxicity_class FROM chan_1_posts_copy_2 WHERE toxicity_class IS NOT NULL
        UNION ALL
        SELECT toxicity_class FROM chan_posts_copy WHERE toxicity_class IS NOT NULL
        UNION ALL
        SELECT toxicity_class FROM chan_2_posts WHERE toxicity_class IS NOT NULL;
    """

    reddit_posts_query = """
        SELECT id, timestamp FROM reddit_1_posts_copy_2
        UNION ALL
        SELECT id, timestamp FROM reddit_posts_copy
        UNION ALL
        SELECT id, timestamp FROM reddit_2_posts;
    """

    chan_posts_query = """
        SELECT id, COALESCE(time, insertion_time) as timestamp FROM chan_1_posts_copy_2
        UNION ALL
        SELECT id, COALESCE(time, insertion_time) as timestamp FROM chan_posts_copy
        UNION ALL
        SELECT id, COALESCE(time, insertion_time) as timestamp FROM chan_2_posts;
    """

    toxicity_plot_url = None
    toxicity_message = None

    posts_plot_url = None
    posts_message = None

    if request.method == 'POST':
        if 'submit_toxicity' in request.form:
            chosen_class = request.form.get('toxicity_class_filter')
            data_source = request.form.get('data_source_filter')

            reddit_data = query_db(DB_URL, reddit_toxicity_query)
            chan_data = query_db(DB_URL, chan_toxicity_query)
            df_reddit = pd.DataFrame(reddit_data)
            df_chan = pd.DataFrame(chan_data)

            if data_source == 'reddit':
                combined = df_reddit
            elif data_source == '4chan':
                combined = df_chan
            else:
                combined = pd.concat([df_reddit, df_chan], ignore_index=True)

            if chosen_class and chosen_class.strip():
                combined = combined[combined['toxicity_class'] == chosen_class.strip()]

            if combined.empty:
                toxicity_message = "No data found for the selected parameters."
            else:
                class_counts = combined['toxicity_class'].value_counts().reset_index()
                class_counts.columns = ['toxicity_class', 'count']
                plt.figure(figsize=(6,4))
                sns.barplot(x='toxicity_class', y='count', data=class_counts, color='purple')
                title_str = "Toxicity Class Distribution"
                if data_source == 'reddit':
                    title_str += " (Reddit)"
                elif data_source == '4chan':
                    title_str += " (4chan)"
                else:
                    title_str += " (Reddit & 4chan)"
                plt.title(title_str)
                plt.xlabel("Toxicity Class")
                plt.ylabel("Count")
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                toxicity_plot_url = f"/static/{filename}"
                toxicity_message = f"Found {len(combined)} entries."

        elif 'submit_posts' in request.form:
            chosen_platform = request.form.get('platform_choice')
            df_reddit = pd.DataFrame(query_db(DB_URL, reddit_posts_query))
            df_chan = pd.DataFrame(query_db(DB_URL, chan_posts_query))

            if chosen_platform == 'reddit':
                if df_reddit.empty:
                    posts_message = "No reddit posts found."
                else:
                    count = len(df_reddit)
                    plt.figure(figsize=(3,4))
                    sns.barplot(x=['Reddit'], y=[count], color='blue')
                    plt.title("Number of Posts - Reddit")
                    plt.ylabel("Count")
                    plt.tight_layout()
                    filename = f"plot_{uuid.uuid4()}.png"
                    filepath = os.path.join('static', filename)
                    plt.savefig(filepath)
                    plt.close()
                    posts_plot_url = f"/static/{filename}"
                    posts_message = f"Reddit posts: {count}"
            elif chosen_platform == '4chan':
                if df_chan.empty:
                    posts_message = "No 4chan posts found."
                else:
                    count = len(df_chan)
                    plt.figure(figsize=(3,4))
                    sns.barplot(x=['4chan'], y=[count], color='green')
                    plt.title("Number of Posts - 4chan")
                    plt.ylabel("Count")
                    plt.tight_layout()
                    filename = f"plot_{uuid.uuid4()}.png"
                    filepath = os.path.join('static', filename)
                    plt.savefig(filepath)
                    plt.close()
                    posts_plot_url = f"/static/{filename}"
                    posts_message = f"4chan posts: {count}"
            else:
                counts = pd.DataFrame({
                    'platform': ['Reddit', '4chan'],
                    'count': [len(df_reddit), len(df_chan)]
                })
                plt.figure(figsize=(6,4))
                sns.barplot(x='platform', y='count', data=counts, palette='Set2')
                plt.title("Number of Posts: Reddit vs 4chan")
                plt.xlabel("Platform")
                plt.ylabel("Count")
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                posts_plot_url = f"/static/{filename}"
                posts_message = f"Reddit: {len(df_reddit)} posts, 4chan: {len(df_chan)} posts"

    return render_template('datasets_analysis.html',
                           dataset_summary=dataset_summary,
                           toxicity_plot_url=toxicity_plot_url,
                           toxicity_message=toxicity_message,
                           posts_plot_url=posts_plot_url,
                           posts_message=posts_message)

#Reddit
@app.route('/reddit_analysis', methods=['GET', 'POST'])
def reddit_analysis():
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
        "reddit_comments": """
            SELECT 'reddit_comments' AS table_name, COUNT(*) AS count FROM (
                SELECT * FROM reddit_comments
                UNION ALL
                SELECT * FROM reddit_2_comments
            ) combined_reddit_comments;
        """
    }

    reddit_dataset_summary = []
    reddit_dataset_summary += query_db(DB_URL, queries["reddit_posts"])
    reddit_dataset_summary += query_db(DB_URL_C, queries["reddit_comments"])

    subreddit_query = """
    SELECT DISTINCT subreddit FROM (
        SELECT subreddit FROM reddit_1_posts_copy_2
        UNION ALL
        SELECT subreddit FROM reddit_posts_copy
        UNION ALL
        SELECT subreddit FROM reddit_2_posts
    ) t
    WHERE subreddit IS NOT NULL
    ORDER BY subreddit;
    """
    subreddits_result = query_db(DB_URL, subreddit_query)
    subreddit_list = [r['subreddit'] for r in subreddits_result]

    upvotes_query_template = """
    SELECT
        time_bucket('1 day', timestamp) AS day,
        AVG((upvotes_history->-1->>'value')::int) AS avg_upvotes
    FROM (
        SELECT
            id, title, post_id, content, subreddit, deleted::text as deleted, crawl_count,
            timestamp::timestamp as timestamp, insertion_time,
            upvotes_history, downvotes_history, comments_history, update_history,
            toxicity_class, toxicity_confidence
        FROM reddit_1_posts_copy_2
        UNION ALL
        SELECT
            id, title, post_id, content, subreddit, deleted::text as deleted, crawl_count,
            timestamp::timestamp as timestamp, insertion_time,
            upvotes_history, downvotes_history, comments_history, update_history,
            toxicity_class, toxicity_confidence
        FROM reddit_posts_copy
        UNION ALL
        SELECT
            id, title, post_id, content, subreddit, deleted::text as deleted, crawl_count,
            timestamp::timestamp as timestamp, insertion_time,
            upvotes_history, downvotes_history, comments_history, update_history,
            toxicity_class, toxicity_confidence
        FROM reddit_2_posts
    ) combined_reddit
    WHERE 1=1
    {date_filter}
    GROUP BY day
    ORDER BY day;
    """

    correlation_query = """
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
      AND upvotes > 0
    """

    toxicity_dist_query = """
    SELECT
        subreddit,
        COUNT(*) FILTER (WHERE toxicity_class = 'normal') AS normal_posts,
        COUNT(*) FILTER (WHERE toxicity_class = 'flag') AS flagged_posts
    FROM (
        SELECT 
            id, title, post_id, content, subreddit, deleted::text as deleted,
            crawl_count, timestamp::timestamp as timestamp, insertion_time,
            upvotes_history, downvotes_history, comments_history, update_history,
            toxicity_class, toxicity_confidence
        FROM reddit_1_posts_copy_2
        UNION ALL
        SELECT 
            id, title, post_id, content, subreddit, deleted::text as deleted,
            crawl_count, timestamp::timestamp as timestamp, insertion_time,
            upvotes_history, downvotes_history, comments_history, update_history,
            toxicity_class, toxicity_confidence
        FROM reddit_posts_copy
        UNION ALL
        SELECT 
            id, title, post_id, content, subreddit, deleted::text as deleted,
            crawl_count, timestamp::timestamp as timestamp, insertion_time,
            upvotes_history, downvotes_history, comments_history, update_history,
            toxicity_class, toxicity_confidence
        FROM reddit_2_posts
    ) combined_reddit
    GROUP BY subreddit
    ORDER BY subreddit;
    """

    upvotes_plot_url = None
    upvotes_message = None
    correlation_plot_url = None
    correlation_message = None
    toxicity_dist_plot_url = None
    toxicity_dist_message = None

    daily_comments_plot_url = None
    daily_comments_message = None

    subreddit_posts_plot_url = None
    subreddit_posts_message = None

    comment_heatmap_plot_url = None
    comment_heatmap_message = None

    if request.method == 'POST':
        if 'submit_upvotes' in request.form:
            start_date = request.form.get('upvotes_start_date')
            end_date = request.form.get('upvotes_end_date')
            date_filter = ""
            params = []
            if start_date:
                date_filter += " AND timestamp >= %s"
                params.append(start_date)
            if end_date:
                date_filter += " AND timestamp <= %s"
                params.append(end_date)
            query = upvotes_query_template.format(date_filter=date_filter)
            results = query_db(DB_URL, query, tuple(params))
            if len(results) == 0:
                upvotes_message = "No data found for the selected date range."
            else:
                df = pd.DataFrame(results)
                plt.figure(figsize=(8,4))
                sns.lineplot(x='day', y='avg_upvotes', data=df, marker='o')
                plt.title("Average Upvotes Over Time")
                plt.xlabel("Date")
                plt.ylabel("Average Upvotes")
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                upvotes_plot_url = f"/static/{filename}"
                upvotes_message = f"Found {len(df)} data points."

        elif 'submit_correlation' in request.form:
            lower = request.form.get('tox_conf_lower')
            upper = request.form.get('tox_conf_upper')
            corr_query = correlation_query
            params = []
            if lower and upper:
                corr_query += " AND toxicity_confidence BETWEEN %s AND %s"
                params.extend([float(lower), float(upper)])
            results = query_db(DB_URL_C, corr_query, tuple(params))
            if len(results) == 0:
                correlation_message = "No data found for the selected toxicity confidence range."
            else:
                df = pd.DataFrame(results)
                plt.figure(figsize=(6,4))
                sns.scatterplot(x='toxicity_confidence', y='upvotes', data=df)
                plt.title("Toxicity Confidence vs Upvotes")
                plt.xlabel("Toxicity Confidence")
                plt.ylabel("Upvotes")
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                correlation_plot_url = f"/static/{filename}"
                correlation_message = f"Found {len(df)} points."

        elif 'submit_toxicity_distribution' in request.form:
            selected_subs = request.form.getlist('selected_subreddits')
            results = query_db(DB_URL, toxicity_dist_query)
            df = pd.DataFrame(results)
            if selected_subs:
                df = df[df['subreddit'].isin(selected_subs)]
            if df.empty:
                toxicity_dist_message = "No data found for the selected subreddit(s)."
            else:
                df_melt = df.melt(id_vars='subreddit', value_vars=['normal_posts', 'flagged_posts'],
                                  var_name='post_type', value_name='count')
                plt.figure(figsize=(8,4))
                sns.barplot(x='subreddit', y='count', hue='post_type', data=df_melt)
                plt.title("Toxicity Distribution by Subreddit")
                plt.xlabel("Subreddit")
                plt.ylabel("Count")
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                toxicity_dist_plot_url = f"/static/{filename}"
                toxicity_dist_message = f"Found data for {len(df)} subreddits."

                toxicity_types = request.form.getlist('toxicity_types')
                if toxicity_types:
                    allowed_types = []
                    if 'normal' in toxicity_types:
                        allowed_types.append('normal_posts')
                    if 'flagged' in toxicity_types:
                        allowed_types.append('flagged_posts')

                    df_melt_filtered = df_melt[df_melt['post_type'].isin(allowed_types)]
                    if df_melt_filtered.empty:
                        toxicity_dist_message = "No data found after filtering for the selected post types."
                        toxicity_dist_plot_url = None
                    else:
                        plt.figure(figsize=(8,4))
                        unique_post_types = df_melt_filtered['post_type'].unique()
                        if len(unique_post_types) == 1:
                            sns.barplot(x='subreddit', y='count', data=df_melt_filtered, color='steelblue')
                            plt.title(f"Toxicity Distribution ({unique_post_types[0]}) by Subreddit")
                        else:
                            sns.barplot(x='subreddit', y='count', hue='post_type', data=df_melt_filtered)
                            plt.title("Toxicity Distribution (Normal & Flagged) by Subreddit")
                        plt.xlabel("Subreddit")
                        plt.ylabel("Count")
                        plt.xticks(rotation=45, ha='right')
                        plt.tight_layout()
                        filename = f"plot_{uuid.uuid4()}.png"
                        filepath = os.path.join('static', filename)
                        plt.savefig(filepath)
                        plt.close()
                        toxicity_dist_plot_url = f"/static/{filename}"
                        toxicity_dist_message = f"Found data for {len(df)} subreddits with chosen types."

        elif 'submit_post_activity_heatmap' in request.form:
            reddit_activity_posts_query = """
                SELECT 
                    timestamp
                FROM (
                    SELECT 
                        id, title, post_id, content, subreddit, deleted::text AS deleted,
                        crawl_count, timestamp::timestamp AS timestamp, insertion_time,
                        upvotes_history, downvotes_history, comments_history, update_history,
                        toxicity_class, toxicity_confidence
                    FROM reddit_1_posts_copy_2
                    UNION ALL
                    SELECT 
                        id, title, post_id, content, subreddit, deleted::text AS deleted,
                        crawl_count, timestamp::timestamp as timestamp, insertion_time,
                        upvotes_history, downvotes_history, comments_history, update_history,
                        toxicity_class, toxicity_confidence
                    FROM reddit_posts_copy
                    UNION ALL
                    SELECT 
                        id, title, post_id, content, subreddit, deleted::text as deleted,
                        crawl_count, timestamp::timestamp as timestamp, insertion_time,
                        upvotes_history, downvotes_history, comments_history, update_history,
                        toxicity_class, toxicity_confidence
                    FROM reddit_2_posts
                ) combined_reddit
                WHERE timestamp >= '2024-10-01';
            """

            post_results = query_db(DB_URL, reddit_activity_posts_query)
            if len(post_results) == 0:
                post_activity_message = "No posts found."
            else:
                df_posts = pd.DataFrame(post_results)
                df_posts['day_of_week'] = df_posts['timestamp'].dt.dayofweek
                df_posts['hour_of_day'] = df_posts['timestamp'].dt.hour

                pivot = df_posts.groupby(['day_of_week', 'hour_of_day']).size().reset_index(name='post_count')
                pivot_table = pivot.pivot(index='day_of_week', columns='hour_of_day', values='post_count').fillna(0)

                plt.figure(figsize=(10,6))
                sns.heatmap(pivot_table, cmap='Blues', annot=False, fmt='g')
                plt.title("Reddit Post Activity Heatmap\n(Day of Week vs Hour of Day)")
                plt.xlabel("Hour of Day")
                plt.ylabel("Day of Week (0=Mon,6=Sun)")
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()

                post_activity_plot_url = f"/static/{filename}"
                post_activity_message = f"Data shows {len(df_posts)} posts."

            return render_template('reddit_analysis.html',
                                   reddit_dataset_summary=reddit_dataset_summary,
                                   subreddit_list=subreddit_list,
                                   upvotes_plot_url=upvotes_plot_url,
                                   upvotes_message=upvotes_message,
                                   correlation_plot_url=correlation_plot_url,
                                   correlation_message=correlation_message,
                                   toxicity_dist_plot_url=toxicity_dist_plot_url,
                                   toxicity_dist_message=toxicity_dist_message,
                                   post_activity_plot_url=locals().get('post_activity_plot_url'),
                                   post_activity_message=locals().get('post_activity_message'),
                                   daily_comments_plot_url=daily_comments_plot_url,
                                   daily_comments_message=daily_comments_message,
                                   subreddit_posts_plot_url=subreddit_posts_plot_url,
                                   subreddit_posts_message=subreddit_posts_message,
                                   comment_heatmap_plot_url=comment_heatmap_plot_url,
                                   comment_heatmap_message=comment_heatmap_message)

        elif 'submit_daily_comments' in request.form:
            comments_start_date = request.form.get('comments_start_date')
            comments_end_date = request.form.get('comments_end_date')
            selected_comments_subreddits = request.form.getlist('comments_subreddits')

            daily_comments_query = """
            SELECT 
                subreddit,
                time_bucket('1 day', timestamp) AS day,
                SUM((comments_history->-1->>'value')::int) AS total_comments
            FROM (
                SELECT
                    id, title, post_id, content, subreddit, deleted::text as deleted,
                    crawl_count, timestamp::timestamp as timestamp,
                    insertion_time, upvotes_history, downvotes_history,
                    comments_history, update_history,
                    toxicity_class, toxicity_confidence
                FROM reddit_1_posts_copy_2
                UNION ALL
                SELECT
                    id, title, post_id, content, subreddit, deleted::text as deleted,
                    crawl_count, timestamp::timestamp as timestamp,
                    insertion_time, upvotes_history, downvotes_history,
                    comments_history, update_history,
                    toxicity_class, toxicity_confidence
                FROM reddit_posts_copy
                UNION ALL
                SELECT
                    id, title, post_id, content, subreddit, deleted::text as deleted,
                    crawl_count, timestamp::timestamp as timestamp,
                    insertion_time, upvotes_history, downvotes_history,
                    comments_history, update_history,
                    toxicity_class, toxicity_confidence
                FROM reddit_2_posts
            ) combined_reddit
            WHERE 1=1
            """

            params = []
            if comments_start_date:
                daily_comments_query += " AND timestamp >= %s"
                params.append(comments_start_date)
            if comments_end_date:
                daily_comments_query += " AND timestamp <= %s"
                params.append(comments_end_date)

            daily_comments_query += " GROUP BY subreddit, day ORDER BY day;"

            results = query_db(DB_URL, daily_comments_query, tuple(params))
            if len(results) == 0:
                daily_comments_message = "No comments data found for the selected criteria."
            else:
                df = pd.DataFrame(results)
                if selected_comments_subreddits:
                    df = df[df['subreddit'].isin(selected_comments_subreddits)]

                if df.empty:
                    daily_comments_message = "No data found for the selected subreddits and date range."
                else:
                    plt.figure(figsize=(10,6))
                    for sb in df['subreddit'].unique():
                        sb_data = df[df['subreddit'] == sb]
                        plt.plot(sb_data['day'], sb_data['total_comments'], marker='o', label=sb)
                    plt.title("Daily Number of Comments by Subreddit")
                    plt.xlabel("Date")
                    plt.ylabel("Total Comments")
                    plt.legend()
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    filename = f"plot_{uuid.uuid4()}.png"
                    filepath = os.path.join('static', filename)
                    plt.savefig(filepath)
                    plt.close()
                    daily_comments_plot_url = f"/static/{filename}"
                    daily_comments_message = f"Found {len(df)} data points."

        elif 'submit_subreddit_posts' in request.form:
            posts_start_date = request.form.get('posts_start_date')
            posts_end_date = request.form.get('posts_end_date')
            selected_posts_subreddits = request.form.getlist('posts_subreddits')

            subreddit_posts_query = """
            SELECT
                subreddit,
                timestamp::date AS post_date
            FROM reddit_1_posts_copy_2
            WHERE subreddit IS NOT NULL
            UNION ALL
            SELECT
                subreddit,
                timestamp::date AS post_date
            FROM reddit_posts_copy
            WHERE subreddit IS NOT NULL
            UNION ALL
            SELECT
                subreddit,
                timestamp::date AS post_date
            FROM reddit_2_posts
            WHERE subreddit IS NOT NULL;
            """

            results = query_db(DB_URL, subreddit_posts_query)
            df = pd.DataFrame(results)

            df['post_date'] = pd.to_datetime(df['post_date'])
            if posts_start_date:
                start_dt = pd.to_datetime(posts_start_date)
                df = df[df['post_date'] >= start_dt]
            if posts_end_date:
                end_dt = pd.to_datetime(posts_end_date)
                df = df[df['post_date'] <= end_dt]

            if selected_posts_subreddits:
                df = df[df['subreddit'].isin(selected_posts_subreddits)]

            if df.empty:
                subreddit_posts_message = "No posts found for the selected criteria."
            else:
                count_df = df.groupby(['subreddit', 'post_date']).size().reset_index(name='post_count')
                plt.figure(figsize=(10,6))
                for sb in count_df['subreddit'].unique():
                    sb_data = count_df[count_df['subreddit'] == sb]
                    plt.plot(sb_data['post_date'], sb_data['post_count'], marker='o', label=sb)
                plt.title("Number of Posts in Each Subreddit Over Time")
                plt.xlabel("Date")
                plt.ylabel("Number of Posts")
                plt.legend()
                plt.xticks(rotation=45)
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                subreddit_posts_plot_url = f"/static/{filename}"
                subreddit_posts_message = f"Found {len(count_df)} data points."

        elif 'submit_comment_heatmap' in request.form:
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

            results = query_db(DB_URL_C, reddit_heatmap_query)
            if len(results) == 0:
                comment_heatmap_message = "No comments found for the specified criteria."
            else:
                df = pd.DataFrame(results)
                pivot_table = df.pivot(index='day_of_week', columns='hour_of_day', values='comment_count').fillna(0)

                plt.figure(figsize=(10,6))
                sns.heatmap(pivot_table, cmap='Reds', annot=False, fmt='g')
                plt.title("Reddit Comment Activity Heatmap\n(Day of Week vs Hour of Day)")
                plt.xlabel("Hour of Day")
                plt.ylabel("Day of Week (0=Mon,6=Sun)")
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                comment_heatmap_plot_url = f"/static/{filename}"
                comment_heatmap_message = f"Data shows {int(df['comment_count'].sum())} comments in total."

    return render_template('reddit_analysis.html',
                           reddit_dataset_summary=reddit_dataset_summary,
                           subreddit_list=subreddit_list,
                           upvotes_plot_url=upvotes_plot_url,
                           upvotes_message=upvotes_message,
                           correlation_plot_url=correlation_plot_url,
                           correlation_message=correlation_message,
                           toxicity_dist_plot_url=toxicity_dist_plot_url,
                           toxicity_dist_message=toxicity_dist_message,
                           daily_comments_plot_url=daily_comments_plot_url,
                           daily_comments_message=daily_comments_message,
                           subreddit_posts_plot_url=subreddit_posts_plot_url,
                           subreddit_posts_message=subreddit_posts_message,
                           comment_heatmap_plot_url=comment_heatmap_plot_url,
                           comment_heatmap_message=comment_heatmap_message)



#4chan
@app.route('/chan_analysis', methods=['GET', 'POST'])
def chan_analysis():
    queries = {
        "chan_posts": """
            SELECT 'chan_posts' AS table_name, COUNT(*) AS count FROM (
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
        "chan_comments": """
            SELECT 'chan_comments' AS table_name, COUNT(*) AS count FROM (
                SELECT * FROM chan_comments
                UNION ALL
                SELECT * FROM chan_2_comments
            ) combined_chan_comments;
        """
    }

    chan_dataset_summary = []
    chan_dataset_summary += query_db(DB_URL, queries["chan_posts"])
    chan_dataset_summary += query_db(DB_URL_C, queries["chan_comments"])

    board_query = """
    SELECT DISTINCT board FROM (
        SELECT board FROM chan_1_posts_copy_2
        UNION ALL
        SELECT board FROM chan_posts_copy
        UNION ALL
        SELECT board FROM chan_2_posts
    ) t
    WHERE board IS NOT NULL
    ORDER BY board;
    """
    boards_result = query_db(DB_URL, board_query)
    board_list = [r['board'] for r in boards_result]

    chan_toxicity_query = """
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

    chan_activity_query = """
    SELECT 
        COALESCE(time, insertion_time) AS timestamp
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

    chan_daily_comments_template = """
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
    WHERE 1=1
    {time_filter}
    GROUP BY board, day
    ORDER BY day;
    """

    chan_comment_heatmap_query = """
    SELECT 
        EXTRACT(DOW FROM timestamp) AS day_of_week,
        EXTRACT(HOUR FROM timestamp) AS hour_of_day,
        COUNT(*) AS comment_count
    FROM (
        SELECT * FROM chan_comments
        UNION ALL
        SELECT * FROM chan_2_comments
    ) combined_chan
    WHERE timestamp >= '2024-10-01'
    GROUP BY day_of_week, hour_of_day
    ORDER BY day_of_week, hour_of_day;
    """

    chan_posts_query = """
    SELECT
        board,
        time::date AS post_date
    FROM chan_1_posts_copy_2
    WHERE board IS NOT NULL AND time >= '2024-10-01'
    UNION ALL
    SELECT
        board,
        time::date AS post_date
    FROM chan_posts_copy
    WHERE board IS NOT NULL AND time >= '2024-10-01'
    UNION ALL
    SELECT
        board,
        time::date AS post_date
    FROM chan_2_posts
    WHERE board IS NOT NULL AND time >= '2024-10-01';
    """

    chan_toxicity_plot_url = None
    chan_toxicity_message = None

    chan_activity_plot_url = None
    chan_activity_message = None

    chan_daily_comments_plot_url = None
    chan_daily_comments_message = None

    chan_comment_heatmap_plot_url = None
    chan_comment_heatmap_message = None

    chan_posts_plot_url = None
    chan_posts_message = None

    if request.method == 'POST':
        if 'submit_chan_toxicity' in request.form:
            selected_boards = request.form.getlist('chan_boards_toxicity')
            toxicity_types = request.form.getlist('chan_toxicity_types')

            results = query_db(DB_URL, chan_toxicity_query)
            df = pd.DataFrame(results)
            if selected_boards:
                df = df[df['board'].isin(selected_boards)]
            if df.empty:
                chan_toxicity_message = "No data found for the selected board(s)."
            else:
                df_melt = df.melt(id_vars='board', value_vars=['normal_posts', 'flagged_posts'],
                                  var_name='post_type', value_name='count')
                
                if toxicity_types:
                    allowed_types = []
                    if 'normal' in toxicity_types:
                        allowed_types.append('normal_posts')
                    if 'flagged' in toxicity_types:
                        allowed_types.append('flagged_posts')
                    df_melt = df_melt[df_melt['post_type'].isin(allowed_types)]
                
                if df_melt.empty:
                    chan_toxicity_message = "No data found after filtering by post types."
                else:
                    plt.figure(figsize=(8,4))
                    unique_types = df_melt['post_type'].unique()
                    if len(unique_types) == 1:
                        sns.barplot(x='board', y='count', data=df_melt, color='steelblue')
                        plt.title(f"Toxicity Distribution ({unique_types[0]}) by Board")
                    else:
                        sns.barplot(x='board', y='count', hue='post_type', data=df_melt)
                        plt.title("Toxicity Distribution (Normal & Flagged) by Board")

                    plt.xlabel("Board")
                    plt.ylabel("Count")
                    plt.xticks(rotation=45, ha='right')
                    plt.tight_layout()
                    filename = f"plot_{uuid.uuid4()}.png"
                    filepath = os.path.join('static', filename)
                    plt.savefig(filepath)
                    plt.close()
                    chan_toxicity_plot_url = f"/static/{filename}"
                    chan_toxicity_message = f"Found data for {len(df)} boards."

        elif 'submit_chan_activity_heatmap' in request.form:
            results = query_db(DB_URL, chan_activity_query)
            if len(results) == 0:
                chan_activity_message = "No posts found."
            else:
                df = pd.DataFrame(results)
                df['day_of_week'] = df['timestamp'].dt.dayofweek
                df['hour_of_day'] = df['timestamp'].dt.hour

                pivot = df.groupby(['day_of_week', 'hour_of_day']).size().reset_index(name='post_count')
                pivot_table = pivot.pivot(index='day_of_week', columns='hour_of_day', values='post_count').fillna(0)

                plt.figure(figsize=(10,6))
                sns.heatmap(pivot_table, cmap='Blues', annot=False, fmt='g')
                plt.title("4chan Post Activity Heatmap\n(Day of Week vs Hour of Day)")
                plt.xlabel("Hour of Day")
                plt.ylabel("Day of Week (0=Mon,6=Sun)")
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()

                chan_activity_plot_url = f"/static/{filename}"
                chan_activity_message = f"Data shows {len(df)} posts."

        elif 'submit_chan_daily_comments' in request.form:
            start_date = request.form.get('chan_comments_start_date')
            end_date = request.form.get('chan_comments_end_date')
            selected_comment_boards = request.form.getlist('chan_comments_boards')

            time_filter = ""
            params = []
            if start_date:
                time_filter += " AND time >= %s"
                params.append(start_date)
            if end_date:
                time_filter += " AND time <= %s"
                params.append(end_date)

            query = chan_daily_comments_template.format(time_filter=time_filter)
            results = query_db(DB_URL, query, tuple(params))
            if len(results) == 0:
                chan_daily_comments_message = "No comments data found for the selected criteria."
            else:
                df = pd.DataFrame(results)
                if selected_comment_boards:
                    df = df[df['board'].isin(selected_comment_boards)]
                
                if df.empty:
                    chan_daily_comments_message = "No data found for the selected boards and date range."
                else:
                    plt.figure(figsize=(10,6))
                    for brd in df['board'].unique():
                        brd_data = df[df['board'] == brd]
                        plt.plot(brd_data['day'], brd_data['total_replies'], marker='o', label=brd)
                    plt.title("Daily Number of Comments by Board")
                    plt.xlabel("Date")
                    plt.ylabel("Total Replies")
                    plt.legend()
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    filename = f"plot_{uuid.uuid4()}.png"
                    filepath = os.path.join('static', filename)
                    plt.savefig(filepath)
                    plt.close()
                    chan_daily_comments_plot_url = f"/static/{filename}"
                    chan_daily_comments_message = f"Found {len(df)} data points."

        elif 'submit_chan_comment_heatmap' in request.form:
            results = query_db(DB_URL_C, chan_comment_heatmap_query)
            if len(results) == 0:
                chan_comment_heatmap_message = "No comments found."
            else:
                df = pd.DataFrame(results)
                pivot_table = df.pivot(index='day_of_week', columns='hour_of_day', values='comment_count').fillna(0)
                plt.figure(figsize=(10,6))
                sns.heatmap(pivot_table, cmap='Reds', annot=False, fmt='g')
                plt.title("4chan Comment Activity Heatmap\n(Day of Week vs Hour of Day)")
                plt.xlabel("Hour of Day")
                plt.ylabel("Day of Week (0=Mon,6=Sun)")
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                chan_comment_heatmap_plot_url = f"/static/{filename}"
                chan_comment_heatmap_message = f"Data shows total of {int(df['comment_count'].sum())} comments."

        elif 'submit_chan_posts' in request.form:
            posts_start_date = request.form.get('chan_posts_start_date')
            posts_end_date = request.form.get('chan_posts_end_date')
            selected_chan_boards = request.form.getlist('chan_posts_boards')

            results = query_db(DB_URL, chan_posts_query)
            df = pd.DataFrame(results)
            df['post_date'] = pd.to_datetime(df['post_date'])

            if posts_start_date:
                start_dt = pd.to_datetime(posts_start_date)
                df = df[df['post_date'] >= start_dt]
            if posts_end_date:
                end_dt = pd.to_datetime(posts_end_date)
                df = df[df['post_date'] <= end_dt]

            if selected_chan_boards:
                df = df[df['board'].isin(selected_chan_boards)]

            if df.empty:
                chan_posts_message = "No posts found for the selected criteria."
            else:
                count_df = df.groupby(['board', 'post_date']).size().reset_index(name='post_count')
                plt.figure(figsize=(10,6))
                for brd in count_df['board'].unique():
                    brd_data = count_df[count_df['board'] == brd]
                    plt.plot(brd_data['post_date'], brd_data['post_count'], marker='o', label=brd)
                plt.title("Number of Posts in Each 4chan Board Over Time")
                plt.xlabel("Date")
                plt.ylabel("Number of Posts")
                plt.legend()
                plt.xticks(rotation=45)
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                chan_posts_plot_url = f"/static/{filename}"
                chan_posts_message = f"Found {len(count_df)} data points."

    return render_template('chan_analysis.html',
                           chan_dataset_summary=chan_dataset_summary,
                           board_list=board_list,
                           chan_toxicity_plot_url=chan_toxicity_plot_url,
                           chan_toxicity_message=chan_toxicity_message,
                           chan_activity_plot_url=chan_activity_plot_url,
                           chan_activity_message=chan_activity_message,
                           chan_daily_comments_plot_url=chan_daily_comments_plot_url,
                           chan_daily_comments_message=chan_daily_comments_message,
                           chan_comment_heatmap_plot_url=chan_comment_heatmap_plot_url,
                           chan_comment_heatmap_message=chan_comment_heatmap_message,
                           chan_posts_plot_url=chan_posts_plot_url,
                           chan_posts_message=chan_posts_message)

#toxicity
@app.route('/toxicity_analysis', methods=['GET', 'POST'])
def toxicity_analysis():
    tox_class = request.form.get('tox_class') if request.method == 'POST' else None

    plot_url = None
    message = None

    query = "SELECT toxicity_class FROM toxicity_cache"
    params = []
    if tox_class and tox_class.strip():
        query += " WHERE toxicity_class = %s"
        params.append(tox_class.strip())

    results = query_db(DB_URL_T, query, tuple(params))

    if len(results) == 0:
        message = "No data found for the selected parameters."
    else:
        df = pd.DataFrame(results)
        class_counts = df['toxicity_class'].value_counts(dropna=False).reset_index()
        class_counts.columns = ['toxicity_class', 'count']

        plt.figure(figsize=(8,4))
        sns.barplot(x='toxicity_class', y='count', data=class_counts, color='green')
        plt.title("Toxicity Class Distribution")
        plt.xlabel("Toxicity Class")
        plt.ylabel("Count")
        plt.xticks(rotation=45)
        plt.tight_layout()

        filename = f"plot_{uuid.uuid4()}.png"
        filepath = os.path.join('static', filename)
        plt.savefig(filepath)
        plt.close()
        plot_url = f"/static/{filename}"
        message = f"Found {len(results)} entries."

    return render_template('toxicity_analysis.html',
                           tox_class=tox_class,
                           plot_url=plot_url,
                           message=message)

#additional analysis
@app.route('/additional_analysis', methods=['GET', 'POST'])
def additional_analysis():
    reddit_submissions_query = """
        SELECT 
            time_bucket('1 day', timestamp) AS day,
            COUNT(post_id) AS submissions
        FROM reddit_1_posts
        WHERE subreddit = 'politics'
        AND timestamp BETWEEN '2024-11-01 00:00:00' AND '2024-11-14 23:59:59'
        GROUP BY day
        ORDER BY day;
    """

    reddit_comments_hourly_query = """
        SELECT 
            time_bucket('1 hour', timestamp) AS hour,
            SUM((comments_history->-1->>'value')::int) AS total_comments
        FROM reddit_1_posts
        WHERE subreddit = 'politics'
        AND timestamp BETWEEN '2024-11-01 00:00:00' AND '2024-11-14 23:59:59'
        GROUP BY hour
        ORDER BY hour;
    """

    chan_pol_comments_hourly_query = """
        SELECT 
            time_bucket('1 hour', time) AS hour_bucket,
            SUM((replies_history->-1->>'value')::int) AS total_comments
        FROM 
            chan_1_posts
        WHERE 
            board = 'pol'
            AND time >= '2024-11-01 00:00:00' 
            AND time < '2024-11-15 00:00:00'
        GROUP BY 
            hour_bucket
        ORDER BY 
            hour_bucket;
    """

    reddit_submissions_plot_url = None
    reddit_submissions_message = None

    reddit_comments_plot_url = None
    reddit_comments_message = None

    chan_pol_comments_plot_url = None
    chan_pol_comments_message = None

    rq1_plot_url = None
    rq1_message = None
    rq2_plot_url = None
    rq2_message = None
    rq3_plot_url = None
    rq3_message = None

    if request.method == 'POST':
        if 'submit_reddit_submissions' in request.form:
            results = query_db(DB_URL, reddit_submissions_query)
            if len(results) == 0:
                reddit_submissions_message = "No submissions found."
            else:
                df = pd.DataFrame(results)
                plt.figure(figsize=(10,5))
                sns.lineplot(x='day', y='submissions', data=df, marker='o')
                plt.title("Number of Submissions in r/politics (Nov 1-14, 2024)")
                plt.xlabel("Day")
                plt.ylabel("Submissions")
                plt.xticks(rotation=45)
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                reddit_submissions_plot_url = f"/static/{filename}"
                reddit_submissions_message = f"Found {len(df)} data points."

        elif 'submit_reddit_comments_hourly' in request.form:
            results = query_db(DB_URL, reddit_comments_hourly_query)
            if len(results) == 0:
                reddit_comments_message = "No comments found."
            else:
                df = pd.DataFrame(results)
                plt.figure(figsize=(10,5))
                sns.lineplot(x='hour', y='total_comments', data=df, marker='o')
                plt.title("Comments per hour in r/politics (Nov 1-14, 2024)")
                plt.xlabel("Hour")
                plt.ylabel("Total Comments")
                plt.xticks(rotation=45)
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                reddit_comments_plot_url = f"/static/{filename}"
                reddit_comments_message = f"Found {len(df)} data points."

        elif 'submit_chan_pol_comments' in request.form:
            results = query_db(DB_URL, chan_pol_comments_hourly_query)
            if len(results) == 0:
                chan_pol_comments_message = "No comments found."
            else:
                df = pd.DataFrame(results)
                plt.figure(figsize=(10,5))
                sns.lineplot(x='hour_bucket', y='total_comments', data=df, marker='o', color='red')
                plt.title("Comments per hour on 4chan /pol/ (Nov 1-14, 2024)")
                plt.xlabel("Hour")
                plt.ylabel("Total Comments")
                plt.xticks(rotation=45)
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                chan_pol_comments_plot_url = f"/static/{filename}"
                chan_pol_comments_message = f"Found {len(df)} data points."

        if 'submit_rq1' in request.form:
            platform = request.form.get('rq1_platform')
            selected_subreddits = request.form.getlist('rq1_subreddits')
            selected_boards = request.form.getlist('rq1_boards')
            start_date = request.form.get('rq1_start_date')
            end_date = request.form.get('rq1_end_date')


            reddit_all_subs = ["Sports", "NBA", "Soccer", "NFL", "Baseball", "CollegeBasketball", 
                               "MMA", "Formula1", "Running", "Hockey", "Snowboarding", "Skiing",
                               "Boxing", "olympics", "ipl", "Cricket", "formuladank", "politics"]


            chan_all_boards = ["sp", "xs", "pol"]

            if platform == 'reddit':
                if len(selected_boards) > 0:
                    rq1_message = "For Reddit, please select subreddits only, not boards."
                    rq1_plot_url = None
                    return render_template('additional_analysis.html',
                                           reddit_submissions_plot_url=reddit_submissions_plot_url,
                                           reddit_submissions_message=reddit_submissions_message,
                                           reddit_comments_plot_url=reddit_comments_plot_url,
                                           reddit_comments_message=reddit_comments_message,
                                           chan_pol_comments_plot_url=chan_pol_comments_plot_url,
                                           chan_pol_comments_message=chan_pol_comments_message,
                                           rq1_plot_url=rq1_plot_url,
                                           rq1_message=rq1_message,
                                           rq2_plot_url=rq2_plot_url,
                                           rq2_message=rq2_message,
                                           rq3_plot_url=rq3_plot_url,
                                           rq3_message=rq3_message)
                comm_list = selected_subreddits if selected_subreddits else reddit_all_subs
            else:
                if len(selected_subreddits) > 0:
                    rq1_message = "For 4chan, please select boards only, not subreddits."
                    rq1_plot_url = None
                    return render_template('additional_analysis.html',
                                           reddit_submissions_plot_url=reddit_submissions_plot_url,
                                           reddit_submissions_message=reddit_submissions_message,
                                           reddit_comments_plot_url=reddit_comments_plot_url,
                                           reddit_comments_message=reddit_comments_message,
                                           chan_pol_comments_plot_url=chan_pol_comments_plot_url,
                                           chan_pol_comments_message=chan_pol_comments_message,
                                           rq1_plot_url=rq1_plot_url,
                                           rq1_message=rq1_message,
                                           rq2_plot_url=rq2_plot_url,
                                           rq2_message=rq2_message,
                                           rq3_plot_url=rq3_plot_url,
                                           rq3_message=rq3_message)
                comm_list = selected_boards if selected_boards else chan_all_boards

            reddit_posts_union = """
            (
                SELECT id, title, post_id, content, subreddit, deleted::text as deleted,
                       crawl_count, timestamp::timestamp as timestamp, insertion_time,
                       upvotes_history, downvotes_history, comments_history, update_history,
                       toxicity_class, toxicity_confidence
                FROM reddit_posts_copy
                UNION ALL
                SELECT id, title, post_id, content, subreddit, deleted::text as deleted,
                       crawl_count, timestamp::timestamp as timestamp, insertion_time,
                       upvotes_history, downvotes_history, comments_history, update_history,
                       toxicity_class, toxicity_confidence
                FROM reddit_1_posts_copy_2
                UNION ALL
                SELECT id, title, post_id, content, subreddit, deleted::text as deleted,
                       crawl_count, timestamp::timestamp as timestamp, insertion_time,
                       upvotes_history, downvotes_history, comments_history, update_history,
                       toxicity_class, toxicity_confidence
                FROM reddit_2_posts
            ) combined_reddit_posts
            """

            chan_posts_union = """
            (
                SELECT id, board, thread_id, subject, description, time::timestamp as time,
                       deleted::text as deleted, replies_history, images_history,
                       update_history, insertion_time, crawl_count, toxicity_class,
                       toxicity_confidence
                FROM chan_posts_copy
                UNION ALL
                SELECT id, board, thread_id, subject, description, time::timestamp as time,
                       deleted::text as deleted, replies_history, images_history,
                       update_history, insertion_time, crawl_count, toxicity_class,
                       toxicity_confidence
                FROM chan_1_posts_copy_2
                UNION ALL
                SELECT id, board, thread_id, subject, description, time::timestamp as time,
                       deleted::text as deleted, replies_history, images_history,
                       update_history, insertion_time, crawl_count, toxicity_class,
                       toxicity_confidence
                FROM chan_2_posts
            ) combined_chan_posts
            """

            if platform == 'reddit':
                query = f"""
                SELECT 
                    date_trunc('day', timestamp) AS day,
                    COUNT(*) FILTER (WHERE toxicity_class='flag') AS flagged_posts,
                    COUNT(*) FILTER (WHERE toxicity_class='normal') AS normal_posts
                FROM {reddit_posts_union}
                WHERE subreddit = ANY(%s)
                  AND timestamp BETWEEN %s AND %s
                GROUP BY day
                ORDER BY day;
                """
                params = [comm_list, start_date, end_date]
                results = query_db(DB_URL, query, tuple(params))
            else:
                query = f"""
                SELECT 
                    date_trunc('day', time) AS day,
                    COUNT(*) FILTER (WHERE toxicity_class='flag') AS flagged_posts,
                    COUNT(*) FILTER (WHERE toxicity_class='normal') AS normal_posts
                FROM {chan_posts_union}
                WHERE board = ANY(%s)
                  AND time BETWEEN %s AND %s
                GROUP BY day
                ORDER BY day;
                """
                params = [comm_list, start_date, end_date]
                results = query_db(DB_URL, query, tuple(params))

            if len(results) == 0:
                rq1_message = "No data found for RQ1 criteria."
                rq1_plot_url = None
            else:
                df = pd.DataFrame(results)
                plt.figure(figsize=(10,5))
                plt.plot(df['day'], df['flagged_posts'], label='Flagged Posts', marker='o', color='red')
                plt.plot(df['day'], df['normal_posts'], label='Normal Posts', marker='o', color='blue')
                plt.title("Event Toxicity Over Time (RQ1 - Posts Only)")
                plt.xlabel("Day")
                plt.ylabel("Count")
                plt.xticks(rotation=45)
                plt.legend()
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                rq1_plot_url = f"/static/{filename}"
                rq1_message = (f"Found {len(df)} data points for RQ1 (Posts Only). "
                               f"Platform: {platform}, Communities: {', '.join(comm_list)}, "
                               f"Start: {start_date}, End: {end_date}, "
                               f"Toxicity: Both (Flagged and Normal)")

        if 'submit_rq2' in request.form:
            platform = request.form.get('rq2_platform') 
            data_type = request.form.get('rq2_data_type') 
            min_conf_str = request.form.get('rq2_min_conf', '')
            max_conf_str = request.form.get('rq2_max_conf', '')

            min_conf = float(min_conf_str) if min_conf_str else 0.0
            max_conf = float(max_conf_str) if max_conf_str else 1.0

            selected_days = request.form.getlist('rq2_days') 
            if len(selected_days) == 0:
                days_int = list(range(7))
            else:
                days_int = [int(d) for d in selected_days]

            days_placeholder = ','.join(['%s']*len(days_int))


            reddit_posts_union = """
            (
                SELECT id, title, post_id, content, subreddit, deleted,
                       crawl_count, timestamp, insertion_time,
                       upvotes_history, downvotes_history, comments_history, update_history,
                       toxicity_class, toxicity_confidence
                FROM reddit_posts_copy
                UNION ALL
                SELECT id, title, post_id, content, subreddit, deleted,
                       crawl_count, timestamp, insertion_time,
                       upvotes_history, downvotes_history, comments_history, update_history,
                       toxicity_class, toxicity_confidence
                FROM reddit_1_posts_copy_2
                UNION ALL
                SELECT id, title, post_id, content, subreddit, deleted,
                       crawl_count, timestamp, insertion_time,
                       upvotes_history, downvotes_history, comments_history, update_history,
                       toxicity_class, toxicity_confidence
                FROM reddit_2_posts
            ) combined_reddit_posts
            """

            reddit_comments_union = """
            (
                SELECT * FROM reddit_comments
                UNION ALL
                SELECT * FROM reddit_2_comments
            ) combined_reddit_comments
            """

            chan_posts_union = """
            (
                SELECT id, board, thread_id, subject, description, time, deleted,
                       replies_history, images_history, update_history,
                       insertion_time, crawl_count, toxicity_class, toxicity_confidence
                FROM chan_posts_copy
                UNION ALL
                SELECT id, board, thread_id, subject, description, time, deleted,
                       replies_history, images_history, update_history,
                       insertion_time, crawl_count, toxicity_class, toxicity_confidence
                FROM chan_1_posts_copy_2
                UNION ALL
                SELECT id, board, thread_id, subject, description, time, deleted,
                       replies_history, images_history, update_history,
                       insertion_time, crawl_count, toxicity_class, toxicity_confidence
                FROM chan_2_posts
            ) combined_chan_posts
            """

            chan_comments_union = """
            (
                SELECT * FROM chan_comments
                UNION ALL
                SELECT * FROM chan_2_comments
            ) combined_chan_comments
            """

            if platform == 'reddit':
                if data_type == 'posts':
                    query = f"""
                    SELECT 
                        EXTRACT(DOW FROM timestamp) AS day_of_week,
                        EXTRACT(HOUR FROM timestamp) AS hour_of_day,
                        AVG(toxicity_confidence) AS avg_toxicity_conf
                    FROM {reddit_posts_union}
                    WHERE toxicity_confidence BETWEEN %s AND %s
                      AND EXTRACT(DOW FROM timestamp) IN ({days_placeholder})
                    GROUP BY day_of_week, hour_of_day
                    ORDER BY day_of_week, hour_of_day;
                    """
                    params = [min_conf, max_conf] + days_int
                    results = query_db(DB_URL, query, tuple(params))
                else:
                    query = f"""
                    SELECT
                        EXTRACT(DOW FROM timestamp) AS day_of_week,
                        EXTRACT(HOUR FROM timestamp) AS hour_of_day,
                        AVG(toxicity_confidence) AS avg_toxicity_conf
                    FROM {reddit_comments_union}
                    WHERE toxicity_confidence BETWEEN %s AND %s
                      AND EXTRACT(DOW FROM timestamp) IN ({days_placeholder})
                    GROUP BY day_of_week, hour_of_day
                    ORDER BY day_of_week, hour_of_day;
                    """
                    params = [min_conf, max_conf] + days_int
                    results = query_db(DB_URL_C, query, tuple(params))
            else:
                if data_type == 'posts':
                    query = f"""
                    SELECT 
                        EXTRACT(DOW FROM time) AS day_of_week,
                        EXTRACT(HOUR FROM time) AS hour_of_day,
                        AVG(toxicity_confidence) AS avg_toxicity_conf
                    FROM {chan_posts_union}
                    WHERE toxicity_confidence BETWEEN %s AND %s
                      AND EXTRACT(DOW FROM time) IN ({days_placeholder})
                    GROUP BY day_of_week, hour_of_day
                    ORDER BY day_of_week, hour_of_day;
                    """
                    params = [min_conf, max_conf] + days_int
                    results = query_db(DB_URL, query, tuple(params))
                else:
                    query = f"""
                    SELECT
                        EXTRACT(DOW FROM timestamp) AS day_of_week,
                        EXTRACT(HOUR FROM timestamp) AS hour_of_day,
                        AVG(toxicity_confidence) AS avg_toxicity_conf
                    FROM {chan_comments_union}
                    WHERE toxicity_confidence BETWEEN %s AND %s
                      AND EXTRACT(DOW FROM timestamp) IN ({days_placeholder})
                    GROUP BY day_of_week, hour_of_day
                    ORDER BY day_of_week, hour_of_day;
                    """
                    params = [min_conf, max_conf] + days_int
                    results = query_db(DB_URL_C, query, tuple(params))

            if len(results) == 0:
                rq2_message = "No data found for RQ2."
                rq2_plot_url = None
            else:
                df = pd.DataFrame(results)
                pivot_table = df.pivot(index='day_of_week', columns='hour_of_day', values='avg_toxicity_conf').fillna(0)
                plt.figure(figsize=(10,6))
                sns.heatmap(pivot_table, cmap='coolwarm', annot=False, fmt='g')
                plt.title("Toxicity Timing Heatmap (RQ2)")
                plt.xlabel("Hour of Day")
                plt.ylabel("Day of Week (0=Mon,6=Sun)")
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                rq2_plot_url = f"/static/{filename}"

                chosen_days = days_int if len(selected_days)>0 else list(range(7))
                rq2_message = (f"Found {len(df)} data points for RQ2. "
                               f"Platform: {platform}, Data Type: {data_type}, "
                               f"Min Toxicity Conf: {min_conf}, Max Toxicity Conf: {max_conf}, "
                               f"Days of Week: {chosen_days if len(selected_days)>0 else 'All'}")

        if 'submit_rq3' in request.form:
            platform = request.form.get('rq3_platform')  
            keyword = request.form.get('rq3_keyword')
            rq3_data_mode = request.form.get('rq3_data_mode')
            toxicity_selection = request.form.getlist('rq3_toxicity_type') 

            tox_condition = ""
            if len(toxicity_selection) == 1:
                if toxicity_selection[0] == 'flag':
                    tox_condition = "AND toxicity_class = 'flag'"
                else:
                    tox_condition = "AND toxicity_class = 'normal'"

            chosen_tox = "Both"
            if len(toxicity_selection) == 1:
                chosen_tox = "Flagged" if toxicity_selection[0]=='flag' else "Normal"
            elif len(toxicity_selection) == 2:
                chosen_tox = "Flagged and Normal"
            if len(toxicity_selection)==0:
                chosen_tox = "Both"

            kw_param = f"%{keyword}%"

            reddit_posts_union = """
            (
                SELECT id, title, post_id, content, subreddit, deleted,
                       crawl_count, timestamp, insertion_time,
                       upvotes_history, downvotes_history, comments_history, update_history,
                       toxicity_class, toxicity_confidence
                FROM reddit_posts_copy
                UNION ALL
                SELECT id, title, post_id, content, subreddit, deleted,
                       crawl_count, timestamp, insertion_time,
                       upvotes_history, downvotes_history, comments_history, update_history,
                       toxicity_class, toxicity_confidence
                FROM reddit_1_posts_copy_2
                UNION ALL
                SELECT id, title, post_id, content, subreddit, deleted,
                       crawl_count, timestamp, insertion_time,
                       upvotes_history, downvotes_history, comments_history, update_history,
                       toxicity_class, toxicity_confidence
                FROM reddit_2_posts
            ) combined_reddit_posts
            """

            reddit_comments_union = """
            (
                SELECT * FROM reddit_comments
                UNION ALL
                SELECT * FROM reddit_2_comments
            ) combined_reddit_comments
            """

            chan_posts_union = """
            (
                SELECT id, board, thread_id, subject, description, time, deleted,
                       replies_history, images_history, update_history,
                       insertion_time, crawl_count, toxicity_class, toxicity_confidence
                FROM chan_posts_copy
                UNION ALL
                SELECT id, board, thread_id, subject, description, time, deleted,
                       replies_history, images_history, update_history,
                       insertion_time, crawl_count, toxicity_class, toxicity_confidence
                FROM chan_1_posts_copy_2
                UNION ALL
                SELECT id, board, thread_id, subject, description, time, deleted,
                       replies_history, images_history, update_history,
                       insertion_time, crawl_count, toxicity_class, toxicity_confidence
                FROM chan_2_posts
            ) combined_chan_posts
            """

            chan_comments_union = """
            (
                SELECT * FROM chan_comments
                UNION ALL
                SELECT * FROM chan_2_comments
            ) combined_chan_comments
            """

            if platform == 'reddit':
                if rq3_data_mode == 'posts':
                    query = f"""
                    SELECT toxicity_class, COUNT(*) AS post_count
                    FROM {reddit_posts_union}
                    WHERE (title ILIKE %s OR content ILIKE %s)
                      {tox_condition}
                    GROUP BY toxicity_class;
                    """
                    params = (kw_param, kw_param)
                    results = query_db(DB_URL, query, params)
                else:
                    query = f"""
                    SELECT toxicity_class, COUNT(*) AS post_count
                    FROM {reddit_comments_union}
                    WHERE body ILIKE %s
                      {tox_condition}
                    GROUP BY toxicity_class;
                    """
                    params = (kw_param,)
                    results = query_db(DB_URL_C, query, params)
            else:
                if rq3_data_mode == 'posts':
                    query = f"""
                    SELECT toxicity_class, COUNT(*) AS post_count
                    FROM {chan_posts_union}
                    WHERE (subject ILIKE %s OR description ILIKE %s)
                      {tox_condition}
                    GROUP BY toxicity_class;
                    """
                    params = (kw_param, kw_param)
                    results = query_db(DB_URL, query, params)
                else:
                    query = f"""
                    SELECT toxicity_class, COUNT(*) AS post_count
                    FROM {chan_comments_union}
                    WHERE body ILIKE %s
                      {tox_condition}
                    GROUP BY toxicity_class;
                    """
                    params = (kw_param,)
                    results = query_db(DB_URL_C, query, params)

            if len(results) == 0:
                rq3_message = "No data found for that keyword."
                rq3_plot_url = None
            else:
                df = pd.DataFrame(results)
                plt.figure(figsize=(6,4))
                sns.barplot(x='toxicity_class', y='post_count', data=df, color='green')
                plt.title(f"Toxicity Distribution for keyword: {keyword}")
                plt.xlabel("Toxicity Class")
                plt.ylabel("Count")
                plt.xticks(rotation=45)
                plt.tight_layout()
                filename = f"plot_{uuid.uuid4()}.png"
                filepath = os.path.join('static', filename)
                plt.savefig(filepath)
                plt.close()
                rq3_plot_url = f"/static/{filename}"
                rq3_message = (f"Found {len(df)} rows for RQ3. "
                               f"Platform: {platform}, Keyword: {keyword}, "
                               f"Data Mode: {rq3_data_mode}, Toxicity: {chosen_tox}")
        
        if 'submit_authors' in request.form:
            platform = request.form.get('authors_platform')
            start_date = request.form.get('authors_start_date')
            end_date = request.form.get('authors_end_date')
            top_n_str = request.form.get('authors_top_n', '5')
            top_n = int(top_n_str)

            if platform == 'reddit':
                top_authors_query = f"""
                WITH combined_reddit_comments AS (
                    SELECT * FROM reddit_comments
                    UNION ALL
                    SELECT * FROM reddit_2_comments
                )
                SELECT author, COUNT(*) AS post_count
                FROM combined_reddit_comments
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY author
                ORDER BY post_count DESC
                LIMIT %s;
                """
                daily_query = f"""
                WITH combined_reddit_comments AS (
                    SELECT * FROM reddit_comments
                    UNION ALL
                    SELECT * FROM reddit_2_comments
                )
                SELECT date_trunc('day', timestamp) AS day, author, COUNT(*) AS post_count
                FROM combined_reddit_comments
                WHERE timestamp BETWEEN %s AND %s
                AND author = ANY(%s)
                GROUP BY day, author
                ORDER BY day;
                """
                db_url = DB_URL_C 
            else:
                top_authors_query = f"""
                WITH combined_chan_comments AS (
                    SELECT * FROM chan_comments
                    UNION ALL
                    SELECT * FROM chan_2_comments
                )
                SELECT author, COUNT(*) AS post_count
                FROM combined_chan_comments
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY author
                ORDER BY post_count DESC
                LIMIT %s;
                """
                daily_query = f"""
                WITH combined_chan_comments AS (
                    SELECT * FROM chan_comments
                    UNION ALL
                    SELECT * FROM chan_2_comments
                )
                SELECT date_trunc('day', timestamp) AS day, author, COUNT(*) AS post_count
                FROM combined_chan_comments
                WHERE timestamp BETWEEN %s AND %s
                AND author = ANY(%s)
                GROUP BY day, author
                ORDER BY day;
                """
                db_url = DB_URL_C 

            top_authors = query_db(db_url, top_authors_query, (start_date, end_date, top_n))

            if len(top_authors) == 0:
                authors_message = "No data found."
                authors_plot_url = None
            else:
                author_list = [row['author'] for row in top_authors]
                daily_res = query_db(db_url, daily_query, (start_date, end_date, author_list))

                if len(daily_res) == 0:
                    authors_message = "No data after filtering top authors."
                    authors_plot_url = None
                else:
                    df = pd.DataFrame(daily_res)
                    plt.figure(figsize=(10,5))
                    for auth in author_list:
                        auth_df = df[df['author'] == auth]
                        plt.plot(auth_df['day'], auth_df['post_count'], marker='o', label=f"{auth}")
                    plt.xticks(rotation=45)
                    plt.xlabel("Day")
                    plt.ylabel("Post Count")
                    plt.title("Top Authors Over Time")
                    plt.legend()
                    plt.tight_layout()
                    filename = f"plot_{uuid.uuid4()}.png"
                    filepath = os.path.join('static', filename)
                    plt.savefig(filepath)
                    plt.close()
                    authors_plot_url = f"/static/{filename}"
                    author_counts_str = ", ".join([f"{row['author']}({row['post_count']})" for row in top_authors])
                    authors_message = (f"Top {top_n} authors shown: {author_counts_str}. "
                                    f"Platform: {platform}, Date Range: {start_date} to {end_date}")

    return render_template('additional_analysis.html',
                       reddit_submissions_plot_url=reddit_submissions_plot_url,
                       reddit_submissions_message=reddit_submissions_message,
                       reddit_comments_plot_url=reddit_comments_plot_url,
                       reddit_comments_message=reddit_comments_message,
                       chan_pol_comments_plot_url=chan_pol_comments_plot_url,
                       chan_pol_comments_message=chan_pol_comments_message,
                       rq1_plot_url=rq1_plot_url,
                       rq1_message=rq1_message,
                       rq2_plot_url=rq2_plot_url,
                       rq2_message=rq2_message,
                       rq3_plot_url=rq3_plot_url,
                       rq3_message=rq3_message,
                       authors_plot_url=authors_plot_url if 'authors_plot_url' in locals() else None,
                       authors_message=authors_message if 'authors_message' in locals() else None)

if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=True)
