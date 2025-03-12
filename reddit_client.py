import requests
import psycopg2
from dotenv import load_dotenv
import os
import datetime
from requests.auth import HTTPBasicAuth
import time
import logging
from toxicity_client import fetch_toxicity_score

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
DATABASE_URL = os.getenv('DATABASE_URL')

def get_reddit_token():
    try:
        auth = HTTPBasicAuth(os.getenv('REDDIT_CLIENT_ID'), os.getenv('REDDIT_SECRET'))
        headers = {'User-Agent': os.getenv('REDDIT_USER_AGENT')}
        data = {'grant_type': 'client_credentials'}
        response = requests.post('https://www.reddit.com/api/v1/access_token', auth=auth, data=data, headers=headers)
        response.raise_for_status()
        token = response.json().get('access_token')
        return token
    except requests.RequestException as e:
        logging.error(f"Error getting Reddit token: {e}")
        return None

def fetch_reddit_posts(subreddit, max_retries=3):
    for attempt in range(max_retries):
        try:
            logging.info(f"Fetching posts from /r/{subreddit}, Attempt {attempt + 1}")
            token = get_reddit_token()
            if not token:
                logging.error(f"Failed to get token for subreddit: {subreddit}")
                return []
            headers = {"Authorization": f"Bearer {token}", 'User-Agent': os.getenv('REDDIT_USER_AGENT')}
            url = f"https://oauth.reddit.com/r/{subreddit}/hot"
            params = {'limit': None}
            response = requests.get(url, headers=headers, params=params, timeout=30)
            if response.status_code == 429:
                rate_limit_reset = int(response.headers.get('X-Ratelimit-Reset', 60))
                logging.warning(f"Rate limit exceeded for /r/{subreddit}. Waiting for {rate_limit_reset} seconds before retrying...")
                time.sleep(rate_limit_reset)
                continue 

            response.raise_for_status()
            posts = response.json()
            if not posts.get('data', {}).get('children', []):
                logging.info(f"No posts fetched from /r/{subreddit}.")
                return []
            post_data_list = []
            for post in posts['data']['children']:
                post_data = post['data']
                post_data_list.append({
                    'title': post_data['title'],
                    'post_id': post_data['id'],
                    'content': post_data.get('selftext', ''),
                    'subreddit': post_data['subreddit'],
                    'upvotes': post_data['ups'],
                    'downvotes': post_data['downs'],
                    'comment_count': post_data.get('num_comments', 0),
                    'deleted': post_data.get('removed_by_category') is not None,
                    'timestamp': datetime.datetime.fromtimestamp(post_data['created_utc'], tz=datetime.timezone.utc)
                })
            logging.info(f"Fetched {len(post_data_list)} posts from /r/{subreddit}")
            return post_data_list
        except requests.RequestException as e:
            logging.error(f"RequestException while fetching posts from /r/{subreddit}: {e}")
            time.sleep(5)
            continue 

        except Exception as e:
            logging.error(f"General error for /r/{subreddit}: {e}")
            return []
    logging.error(f"Failed to fetch posts from /r/{subreddit} after {max_retries} attempts.")
    return []

def fetch_reddit_comments(post_id, max_retries=3):
    for attempt in range(max_retries):
        try:
            logging.info(f"Fetching comments for post {post_id}, Attempt {attempt + 1}")
            token = get_reddit_token()
            if not token:
                logging.error(f"Failed to get token for post: {post_id}")
                return []
            headers = {"Authorization": f"Bearer {token}", 'User-Agent': os.getenv('REDDIT_USER_AGENT')}
            url = f"https://oauth.reddit.com/comments/{post_id}"
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 429:
                rate_limit_reset = int(response.headers.get('X-Ratelimit-Reset', 60))
                logging.warning(f"Rate limit exceeded for post {post_id}. Waiting for {rate_limit_reset} seconds before retrying...")
                time.sleep(rate_limit_reset)
                continue 

            response.raise_for_status()
            comments = response.json()
            comment_data_list = []

            for child in comments[1].get('data', {}).get('children', []):
                comment_data = child.get('data', {})
                if 'body' in comment_data:
                    toxicity_class, toxicity_confidence = fetch_toxicity_score(comment_data['body'])
                    comment_data_list.append({
                        'post_id': post_id,
                        'comment_id': comment_data['id'],
                        'body': comment_data['body'],
                        'author': comment_data.get('author', '[deleted]'),
                        'upvotes': comment_data.get('ups', 0),
                        'timestamp': datetime.datetime.fromtimestamp(comment_data.get('created_utc', 0), tz=datetime.timezone.utc),
                        'parent_id': comment_data.get('parent_id', ''),
                        'toxicity_class': toxicity_class,
                        'toxicity_confidence': toxicity_confidence
                    })

            logging.info(f"Fetched {len(comment_data_list)} comments for post {post_id}")
            return comment_data_list

        except requests.RequestException as e:
            logging.error(f"RequestException while fetching comments for post {post_id}: {e}")
            time.sleep(5)
            continue 

        except Exception as e:
            logging.error(f"General error for post {post_id}: {e}")
            return []

    logging.error(f"Failed to fetch comments for post {post_id} after {max_retries} attempts.")
    return []
