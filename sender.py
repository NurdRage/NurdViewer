import asyncio
import argparse
import json
import cv2
import numpy as np
import sys  # For same-line logging
from mss import mss
from av import VideoFrame
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
import websockets
import logging
import logging.handlers
import os

# Logging configuration
SCRIPT_NAME = os.path.splitext(os.path.basename(__file__))[0]
LOCAL_LOG_FILENAME = f"{SCRIPT_NAME}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOCAL_LOG_FILENAME, mode='w'),
        logging.StreamHandler()
    ]
)
central_ip = os.environ.get("CENTRAL_LOG_IP", "127.0.0.1")
logging.debug(f"Using central logging IP: {central_ip}")
central_handler = logging.handlers.SocketHandler(central_ip, 9020)
logging.getLogger().addHandler(central_handler)

# Helper function for same-line logging.
def log_same_line(message: str):
    sys.stdout.write("\r" + message)
    sys.stdout.flush()

def register_ice_callback(pc: RTCPeerConnection):
    @pc.on("iceconnectionstatechange")
    def on_ice_state_change():
        logging.debug(f"ICE connection state changed to {pc.iceConnectionState}")

# This class is a custom VideoStreamTrack that captures the screen.
class ScreenShareTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        logging.debug("Initializing screen capture...")
        self.sct = mss()
        self.monitor = self.sct.monitors[1]
        self.kind = "video"
        logging.debug(f"Screen capture initialized. Monitor info: {self.monitor}")

    async def recv(self):
        log_same_line("[DEBUG] Starting to capture a screen frame...")
        pts, time_base = await self.next_timestamp()
        log_same_line(f"[DEBUG] Obtained timestamp: pts={pts}, time_base={time_base}")
        img = np.array(self.sct.grab(self.monitor))
        log_same_line(f"[DEBUG] Raw image captured. Shape: {img.shape}")
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        log_same_line("[DEBUG] Frame processed and formatted. Returning frame.")
        return frame

async def run(pc, signaling_uri, room_id):
    logging.debug(f"Connecting to signaling server at {signaling_uri}, room {room_id}...")
    try:
        async with websockets.connect(f"{signaling_uri}/ws/{room_id}") as websocket:
            logging.debug("Connected to signaling server.")

            # Register ICE callback.
            register_ice_callback(pc)

            track = ScreenShareTrack()
            logging.debug("Adding video track to WebRTC connection...")
            pc.addTrack(track)
            logging.debug("Video track added successfully.")

            @pc.on("negotiationneeded")
            async def on_negotiationneeded():
                logging.debug("Negotiation needed triggered.")
                try:
                    offer = await pc.createOffer()
                    logging.debug(f"Offer created. SDP (first 200 chars): {offer.sdp[:200]}...")
                    await pc.setLocalDescription(offer)
                    logging.debug("Local description set successfully.")
                    offer_payload = json.dumps({"type": "offer", "sdp": pc.localDescription.sdp})
                    logging.debug(f"Sending offer payload (first 100 chars): {offer_payload[:100]}...")
                    await websocket.send(offer_payload)
                    logging.debug("Offer sent to signaling server.")
                except Exception as e:
                    logging.error(f"Exception during negotiation: {e}")

            logging.debug("Triggering initial negotiation...")
            await on_negotiationneeded()

            async for message in websocket:
                logging.debug(f"Message received from signaling server (first 100 chars): {message[:100]}...")
                try:
                    data = json.loads(message)
                    if data.get("type") == "answer":
                        logging.debug("Answer received from signaling server.")
                        answer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                        await pc.setRemoteDescription(answer)
                        logging.debug("Remote description set. WebRTC connection established.")
                        break
                except json.JSONDecodeError:
                    logging.error("Received invalid JSON from signaling server.")
                except Exception as e:
                    logging.error(f"Exception processing signaling message: {e}")

            logging.debug("Entering indefinite wait for video stream...")
            await asyncio.Future()

    except Exception as e:
        logging.error(f"Exception in WebSocket/WebRTC connection: {e}")

if __name__ == "__main__":
    logging.debug("Starting sender script...")
    parser = argparse.ArgumentParser(description="Screen Share Sender")
    parser.add_argument("--signaling", type=str, default="ws://localhost:8000",
                        help="WebSocket signaling server URL (e.g., ws://localhost:8000)")
    parser.add_argument("--room", type=str, default="testroom",
                        help="Room ID for pairing sender and receiver")
    args = parser.parse_args()
    logging.debug(f"Parsed arguments: {args}")

    pc = RTCPeerConnection()
    logging.debug("Created RTCPeerConnection.")

    try:
        loop = asyncio.get_running_loop()
        logging.debug("Using existing event loop.")
    except RuntimeError:
        logging.debug("No running event loop found. Creating a new event loop.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        logging.debug("Running async event loop for sender...")
        loop.run_until_complete(run(pc, args.signaling, args.room))
    except KeyboardInterrupt:
        logging.debug("Sender script interrupted by user (KeyboardInterrupt).")
    except Exception as e:
        logging.error(f"Unexpected error in main execution: {e}")
