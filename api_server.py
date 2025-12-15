# api_server.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

# 👇  Import the backend class we just added.
# If you kept the name exactly as “earth_backend_fixed.py”, use this import:
from earth_backend_fixed import PhaseCoherentEarthBackend
# (If you renamed the file to earth_backend.py, change the line to:
# from earth_backend import PhaseCoherentEarthBackend)

app = FastAPI(title="Phase‑Coherent Earth Monitor API")

# Allow any origin while you’re developing.
# In production replace ["*"] with your actual domain(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # e.g. ["https://your‑site.com"]
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Create ONE backend instance that lives for the life of the process.
backend = PhaseCoherentEarthBackend()

@app.get("/dashboard")
def get_dashboard():
    """
    Return the latest JSON payload for the front‑end.
    Uncomment the two lines below if you want a fresh pull on every request.
    """
    # backend.fetch_iers_data()
    # backend.fetch_grace_data()
    data = backend.generate_dashboard_update()
    return data

if __name__ == "__main__":
    # Run locally for testing:
    #   uvicorn api_server:app --reload --port 8000
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
