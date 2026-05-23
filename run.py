import sys

try:
    import uvicorn
except ModuleNotFoundError:
    print(
        "\nERROR: uvicorn is not installed in the current Python environment.\n"
        f"  Python in use: {sys.executable}\n\n"
        "Run the app via the start script instead:\n"
        "  macOS/Linux:  ./start.sh\n"
        "  Windows:      start.bat\n\n"
        "Or install dependencies manually into this Python:\n"
        f"  {sys.executable} -m pip install -r requirements-frozen.txt\n",
        file=sys.stderr,
    )
    sys.exit(1)

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
