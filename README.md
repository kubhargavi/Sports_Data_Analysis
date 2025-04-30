## 1. 🧵 Running Crawlers

I implemented two crawlers:

- `reddit_crawler.py`: Gathers recent posts and comments from a list of subreddits in `subreddits.txt`
- `chan_crawler.py`: Collects posts and thread replies from 4chan boards listed in `chan.txt`

To run them, execute:

```bash
python reddit_crawler.py
python chan_crawler.py
```

These crawlers operate on a loop, continuously fetching new data and sending jobs to Faktory queues for processing.

---

## 2. 📦 Faktory

**Faktory** is a job queue system used here to manage background tasks efficiently.

- I used it to queue and process posts asynchronously from Reddit and 4chan.
- It allows reliable and scalable ingestion without overwhelming APIs.

**Faktory Docker Setup Used**:

```bash
docker run -d --name faktory \
  -v ~/projects/docker-disks/faktory-data:/var/lib/faktory/db \
  -e "FAKTORY_PASSWORD=###" \
  -p 127.0.0.1:7519:7519 \
  -p 127.0.0.1:7520:7520 \
  contribsys/faktory:latest \
  /faktory -b :7519 -w :7520
```

To run and monitor Faktory:

```bash
docker start faktory
```

- Access the Faktory web UI at: [http://127.0.0.1:7520](http://127.0.0.1:7520)

---

## 3. 🐘 Database Access via pgAdmin

All posts and comments were stored in **TimescaleDB**, a time-series optimized PostgreSQL database.

To explore and query this data visually, I set up **pgAdmin**

**timescaledb and pgAdmin Docker Setup Used**:

```bash
docker run -d --name timescaledb \
  -p 5432:5432 \
  -e POSTGRES_USER=### \
  -e POSTGRES_PASSWORD=### \
  -e POSTGRES_DB=crawler \
  timescale/timescaledb-ha:pg16
```

```bash
docker run -d --name pgadmin \
  -e PGADMIN_DEFAULT_EMAIL=<hashed_email> \
  -e PGADMIN_DEFAULT_PASSWORD=<hashed_password> \
  -p 5050:80 \
  dpage/pgadmin4
```

```bash
docker start pgadmin
docker start timescaledb
```

- Access pgAdmin at: [http://localhost:5050](http://localhost:5050)

---

## 4. 📊 Displaying the Dashboard

The web dashboard is built using **Flask** and allows users to interact with the collected data:

```bash
python app.py
```

- Access the dashboard at: [http://localhost:5000](http://localhost:5000)

### 🧭 Dashboard Navigation

#### Home Page (`/`)
- Landing page with navigation links to analysis sections.

#### `/datasets_analysis`
- Summary table showing total post and comment counts from Reddit and 4chan.
- Interactive visual filters:
  - **Toxicity Filter**: Filter and view toxicity distribution by source (`reddit`, `4chan`, or both).
  - **Post Count Filter**: Compare post volume between Reddit and 4chan.

#### `/reddit_analysis`
- Visuals for Reddit-specific datasets:
  - **Upvotes Over Time**: Line chart showing average upvotes per day.
  - **Toxicity Confidence vs Upvotes**: Scatter plot for correlation analysis.
  - **Toxicity Distribution**: Normal vs flagged post counts by subreddit.
  - **Activity Heatmap**: Post/comment activity by day of week and hour.
  - **Daily Comments**: Comments per day across chosen subreddits.
  - **Subreddit-wise Post Trends**: Trends for selected subreddits over time.

#### `/chan_analysis`
- Visuals for 4chan-specific datasets:
  - **Toxicity Distribution**: Flagged vs normal posts by board (`sp`, `xs`, etc.).
  - **Activity Heatmap**: Post activity by time on 4chan.
  - **Daily Comments**: Comments per day across chosen boards.
  - **Post Trends**: Board-wise trends over time.

---

#### `/additional_analysis`

This section provides **RQ-driven advanced insights** into Reddit and 4chan posts:

##### Key Features:

- **Most Toxic Posts**:
  - Displays top posts ranked by toxicity confidence.
  - Useful for identifying extreme or harmful discussions.

- **Toxicity vs Time**:
  - Line plot showing how toxicity fluctuates over days or hours.
  - Helps track harmful content trends over time.

- **Keyword-based Toxicity Search**:
  - Input a keyword (e.g., "win").
  - Dashboard filters posts/comments that contain the keyword and shows their toxicity classification and score.

- **Most Active Authors**:
  - Bar chart showing users who posted the most comments or posts over a period.
  - Helps surface influential or highly engaged users.

