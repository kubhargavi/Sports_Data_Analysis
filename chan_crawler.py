import os
import time
import logging
from dotenv import load_dotenv
from pyfaktory import Client, Producer, Consumer, Job
from chan_client import fetch_4chan_posts
import psycopg2
from psycopg2.extras import Json
import datetime
from toxicity_client import fetch_toxicity_score
from chan_client import fetch_4chan_comments
import requests
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
        cursor.execute("SELECT COUNT(*) FROM chan_2_posts;")
        row_count = cursor.fetchone()[0]
        logging.info(f"Total number of records in the database: {row_count}")
    except Exception as e:
        logging.error(f"Error getting record count: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

def submit_4chan_jobs():
    faktory_server_url = os.getenv('FAKTORY_SERVER_URL')
    with open('chan.txt', 'r') as f:
        BOARDS = [line.strip() for line in f if line.strip()]
    with Client(faktory_url=faktory_server_url, role="producer", timeout=120) as client:
        producer = Producer(client=client)
        for board in BOARDS:
            posts = fetch_4chan_posts(board, limit=None)
            if not posts:
                logging.warning(f"No posts fetched from board /{board}/!")
                no_posts_counter[board] = no_posts_counter.get(board, 0) + 1
                if no_posts_counter[board] >= 3:
                    logging.error(f"ALERT: No posts fetched from board /{board}/ for 3 consecutive attempts.")
                continue
            else:
                no_posts_counter[board] = 0
            logging.info(f"Fetched {len(posts)} posts for board /{board}/.")
            for post in posts:
                post['time'] = post['time'].isoformat()
                job = Job(jobtype="process-post", args=(post,), queue="4chan")
                producer.push(job)
                logging.info(f"Job submitted for thread {post['thread_id']} with subject \"{post['subject']}\"")
    get_record_count()

def store_4chan_comments():
    DATABASE_URL_C = os.getenv('DATABASE_URL_C')

    if not DATABASE_URL_C:
        logging.error("DATABASE_URL_C is not set. Cannot store comments.")
        return

    try:
        with psycopg2.connect(DATABASE_URL) as chan_connection:
            with chan_connection.cursor() as chan_cursor:
                chan_cursor.execute("SELECT board, thread_id FROM chan_2_posts WHERE deleted = FALSE;")
                threads = chan_cursor.fetchall()

        if not threads:
            logging.info("No threads found to fetch comments for.")
            return

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(process_thread_comments, board, thread_id)
                for board, thread_id in threads
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.exception(f"Error processing thread comments: {e}")

    except Exception as e:
        logging.exception(f"Error in store_4chan_comments(): {e}")

def process_thread_comments(board, thread_id):
    DATABASE_URL_C = os.getenv('DATABASE_URL_C')

    comments = fetch_4chan_comments_with_status(board, thread_id)
    if comments is None:
        mark_thread_as_deleted(thread_id)
        logging.info(f"Thread {thread_id} on /{board}/ marked as deleted.")
        return
    elif not comments:
        logging.info(f"No comments fetched for thread {thread_id} on /{board}/.")
        return

    try:
        with psycopg2.connect(DATABASE_URL_C) as comm_connection:
            with comm_connection.cursor() as comm_cursor:
                create_table_query = """
                CREATE TABLE IF NOT EXISTS chan_2_comments (
                    id SERIAL PRIMARY KEY,
                    thread_id BIGINT NOT NULL,
                    comment_id BIGINT UNIQUE NOT NULL,
                    body TEXT,
                    author TEXT,
                    timestamp TIMESTAMP,
                    toxicity_class TEXT,
                    toxicity_confidence FLOAT
                );
                """
                comm_cursor.execute(create_table_query)
                comm_connection.commit()

                for comment in comments:
                    insert_query = """
                    INSERT INTO chan_2_comments (thread_id, comment_id, body, author, timestamp, toxicity_class, toxicity_confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (comment_id) DO NOTHING;
                    """
                    try:
                        comm_cursor.execute(insert_query, (
                            comment['thread_id'],
                            comment['comment_id'],
                            comment['body'],
                            comment['author'],
                            comment['timestamp'],
                            comment['toxicity_class'],
                            comment['toxicity_confidence']
                        ))
                    except Exception as e:
                        logging.exception(f"Error inserting comment {comment['comment_id']} into database: {e}")
                        comm_connection.rollback()
                        continue 

                comm_connection.commit()
                logging.info(f"Stored comments for thread {thread_id} on /{board}/ in the `Comm` database.")

    except Exception as e:
        logging.exception(f"Error storing comments for thread {thread_id}: {e}")

def fetch_4chan_comments_with_status(board, thread_id, max_retries=3):
    for attempt in range(max_retries):
        try:
            logging.info(f"Fetching comments for thread {thread_id} on /{board}/, Attempt {attempt + 1}")
            url = f"https://a.4cdn.org/{board}/thread/{thread_id}.json"
            response = requests.get(url, timeout=30)

            if response.status_code == 404:
                logging.warning(f"Thread {thread_id} on /{board}/ no longer exists. Status: {response.status_code}")
                return None 

            if response.status_code != 200:
                logging.warning(f"Failed to fetch thread {thread_id} from board /{board}/. Status: {response.status_code}")
                time.sleep(5)
                continue

            thread_data = response.json()
            comments = []

            for post in thread_data.get('posts', []):
                if post['no'] != thread_id: 
                    toxicity_class, toxicity_confidence = fetch_toxicity_score(post.get('com', ''))

                    comments.append({
                        'thread_id': thread_id,
                        'comment_id': post['no'],
                        'body': post.get('com', ''),
                        'author': post.get('name', 'Anonymous'),
                        'timestamp': datetime.datetime.fromtimestamp(post['time'], tz=datetime.timezone.utc),
                        'toxicity_class': toxicity_class,
                        'toxicity_confidence': toxicity_confidence,
                    })

            logging.info(f"Fetched {len(comments)} comments for thread {thread_id} on /{board}/.")
            return comments

        except requests.RequestException as e:
            logging.error(f"RequestException while fetching comments for thread {thread_id}: {e}")
            time.sleep(5)
            continue

        except Exception as e:
            logging.error(f"General error for thread {thread_id}: {e}")
            return []

    logging.error(f"Failed to fetch comments for thread {thread_id} on /{board}/ after {max_retries} attempts.")
    return []

def mark_thread_as_deleted(thread_id):
    try:
        with psycopg2.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                update_query = """
                UPDATE chan_2_posts SET deleted = TRUE WHERE thread_id = %s;
                """
                cursor.execute(update_query, (thread_id,))
                connection.commit()
    except Exception as e:
        logging.error(f"Error marking thread {thread_id} as deleted: {e}")

def process_post(post):
    logging.info(f"Processing thread: {post['thread_id']}, Subject: \"{post['subject']}\"")

    try:
        if isinstance(post['time'], str):
            post['time'] = datetime.datetime.fromisoformat(post['time'])

        with psycopg2.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                create_table_query = """
                CREATE TABLE IF NOT EXISTS chan_2_posts (
                    id SERIAL PRIMARY KEY,
                    board TEXT,
                    thread_id BIGINT UNIQUE,
                    subject TEXT,
                    description TEXT,
                    time TIMESTAMP,
                    deleted BOOLEAN DEFAULT FALSE,
                    replies_history JSONB DEFAULT '[]'::jsonb,
                    images_history JSONB DEFAULT '[]'::jsonb,
                    update_history JSONB DEFAULT '[]'::jsonb,
                    insertion_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    crawl_count INTEGER DEFAULT 0,
                    toxicity_class TEXT,
                    toxicity_confidence FLOAT
                );
                """
                cursor.execute(create_table_query)

                cursor.execute("""
                    SELECT deleted, replies_history, images_history, update_history, crawl_count
                    FROM chan_2_posts WHERE thread_id = %s
                """, (post['thread_id'],))
                existing_record = cursor.fetchone()

                if existing_record:
                    existing_deleted = existing_record[0]
                    existing_replies_history = existing_record[1] or []
                    existing_images_history = existing_record[2] or []
                    existing_update_history = existing_record[3] or []
                    crawl_count = existing_record[4] + 1
                else:
                    existing_deleted = False
                    existing_replies_history = []
                    existing_images_history = []
                    existing_update_history = []
                    crawl_count = 1

                new_replies_history = existing_replies_history[:]
                if not existing_replies_history or existing_replies_history[-1].get('value') != post['replies']:
                    new_replies_history.append({'crawl': crawl_count, 'value': post['replies']})

                new_images_history = existing_images_history[:]
                if not existing_images_history or existing_images_history[-1].get('value') != post['images']:
                    new_images_history.append({'crawl': crawl_count, 'value': post['images']})

                is_deleted = post.get('deleted', False)

                changes = {}
                fields_to_track = ["replies", "images", "deleted"]

                for field in fields_to_track:
                    current_value = post[field] if field != "deleted" else is_deleted
                    last_value = None
                    if field == "replies":
                        last_value = existing_replies_history[-1].get('value') if existing_replies_history else None
                    elif field == "images":
                        last_value = existing_images_history[-1].get('value') if existing_images_history else None
                    elif field == "deleted":
                        last_value = existing_deleted

                    if current_value != last_value:
                        changes[field] = current_value

                if changes:
                    changes['crawl'] = crawl_count
                    changes['crawl_time'] = datetime.datetime.utcnow().isoformat()
                    new_update_history = existing_update_history + [changes]
                else:
                    new_update_history = existing_update_history

                text_for_toxicity = post['subject'] if post['subject'] else post['description']
                toxicity_class, toxicity_confidence = fetch_toxicity_score(text_for_toxicity)

                if existing_record:
                    update_query = """
                    UPDATE chan_2_posts SET
                        subject = %s,
                        description = %s,
                        time = %s,
                        deleted = %s,
                        replies_history = %s,
                        images_history = %s,
                        update_history = %s,
                        crawl_count = %s,
                        toxicity_class = %s,
                        toxicity_confidence = %s
                    WHERE thread_id = %s;
                    """
                    cursor.execute(update_query, (
                        post['subject'],
                        post['description'],
                        post['time'],
                        is_deleted,
                        Json(new_replies_history),
                        Json(new_images_history),
                        Json(new_update_history),
                        crawl_count,
                        toxicity_class,
                        toxicity_confidence,
                        post['thread_id']
                    ))
                else:
                    insert_query = """
                    INSERT INTO chan_2_posts (board, thread_id, subject, description, time, deleted,
                                            replies_history, images_history, update_history, crawl_count, toxicity_class, toxicity_confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """

                    changes = {
                        "crawl_time": datetime.datetime.utcnow().isoformat(),
                        "replies": post.get('replies'),
                        "images": post.get('images'),
                        "deleted": is_deleted,
                        "crawl": crawl_count
                    }
                    new_replies_history = [{'crawl': crawl_count, 'value': post['replies']}]
                    new_images_history = [{'crawl': crawl_count, 'value': post['images']}]
                    new_update_history = [changes]

                    cursor.execute(insert_query, (
                        post['board'],
                        post['thread_id'],
                        post['subject'],
                        post['description'],
                        post['time'],
                        is_deleted,
                        Json(new_replies_history),
                        Json(new_images_history),
                        Json(new_update_history),
                        crawl_count,
                        toxicity_class,
                        toxicity_confidence
                    ))

                connection.commit()
                logging.info(f"Thread {post['thread_id']} processed and logged in the database.")

    except psycopg2.DatabaseError as db_error:
        logging.exception(f"DatabaseError for thread {post['thread_id']}: {db_error}")
    except Exception as e:
        logging.exception(f"Error processing thread {post['thread_id']}: {e}")

def start_faktory_worker():
    faktory_server_url = os.getenv('FAKTORY_SERVER_URL')
    while not stop_event.is_set():
        try:
            with Client(faktory_url=faktory_server_url, role="consumer", timeout=120) as client:
                consumer = Consumer(client=client, queues=["4chan"], concurrency=5)
                consumer.register("process-post", process_post)
                consumer.run()
        except Exception as e:
            logging.exception(f"Exception in Faktory worker: {e}")
            time.sleep(5) 

def run_submit_jobs():
    while not stop_event.is_set():
        submit_4chan_jobs()
        stop_event.wait(300) 

def run_store_comments():
    while not stop_event.is_set():
        store_4chan_comments()
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
