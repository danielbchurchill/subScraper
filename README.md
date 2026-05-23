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
git clone https://github.com/danielbchurchill/subScraper.git
cd subScraper
```

Then run the start script — it creates the virtual environment and installs dependencies automatically:

**macOS / Linux:**
```bash
./start.sh
```

**Windows** — double-click `start.bat`, or in a terminal:
```bat
start.bat
```

Open **[http://localhost:8000](http://localhost:8000)** in your browser.

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
```

**macOS / Linux** — in a second terminal:
```bash
./start.sh
```

**Windows:**
```bat
start.bat
```

Open **[http://localhost:8000](http://localhost:8000)**.

> If you prefer to manage the venv yourself: `source .venv/bin/activate` then `python run.py`.

---

## Configuration

On first launch, go to the **Settings tab** in the UI and enter your API keys there. They're saved to a local `.env` file and never leave your machine. **No restart needed** — settings take effect immediately.

Alternatively, copy `.env.example` to `.env` and edit it directly, then restart the server:

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

> **Security:** `.env` is in `.gitignore` and will never be committed. Never share it.

---

## Usage

### Quick start — Banshaku No Ryuugi (Evening Drink Style)

1. Open [http://localhost:8000](http://localhost:8000)
2. Enter IMDB ID: **`tt13742506`**
   *(or search the show on [imdb.com](https://imdb.com) and copy the `tt` ID from the URL)*
3. Click **Load Show** — the episode list loads from TVmaze
4. Select a season from the season buttons
5. Click **Fetch all subtitles** to search and download the whole season
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

"Fetch all season" fetches episodes one at a time to stay within API rate limits.

### Where are the SRT files?

```
data/
└── subtitles/
    └── tt13742506/
        ├── S02E01/
        │   └── english.srt          # if found directly
        ├── S02E02/
        │   ├── source_ja.srt        # original Japanese (kept as reference)
        │   └── translated.srt       # translated by Ollama
        └── ...
```

---

## Troubleshooting

**"No subtitles found" for every episode**
- Verify your API keys are set (Settings tab → check the badges next to each key)
- Some shows have very few subtitles available, especially recent Japanese dramas
- SubDL and OpenSubtitles have different catalogues — one may have what the other doesn't

**Translation never finishes / "Job failed"**
- Make sure Ollama is running: `ollama serve` in a terminal
- Check the model is downloaded: `ollama list` — should show `qwen2.5:7b`
- Ollama logs errors in its terminal window
- If RAM is tight, switch to a smaller model in Settings: `qwen2.5:3b`

**Translation quality is poor**
- `qwen2.5:7b` is the sweet spot of quality vs. speed for Japanese→English
- For higher quality (and more RAM), try `qwen2.5:14b`

**Port 8000 already in use**
Edit `run.py` and change `port=8000` to another port.

**OpenSubtitles "download limit reached"**
Free accounts get 20 downloads/day. The limit resets at midnight UTC. SubDL has a separate limit — both are checked independently.

**"Failed to load show"**
SubScraper uses the TVmaze API to look up episode lists by IMDB ID. If a show doesn't appear, check that the IMDB ID is correct and that the show exists on [tvmaze.com](https://tvmaze.com). Very new or obscure shows may not be indexed yet.

---

## Architecture

```
subScraper/
├── api/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings loaded from .env via pydantic-settings
│   ├── models.py            # Pydantic schemas
│   ├── routes/
│   │   ├── shows.py         # GET /shows/{imdb_id}/episodes + /title
│   │   ├── subtitles.py     # POST /subtitles/fetch, GET /subtitles/download
│   │   ├── jobs.py          # GET /jobs, GET /jobs/stream/all (SSE)
│   │   └── settings_route.py # GET/POST /settings
│   └── services/
│       ├── subdl.py         # SubDL API client
│       ├── opensubtitles.py # OpenSubtitles REST API client (JWT cached per session)
│       ├── imdb.py          # TVmaze API wrapper (episode lookup by IMDB ID, no key needed)
│       ├── translation.py   # llm-subtrans + Ollama integration
│       └── env_manager.py   # .env read/write for Settings UI
├── web/
│   ├── index.html           # Single-page UI
│   └── static/
│       ├── app.js           # Vanilla JS, tab nav, SSE job stream
│       └── style.css
├── data/                    # Created on first run, not committed
│   ├── subtitles/           # Downloaded and translated SRTs
│   └── jobs/                # Translation job state (JSON)
├── .env.example             # Template — copy to .env and fill in keys
├── requirements.txt         # Loose version ranges (for development)
├── requirements-frozen.txt  # Pinned lockfile (for fast installs on other machines)
└── run.py                   # Uvicorn entry point
```

Translation progress streams to the browser via [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) so the Jobs tab updates in real time without polling.

---

## License

MIT
