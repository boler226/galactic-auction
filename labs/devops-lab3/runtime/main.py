# DVO-L3-7F2A91
"""Lab entry point: identify the image and serving pod without changing the app."""
import os
import socket

from app.main import app

VERSION = os.environ.get("APP_VERSION", "unknown")
app.version = VERSION


@app.middleware("http")
async def identify_replica(request, call_next):
    response = await call_next(request)
    response.headers["X-App-Version"] = VERSION
    response.headers["X-Pod-Name"] = socket.gethostname()
    return response


@app.get("/lab/info", tags=["lab"])
async def lab_info():
    return {"version": VERSION, "pod": socket.gethostname()}
