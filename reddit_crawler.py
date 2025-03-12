import os
import time
import logging
from dotenv import load_dotenv
from pyfaktory import Client, Producer, Consumer, Job
from reddit_client import fetch_reddit_posts, fetch_reddit_comments
import psycopg2
from psycopg2.extras import Json
import datetime
from toxicity_client import fetch_toxicity_score
import concurrent.futures
from threading import Thread, Event

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
DATABASE_URL = os.getenv('DATABASE_URL')
no_posts_counter = {}
stop_event = Event() 

def get_record_count():
    try:
        connection = psycopg2.connect(DATABASE_URL)
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM reddit_2_posts;")
        row_count = cursor.fetchone()[0]
        logging.info(f"Total number of records in the database: {row_count}")
    except Exception as e:
        logging.error(f"Error getting record count: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

def submit_reddit_jobs():
    faktory_server_url = os.getenv('FAKTORY_SERVER_URL')
    with open('subreddits.txt', 'r') as f:
        SUBREDDITS = [line.strip() for line in f if line.strip()]
    with Client(faktory_url=faktory_server_url, role="producer", timeout=120) as client:
        producer = Producer(client=client)
        for subreddit in SUBREDDITS:
            posts = fetch_reddit_posts(subreddit)
            if not posts:
                logging.warning(f"No posts fetched from subreddit {subreddit}!")
                no_posts_counter[subreddit] = no_posts_counter.get(subreddit, 0) + 1
                if no_posts_counter[subreddit] >= 3:
                    logging.error(f"ALERT: No posts fetched from subreddit {subreddit} for 3 consecutive attempts.")
                continue 
            else:
                no_posts_counter[subreddit] = 0
            logging.info(f"Fetched {len(posts)} posts for subreddit {subreddit}.")
            for post in posts:
                post_serializable = {}
                for key, value in post.items():
                    if isinstance(value, datetime.datetime):
                        post_serializable[key] = value.isoformat()
                    else:
                        post_serializable[key] = value

                job = Job(jobtype="process-post", args=(post_serializable,), queue="reddit")
                producer.push(job)
                logging.info(f"Job submitted for post {post['post_id']} with title \"{post['title']}\"")
    get_record_count()

def store_reddit_comments():
    DATABASE_URL_C = os.getenv('DATABASE_URL_C')
    if not DATABASE_URL_C:
        logging.error("DATABASE_URL_C is not set. Cannot store comments.")
        return

    try:
        with psycopg2.connect(DATABASE_URL) as reddit_connection:
            with reddit_connection.cursor() as reddit_cursor:
                reddit_cursor.execute("SELECT post_id FROM reddit_2_posts;")
                post_ids = [row[0] for row in reddit_cursor.fetchall()]

        if not post_ids:
            logging.info("No posts found to fetch comments for.")
            return
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(process_post_comments, post_id)
                for post_id in post_ids
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.exception(f"Error processing comments for post: {e}")

    except Exception as e:
        logging.error(f"Error fetching or storing comments: {e}")

def process_post_comments(post_id):
    DATABASE_URL_C = os.getenv('DATABASE_URL_C')
    comments = fetch_reddit_comments(post_id)
    if not comments:
        logging.info(f"No comments fetched for post {post_id}.")
        return

    try:
        with psycopg2.connect(DATABASE_URL_C) as comm_connection:
            with comm_connection.cursor() as comm_cursor:
                create_table_query = """
                CREATE TABLE IF NOT EXISTS reddit_2_comments (
                    id SERIAL PRIMARY KEY,
                    post_id TEXT NOT NULL,
                    comment_id TEXT UNIQUE NOT NULL,
                    body TEXT,
                    author TEXT,
                    upvotes INTEGER,
                    timestamp TIMESTAMP,
                    parent_id TEXT,
                    toxicity_class TEXT,
                    toxicity_confidence FLOAT
                );
                """
                comm_cursor.execute(create_table_query)
                comm_connection.commit()

                for comment in comments:
                    insert_query = """
                    INSERT INTO reddit_2_comments (post_id, comment_id, body, author, upvotes,
                                                  timestamp, parent_id, toxicity_class, toxicity_confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (comment_id) DO NOTHING;
                    """
                    try:
                        comm_cursor.execute(insert_query, (
                            comment['post_id'],
                            comment['comment_id'],
                            comment['body'],
                            comment['author'],
                            comment['upvotes'],
                            comment['timestamp'],
                            comment['parent_id'],
                            comment['toxicity_class'],
                            comment['toxicity_confidence']
                        ))
                    except Exception as e:
                        logging.exception(f"Error inserting comment {comment['comment_id']} into database: {e}")
                        comm_connection.rollback()
                        continue

                comm_connection.commit()
                logging.info(f"Stored comments for post {post_id} in the `comments` database.")

    except Exception as e:
        logging.error(f"Error storing comments for post {post_id}: {e}")

def process_post(post):
    logging.info(f"Processing post: {post['post_id']}, Title: \"{post['title']}\"")
    try:
        if isinstance(post['timestamp'], str):
            post['timestamp'] = datetime.datetime.fromisoformat(post['timestamp'])

        with psycopg2.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                create_table_query = """
                CREATE TABLE IF NOT EXISTS reddit_2_posts (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    post_id TEXT UNIQUE,
                    content TEXT,
                    subreddit TEXT,
                    deleted BOOLEAN DEFAULT FALSE,
                    crawl_count INTEGER DEFAULT 0,
                    timestamp TIMESTAMP,
                    insertion_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    upvotes_history JSONB DEFAULT '[]'::jsonb,
                    downvotes_history JSONB DEFAULT '[]'::jsonb,
                    comments_history JSONB DEFAULT '[]'::jsonb,
                    update_history JSONB DEFAULT '[]'::jsonb,
                    toxicity_class TEXT,
                    toxicity_confidence FLOAT
                );
                """
                cursor.execute(create_table_query)

                cursor.execute("""
                    SELECT deleted, crawl_count, upvotes_history, downvotes_history, comments_history, update_history
                    FROM reddit_2_posts WHERE post_id = %s
                    """, (post['post_id'],))
                existing_record = cursor.fetchone()

                if existing_record:
                    existing_deleted = existing_record[0]
                    existing_crawl_count = existing_record[1]
                    existing_upvotes_history = existing_record[2] or []
                    existing_downvotes_history = existing_record[3] or []
                    existing_comments_history = existing_record[4] or []
                    existing_update_history = existing_record[5] or []
                    crawl_count = existing_crawl_count + 1
                else:
                    existing_deleted = None
                    existing_upvotes_history = []
                    existing_downvotes_history = []
                    existing_comments_history = []
                    existing_update_history = []
                    crawl_count = 1 

                new_upvotes_history = existing_upvotes_history[:]
                if not existing_upvotes_history or existing_upvotes_history[-1].get('value') != post['upvotes']:
                    new_upvotes_history.append({'crawl': crawl_count, 'value': post['upvotes']})

                new_downvotes_history = existing_downvotes_history[:]
                if not existing_downvotes_history or existing_downvotes_history[-1].get('value') != post['downvotes']:
                    new_downvotes_history.append({'crawl': crawl_count, 'value': post['downvotes']})

                new_comments_history = existing_comments_history[:]
                if not existing_comments_history or existing_comments_history[-1].get('value') != post['comment_count']:
                    new_comments_history.append({'crawl': crawl_count, 'value': post['comment_count']})

                has_changes = False
                changes = {}
                fields_to_track = ["upvotes", "downvotes", "comment_count", "deleted"]

                for field in fields_to_track:
                    if field == "upvotes":
                        last_value = existing_upvotes_history[-1].get('value') if existing_upvotes_history else None
                    elif field == "downvotes":
                        last_value = existing_downvotes_history[-1].get('value') if existing_downvotes_history else None
                    elif field == "comment_count":
                        last_value = existing_comments_history[-1].get('value') if existing_comments_history else None
                    elif field == "deleted":
                        last_value = existing_deleted
                    current_value = post.get(field)
                    if current_value != last_value:
                        changes[field] = current_value
                        has_changes = True

                if has_changes:
                    changes['crawl_time'] = datetime.datetime.utcnow().isoformat()
                    changes['crawl'] = crawl_count
                    new_update_history = existing_update_history + [changes]
                else:
                    new_update_history = existing_update_history

                text_for_toxicity = post['title'] if post['title'] else post['content']
                toxicity_class, toxicity_confidence = fetch_toxicity_score(text_for_toxicity)

                if existing_record:
                    update_query = """
                    UPDATE reddit_2_posts SET
                        title = %s,
                        content = %s,
                        subreddit = %s,
                        deleted = %s,
                        crawl_count = %s,
                        timestamp = %s,
                        upvotes_history = %s,
                        downvotes_history = %s,
                        comments_history = %s,
                        update_history = %s,
                        toxicity_class = %s,
                        toxicity_confidence = %s
                    WHERE post_id = %s;
                    """
                    cursor.execute(update_query, (
                        post['title'],
                        post['content'],
                        post['subreddit'],
                        post.get('deleted', False),
                        crawl_count,
                        post['timestamp'],
                        Json(new_upvotes_history),
                        Json(new_downvotes_history),
                        Json(new_comments_history),
                        Json(new_update_history),
                        toxicity_class,
                        toxicity_confidence,
                        post['post_id']
                    ))
                else:
                    insert_query = """
                    INSERT INTO reddit_2_posts (title, post_id, content, subreddit, deleted, crawl_count, timestamp,
                                              upvotes_history, downvotes_history, comments_history, update_history, toxicity_class, toxicity_confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    changes = {
                        "crawl_time": datetime.datetime.utcnow().isoformat(),
                        "upvotes": post.get('upvotes'),
                        "downvotes": post.get('downvotes'),
                        "comment_count": post.get('comment_count'),
                        "deleted": post.get('deleted', False),
                        "crawl": crawl_count
                    }
                    new_update_history = [changes]
                    new_upvotes_history = [{'crawl': crawl_count, 'value': post['upvotes']}]
                    new_downvotes_history = [{'crawl': crawl_count, 'value': post['downvotes']}]
                    new_comments_history = [{'crawl': crawl_count, 'value': post['comment_count']}]

                    cursor.execute(insert_query, (
                        post['title'],
                        post['post_id'],
                        post['content'],
                        post['subreddit'],
                        post.get('deleted', False),
                        crawl_count,
                        post['timestamp'],
                        Json(new_upvotes_history),
                        Json(new_downvotes_history),
                        Json(new_comments_history),
                        Json(new_update_history),
                        toxicity_class,
                        toxicity_confidence
                    ))

                connection.commit()
                logging.info(f"Post {post['post_id']} inserted/updated in the database with updates logged.")

    except psycopg2.DatabaseError as db_error:
        logging.exception(f"DatabaseError for post {post['post_id']}: {db_error}")

    except Exception as e:
        logging.exception(f"Error processing post {post['post_id']}: {e}")

def start_faktory_worker():
    faktory_server_url = os.getenv('FAKTORY_SERVER_URL')

    while not stop_event.is_set():
        try:
            with Client(faktory_url=faktory_server_url, role="consumer", timeout=120) as client:
                consumer = Consumer(client=client, queues=["reddit"], concurrency=5)
                consumer.register("process-post", process_post)
                consumer.run()
        except Exception as e:
            logging.exception(f"Exception in Faktory worker: {e}")
            time.sleep(5)

def run_submit_jobs():
    while not stop_event.is_set():
        submit_reddit_jobs()
        stop_event.wait(300)

def run_store_comments():
    while not stop_event.is_set():
        store_reddit_comments()
        stop_event.wait(300)

if __name__ == "__main__":
    worker_thread = Thread(target=start_faktory_worker, daemon=True)
    worker_thread.start()
    logging.info("Faktory worker started.")

    submit_jobs_thread = Thread(target=run_submit_jobs, daemon=True)
    submit_jobs_thread.start()
    logging.info("Submit jobs thread started.")

    store_comments_thread = Thread(target=run_store_comments, daemon=True)
    store_comments_thread.start()
    logging.info("Store comments thread started.")

    try:
        while True:
            time.sleep(1) 
    except KeyboardInterrupt:
        logging.info("Shutting down.")
        stop_event.set()
        worker_thread.join()
        submit_jobs_thread.join()
        store_comments_thread.join()
