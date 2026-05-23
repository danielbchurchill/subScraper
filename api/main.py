from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import shows, subtitles, jobs
from api.routes.settings_route import router as settings_router

app = FastAPI(title="SubScraper", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(shows.router)
app.include_router(subtitles.router)
app.include_router(jobs.router)
app.include_router(settings_router)

_WEB = Path(__file__).parent.parent / "web"

app.mount("/static", StaticFiles(directory=str(_WEB / "static")), name="static")


@app.get("/")
async def index():
    return FileResponse(str(_WEB / "index.html"))
