import requests
import logging
import os
import json
import time
import threading
import re
from hashlib import sha256
from dotenv import load_dotenv
import psycopg2

load_dotenv()

MODERATE_API_URL = "https://api.moderatehatespeech.com/api/v1/moderate/"
MODERATE_API_KEY = os.getenv('MODERATE_API_KEY')
DATABASE_URL_T = os.getenv('DATABASE_URL_T')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def initialize_cache():
    try:
        conn = psycopg2.connect(DATABASE_URL_T)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS toxicity_cache (
                text_hash TEXT PRIMARY KEY,
                toxicity_class TEXT,
                confidence REAL
            )
        ''')
        conn.commit()
    except Exception as e:
        logging.error(f"Error initializing toxicity cache database: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

initialize_cache()

def normalize_text(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = text.lower()
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    return text

def get_cache(text):
    normalized_text = normalize_text(text)
    text_hash = sha256(normalized_text.encode('utf-8')).hexdigest()
    try:
        conn = psycopg2.connect(DATABASE_URL_T)
        cursor = conn.cursor()
        cursor.execute('SELECT toxicity_class, confidence FROM toxicity_cache WHERE text_hash = %s', (text_hash,))
        result = cursor.fetchone()
        if result:
            logging.info(f"Cache hit for text: {text[:50]}...")
            return result[0], result[1]
        else:
            logging.info(f"Cache miss for text: {text[:50]}...")
            return None, None
    except Exception as e:
        logging.error(f"Error accessing toxicity cache: {e}")
        return None, None
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def set_cache(text, toxicity_class, confidence):
    normalized_text = normalize_text(text)
    text_hash = sha256(normalized_text.encode('utf-8')).hexdigest()
    try:
        conn = psycopg2.connect(DATABASE_URL_T)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO toxicity_cache (text_hash, toxicity_class, confidence)
            VALUES (%s, %s, %s)
            ON CONFLICT (text_hash) DO UPDATE SET
                toxicity_class = EXCLUDED.toxicity_class,
                confidence = EXCLUDED.confidence
        ''', (text_hash, toxicity_class, confidence))
        conn.commit()
    except Exception as e:
        logging.error(f"Error setting toxicity cache: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def rate_limited(max_per_second):
    min_interval = 1.0 / float(max_per_second)
    lock = threading.Lock()
    last_time_called = [0.0]

    def decorator(func):
        def rate_limited_function(*args, **kwargs):
            with lock:
                elapsed = time.perf_counter() - last_time_called[0]
                left_to_wait = min_interval - elapsed
                if left_to_wait > 0:
                    time.sleep(left_to_wait)
                last_time_called[0] = time.perf_counter()
            return func(*args, **kwargs)
        return rate_limited_function
    return decorator

@rate_limited(1)  
def fetch_toxicity_score(text, max_retries=3):
    normalized_text = normalize_text(text)

    cached_class, cached_confidence = get_cache(normalized_text)
    if cached_class is not None and cached_confidence is not None:
        return cached_class, cached_confidence

    if not MODERATE_API_KEY:
        logging.error("Missing API Key for ModerateHatespeech.")
        return None, None

    if not normalized_text or len(normalized_text.strip()) == 0:
        logging.warning("Empty or missing text. Skipping toxicity check.")
        return None, None

    headers = {'Content-Type': 'application/json'}
    payload = {"token": MODERATE_API_KEY, "text": normalized_text}

    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            logging.info(f"Sending request to ModerateHatespeech API. Attempt {attempt}")
            response = requests.post(MODERATE_API_URL, headers=headers, json=payload, timeout=10)
            response.raise_for_status()

            if not response.content:
                logging.error("Empty response from ModerateHatespeech API.")
                time.sleep(2 ** attempt)
                continue 

            try:
                result = response.json()
            except json.JSONDecodeError as e:
                logging.error(f"JSONDecodeError: {e}. Response text: {response.text}")
                logging.debug(f"Raw response content: {response.content}")
                time.sleep(2 ** attempt)
                continue  

            if result.get('response') != 'Success':
                logging.error(f"API did not return success. Response: {result}")
                time.sleep(2 ** attempt)
                continue 

            toxicity_class = result.get('class')
            confidence = result.get('confidence')

            if toxicity_class is None or confidence is None:
                logging.warning(f"Received null values from API for text: {text[:50]}...")
                time.sleep(2 ** attempt)
                continue 

            try:
                confidence = float(confidence)
            except ValueError:
                logging.error(f"Invalid confidence value received: {confidence}. Text: {text[:50]}...")
                time.sleep(2 ** attempt)
                continue  

            if confidence < 0.5 or confidence > 1:
                logging.warning(f"Suspicious confidence score: {confidence} for text: {text[:50]}...")
                return None, None

            logging.info(f"Toxicity score: {toxicity_class}, Confidence: {confidence:.3f}")

            set_cache(normalized_text, toxicity_class, confidence)

            return toxicity_class, confidence

        except requests.exceptions.Timeout:
            logging.error("Request to ModerateHatespeech API timed out.")
            time.sleep(2 ** attempt)
            continue 

        except requests.exceptions.RequestException as e:
            logging.error(f"Request error: {e}")
            time.sleep(2 ** attempt)
            continue 

        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            time.sleep(2 ** attempt)
            continue

    logging.error(f"Failed to get toxicity score after {max_retries} attempts.")
    return None, None
