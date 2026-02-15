"""
Server — FastAPI app that serves the custom web UI and handles WebRTC signaling.

Usage:
  python server.py
  Then open http://localhost:7860 in your browser
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import uvicorn

from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection

load_dotenv(override=True)

try:
    logger.remove(0)
except ValueError:
    pass
logger.add(sys.stderr, level="DEBUG")

app = FastAPI()

# Serve static files (our custom UI)
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    """Serve the main page."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/offer")
async def offer(request: Request):
    """Handle WebRTC offer — create a bot session for each connection."""
    try:
        body = await request.json()
        sdp = body.get("sdp")
        sdp_type = body.get("type")
        logger.debug(f"Received offer: {sdp_type}")
        logger.debug(f"Received offer: {sdp_type}")
        # logger.debug(f"SDP: {sdp}") # Uncomment for full dump if needed

        if not sdp or not sdp_type:
            return JSONResponse(
                {"error": "Missing sdp or type in request"}, status_code=400
            )

        # Create the WebRTC connection
        webrtc_connection = SmallWebRTCConnection()

        # Import and run the bot
        from tutor_agent import run_bot

        from pipecat.runner.types import RunnerArguments
        from pipecat.transports.base_transport import TransportParams
        from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

        transport = SmallWebRTCTransport(
            webrtc_connection=webrtc_connection,
            params=TransportParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
            ),
        )

        # Start bot in background
        asyncio.create_task(run_bot(transport, handle_sigint=False))
        # Allow the bot to start and initialize transport before connecting
        await asyncio.sleep(1.0)

        # Negotiate WebRTC
        await webrtc_connection.initialize(sdp, sdp_type)
        await webrtc_connection.connect()
        answer = webrtc_connection.get_answer()

        return JSONResponse({"sdp": answer["sdp"], "type": answer["type"]})

    except Exception as e:
        logger.exception(f"Error in /api/offer: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    logger.info(f"Starting server at http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
