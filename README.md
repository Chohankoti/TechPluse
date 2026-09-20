# ⚡ TechPulse: Autonomous AI News Curation Engine & LLM Benchmark

**TechPulse** is an open-source, zero-cost ($0.00 API fee) news curation engine that scans 500+ daily Hacker News posts, filters out noise, and delivers hyper-personalized technical briefings directly to your inbox.

---

## 🎯 Purpose

Reading through hundreds of technical blog posts every day is overwhelming. Most news engines rely on expensive cloud LLM APIs that add latency and monthly subscription fees. TechPulse was built to solve both problems:

* **$0.00 Operational API Cost:** Runs 100% locally on standard CPU using lightweight vector embeddings (`all-MiniLM-L6-v2`).
* **High-Precision Noise Reduction:** Rejects ~97% of irrelevant fluff so you only spend time reading high-signal engineering posts.
* **Sub-400ms Processing Latency:** Evaluates titles and article content body in milliseconds.
* **Audited Quality:** Features an LLM-as-a-Judge evaluation framework benchmarked against **Google Gemini 3.1 Flash-Lite**.

---

## 📩 Sample Email Digest View

| Header & Priority Section | Semantic "Why Read" Snippets | Read Later Section |
| :---: | :---: | :---: |
| ![Digest Header & Read First](src/data/view_split_1.jpg) | ![Semantic Snippets & Why Read](src/data/view_split_2.jpg) | ![Read Later Digest Section](src/data/view_split_3.jpg) |

---

## ⚡ Quick Start & Deployment

### Option 1: Fork & Deploy via GitHub Actions (Zero Local Setup)

1. **Fork this repository** to your GitHub account.
2. Navigate to **Settings > Secrets and variables > Actions** in your forked repo and add:
   * **Required Credentials:**
     * `FROM_EMAIL`: Sender Gmail address
     * `APP_PASSWORD`: Gmail App Password ([How to generate](https://support.google.com/accounts/answer/185833))
     * `TO_EMAIL`: Recipient email address
   * **Optional Threshold Secrets (Override Defaults):**
     * `TITLE_RELEVANCE_THRESHOLD`: Custom Stage 1 title threshold (defaults to `0.50`)
     * `CONTENT_RELEVANCE_THRESHOLD`: Custom Stage 2 body content threshold (defaults to `0.60`)
     * `TITLE_FALLBACK_THRESHOLD`: Custom title fallback threshold (defaults to `0.55`)
     * `READ_FIRST_THRESHOLD`: Custom Read-First priority threshold (defaults to `0.65`)
3. Enable **GitHub Actions** under the **Actions** tab. The automated workflow runs daily on schedule.

---

### Option 2: Local Development with `uv`

Clone the repo and sync dependencies:

```bash
git clone https://github.com/Chohankoti/TechPluse.git
cd TechPulse

# Install dependencies using uv
uv sync
```

Create a `.env` file in the root directory:

```ini
# API Keys & Email Credentials
TINYFISH_API_KEY="your-tinyfish-api-key"  
GOOGLE_API_KEY="your-google-gemini-api-key"    # Optional for running eval benchmark
FROM_EMAIL="your_email@gmail.com"
TO_EMAIL="recipient@gmail.com"
APP_PASSWORD="your-app-password"

# Post State & Hacker News API Endpoints
CONTENT_STATE_PATH="src/data/content_state.jsonc"
HN_TOP_STORIES_API="https://hacker-news.firebaseio.com/v0/topstories.json"
HN_NEW_STORIES_API="https://hacker-news.firebaseio.com/v0/newstories.json"
HN_ITEM_API="https://hacker-news.firebaseio.com/v0/item/{id}.json"

# Relevance Threshold & Engine Configurations
SENTENCE_TRANSFORMER_MODEL="all-MiniLM-L6-v2"
USER_CONSTRAINTS_PATH="src/data/user_constraints.jsonc"
TITLE_RELEVANCE_THRESHOLD=0.50
CONTENT_RELEVANCE_THRESHOLD=0.60
TITLE_FALLBACK_THRESHOLD=0.55
READ_FIRST_THRESHOLD=0.65
URL_FETCH_DELAY_SECONDS=1
```

---

## 🚀 Execution Commands

Execute pipeline scripts directly via `uv`:

```bash
# 1. Run main news ingestion & email briefing pipeline
uv run techpulse

# 2. Launch interactive Streamlit Rules Manager (GUI for interest rules & keywords)
uv run techpulse-constraints

# 3. Run LLM-as-a-Judge benchmark evaluation (TechPulse vs Gemini API)
uv run techpulse-eval
```

### 🎛️ Interactive Rules Manager UI (`uv run techpulse-constraints`)

Configure technical topic constraints, phrase weights, and keyword rules dynamically without editing code:

![Streamlit Rules Manager UI](src/data/view_user_constraints.png)

---

## 📊 Benchmark & Evaluation Report

TechPulse includes a 2-pass benchmark tool (`eval_engine.py`) comparing local embedding judgments against **Google Gemini 3.1 Flash-Lite** as ground truth:

| Core Metric | Result | Impact |
| :--- | :--- | :--- |
| **Noise Elimination Rate** | **97.1%** | Rejects 33 out of 34 off-topic Hacker News posts |
| **Precision** | **75.0%** | High relevance accuracy on flagged digests |
| **Local CPU Latency** | **~322 ms** | 10x faster than cloud LLM API calls |
| **Decision Parity** | **73.47%** | Strong alignment with frontier LLMs at $0 cost |

👉 **For the complete per-article breakdown, confusion matrix, and threshold trade-off analysis, see [evaluation_report.md](evaluation_report.md).**

---

## 📁 Project Structure

```
TechPulse/
├── .github/workflows/
│   └── schedule.yml             # GitHub Actions cron workflow
├── src/
│   ├── data/
│   │   ├── content_state.jsonc  # Processed post state & history
│   │   └── user_constraints.jsonc# Configurable topic interest rules
│   └── techpulse/
│       ├── relevance_checker.py # 2-pass SentenceTransformer vector engine
│       ├── executor.py          # Core pipeline orchestrator
│       ├── eval_engine.py       # LLM-as-a-Judge benchmark runner
│       ├── constraints_manager.py# Interactive Streamlit rules UI
│       ├── post_manager.py      # HTTP connection pooling & HN retriever
│       └── mail_manager.py      # Formatted SMTP digest builder
├── evaluation_report.md         # Detailed evaluation report & benchmark metrics
├── pyproject.toml               # Package configuration & CLI entry points
└── README.md
```

---

## 📜 License

MIT License. Free to use, modify, and distribute.
