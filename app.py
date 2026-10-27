"""DialAgent web endpoint (FastAPI skeleton, Day-1 slice).

POST /read with an image file -> the same frozen agent loop as reader.py:
reading + full trace with per-tool-call latency. GET / serves the static
frontend. No model calls, no paid services, no secrets.
"""

import os

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from reader import read_gauge

app = FastAPI(title="DialAgent")
HERE = os.path.dirname(os.path.abspath(__file__))


@app.get("/health")
def health():
    return {"status": "ok", "service": "dialagent"}


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


@app.post("/read")
async def read(image: UploadFile = File(...)):
    data = np.frombuffer(await image.read(), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse(
            {"error": "could not decode image"}, status_code=400)
    reading, trace = read_gauge(img)
    return {"reading": reading, "trace": trace}
