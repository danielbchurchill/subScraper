# SubScraper

A locally-hosted web app that finds subtitles for TV shows, downloads them automatically, and translates non-English subtitles to English using a local LLM — no ongoing API costs for translation.

**Workflow:** enter an IMDB ID → browse episodes → click Fetch. If English subtitles exist on SubDL or OpenSubtitles, they're downloaded immediately. If only Japanese (or another language) subtitles are found, they're downloaded and queued for translation via Ollama running on your machine.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | `python3 --version` to check |
| Git | any | to clone the repo |
| Ollama | latest | for translation — see install below |

**Free API accounts required (both take ~2 minutes to sign up):**
- [SubDL](https://subdl.com) — sign up → account → API key
- [OpenSubtitles](https://www.opensubtitles.com/consumers) — sign up → Consumers → create an app

---

## Installation

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/subScraper.git
cd subScraper

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

> **Note:** The install pulls `llm-subtrans` directly from GitHub. Git must be available on your PATH. On Windows you may need [Git for Windows](https://git-scm.com/download/win).

---

## Install Ollama

Ollama runs the local LLM that translates subtitles. It's free and stays on your machine.

**macOS**
```bash
brew install ollama
```

**Windows / Linux**  
Download the installer from [ollama.com](https://ollama.com/download).

**Pull the recommended model** (~4 GB download, needs ~8 GB RAM):
```bash
ollama pull qwen2.5:7b
```

Other models that work well for Japanese→English: `llama3.1:8b`, `mistral:7b`.  
If you have less RAM, try `qwen2.5:3b` (~2 GB).

---

## Running

```bash
# In one terminal — keep this running while you translate
ollama serve

# In another terminal
source .venv/bin/activate
python run.py
```

Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## Configuration

On first launch, go to the **Settings tab** in the UI and enter your API keys there. They'll be saved to a local `.env` file and never leave your machine.

Alternatively, copy `.env.example` to `.env` and edit it directly:

```bash
cp .env.example .env
```

```ini
# SubDL — get from https://subdl.com (account settings)
SUBDL_API_KEY=your_subdl_key_here

# OpenSubtitles — get from https://www.opensubtitles.com/consumers
OPENSUBTITLES_API_KEY=your_opensubtitles_key_here
OPENSUBTITLES_USERNAME=your_username
OPENSUBTITLES_PASSWORD=your_password

# Ollama (defaults are fine if running locally)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

After editing `.env` directly, restart the server.

> **Security:** `.env` is in `.gitignore` and will never be committed. Never share it.

---

## Usage

### Quick start — Banshaku No Ryuugi (Evening Drink Style) Season 2

1. Open [http://localhost:8000](http://localhost:8000)
2. Enter IMDB ID: **`tt13742506`**  
   *(or search "Banshaku No Ryuugi" on [imdb.com](https://imdb.com) and copy the `tt` ID from the URL)*
3. Click **Load Show** — the episode list loads from IMDB
4. Select **Season 2** from the season buttons
5. Click **Fetch all S2 subtitles** to search and download everything in one go
6. Episodes with English subs show a green ✓ badge immediately
7. Episodes being translated show ⟳ — switch to the **Jobs tab** to watch progress
8. When done, click **Download SRT** on any episode

### How subtitles are found

For each episode, SubScraper:
1. Searches SubDL **and** OpenSubtitles in parallel for English subtitles
2. If English found → downloads and saves immediately
3. If not → searches for Japanese, Chinese, Korean, French, Spanish (in that order)
4. If any found → downloads and queues a background translation job
5. Translated SRT is saved alongside the source file in `data/subtitles/`

### Where are the SRT files?

```
data/
└── subtitles/
    └── tt13742506/
        ├── S02E01/
        │   ├── english.srt          # if found directly
        │   └── source_ja.srt        # original Japanese (kept as reference)
        ├── S02E02/
        │   ├── source_ja.srt
        │   └── translated.srt       # translated by Ollama
        └── ...
```

---

## Troubleshooting

**"IMDB lookup failed"**  
`cinemagoer` scrapes IMDB directly — it can be slow (5–10s) or occasionally blocked. Try again. If it keeps failing, check your internet connection.

**"No subtitles found" for every episode**  
- Verify your API keys are set (Settings tab → check the badges)
- Some shows have very few subtitles available, especially recent Japanese dramas
- Try the other source: if SubDL has nothing, OpenSubtitles sometimes does

**Translation never finishes / "Job failed"**  
- Make sure Ollama is running: `ollama serve` in a terminal
- Check the model is downloaded: `ollama list` — should show `qwen2.5:7b`
- Check Ollama logs: `ollama serve` will print errors in the terminal
- If RAM is tight, switch to a smaller model in Settings: `qwen2.5:3b`

**Translation quality is poor**  
- `qwen2.5:7b` is the sweet spot of quality vs. speed for Japanese→English
- For higher quality (and more RAM), try `qwen2.5:14b` or `llama3.1:70b` (needs 32GB+ RAM)

**Port 8000 already in use**  
Edit `run.py` and change `port=8000` to another port.

**OpenSubtitles "download limit reached"**  
Free accounts get 20 downloads/day. The limit resets at midnight UTC. SubDL has a separate limit — both are checked independently.

---

## Architecture

```
subScraper/
├── api/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings loaded from .env
│   ├── models.py            # Pydantic schemas
│   ├── routes/
│   │   ├── shows.py         # GET /shows/{imdb_id}/episodes
│   │   ├── subtitles.py     # POST /subtitles/fetch, GET /subtitles/download
│   │   ├── jobs.py          # GET /jobs, GET /jobs/stream/all (SSE)
│   │   └── settings_route.py # GET/POST /settings
│   └── services/
│       ├── subdl.py         # SubDL API client
│       ├── opensubtitles.py # OpenSubtitles REST API client
│       ├── imdb.py          # cinemagoer wrapper (no API key needed)
│       ├── translation.py   # llm-subtrans + Ollama integration
│       └── env_manager.py   # .env read/write for Settings UI
├── web/
│   ├── index.html           # Single-page UI
│   └── static/
│       ├── app.js           # Vanilla JS, tabs, SSE job stream
│       └── style.css
├── data/                    # Created on first run, not committed
│   ├── subtitles/           # Downloaded and translated SRTs
│   └── jobs/                # Translation job state (JSON)
├── .env.example             # Template — copy to .env and fill in
├── requirements.txt
└── run.py
```

Translation progress streams to the browser via [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) so the Jobs tab updates in real time without polling.

---

## License

MIT
