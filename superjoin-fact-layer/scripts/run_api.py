import sys
from pathlib import Path
import uvicorn

# Add src to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

if __name__ == "__main__":
    uvicorn.run("superjoin.api.main:app", host="127.0.0.1", port=8000, reload=True)
