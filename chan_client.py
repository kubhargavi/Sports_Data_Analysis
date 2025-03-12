import requests
import psycopg2
from dotenv import load_dotenv
import os
import logging
import datetime
import time
from toxicity_client import fetch_toxicity_score


load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
DATABASE_URL = os.getenv('DATABASE_URL')

def fetch_4chan_posts(board, limit=None):
    try:
        logging.info(f"Fetching posts from /{board}/ board")
        url = f"https://a.4cdn.org/{board}/catalog.json"
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            logging.error(f"Error fetching posts from /{board}/: {response.status_code}")
            return []
        posts = response.json()
        post_data_list = []
        for page in posts:
            for thread in page['threads']:
                post_data = {
                    'board': board,
                    'thread_id': thread['no'],
                    'subject': thread.get('sub', 'No Subject'),
                    'description': thread.get('com', ''),
                    'time': datetime.datetime.fromtimestamp(thread['time'], tz=datetime.timezone.utc),
                    'replies': thread.get('replies', 0),
                    'images': thread.get('images', 0),
                    'deleted': thread.get('archived', False) 
                }
                post_data_list.append(post_data)
        logging.info(f"Fetched {len(post_data_list)} posts from /{board}/")
        return post_data_list
    except requests.RequestException as e:
        logging.error(f"Error fetching posts from /{board}/: {e}")
        return []
    except Exception as e:
        logging.error(f"General error for /{board}/: {e}")
        return []

def fetch_4chan_comments(board, thread_id, max_retries=3):
    """Fetch comments (replies) for a specific thread from 4chan."""
    for attempt in range(max_retries):
        try:
            logging.info(f"Fetching comments for thread {thread_id} on /{board}/, Attempt {attempt + 1}")
            url = f"https://a.4cdn.org/{board}/thread/{thread_id}.json"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 404:
                logging.warning(f"Thread {thread_id} on /{board}/ not found or archived.")
                return []  
            
            if response.status_code != 200:
                logging.warning(f"Failed to fetch thread {thread_id} from board /{board}/. Status: {response.status_code}")
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
