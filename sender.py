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

# Helper function to update debug logs on the same line.
def log_same_line(message: str):
    sys.stdout.write("\r" + message)
    sys.stdout.flush()

# ICE connection state logging callback.
def register_ice_callback(pc: RTCPeerConnection):
    @pc.on("iceconnectionstatechange")
    def on_ice_state_change():
        print(f"[DEBUG] ICE connection state changed to {pc.iceConnectionState}")

# This class is a custom VideoStreamTrack that captures the screen.
class ScreenShareTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        print("[DEBUG] Initializing screen capture...")
        self.sct = mss()
        self.monitor = self.sct.monitors[1]
        self.kind = "video"
        print(f"[DEBUG] Screen capture initialized. Monitor info: {self.monitor}")

    async def recv(self):
        # Update the debug log on the same line instead of printing new ones.
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
    print(f"[DEBUG] Connecting to signaling server at {signaling_uri}, room {room_id}...")
    try:
        async with websockets.connect(f"{signaling_uri}/ws/{room_id}") as websocket:
            print("[DEBUG] Connected to signaling server.")

            # Register ICE callback.
            register_ice_callback(pc)

            track = ScreenShareTrack()
            print("[DEBUG] Adding video track to WebRTC connection...")
            pc.addTrack(track)
            print("[DEBUG] Video track added successfully.")

            @pc.on("negotiationneeded")
            async def on_negotiationneeded():
                print("[DEBUG] Negotiation needed triggered.")
                try:
                    offer = await pc.createOffer()
                    print(f"[DEBUG] Offer created. SDP (first 200 chars): {offer.sdp[:200]}...")
                    await pc.setLocalDescription(offer)
                    print("[DEBUG] Local description set successfully.")
                    offer_payload = json.dumps({"type": "offer", "sdp": pc.localDescription.sdp})
                    print(f"[DEBUG] Sending offer payload (first 100 chars): {offer_payload[:100]}...")
                    await websocket.send(offer_payload)
                    print("[DEBUG] Offer sent to signaling server.")
                except Exception as e:
                    print(f"[ERROR] Exception during negotiation: {e}")

            print("[DEBUG] Triggering initial negotiation...")
            await on_negotiationneeded()

            async for message in websocket:
                print(f"[DEBUG] Message received from signaling server (first 100 chars): {message[:100]}...")
                try:
                    data = json.loads(message)
                    if data.get("type") == "answer":
                        print("[DEBUG] Answer received from signaling server.")
                        answer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                        await pc.setRemoteDescription(answer)
                        print("[DEBUG] Remote description set. WebRTC connection established.")
                        break
                except json.JSONDecodeError:
                    print("[ERROR] Received invalid JSON from signaling server.")
                except Exception as e:
                    print(f"[ERROR] Exception processing signaling message: {e}")

            print("[DEBUG] Entering indefinite wait for video stream...")
            await asyncio.Future()

    except Exception as e:
        print(f"[ERROR] Exception in WebSocket/WebRTC connection: {e}")

if __name__ == "__main__":
    print("[DEBUG] Starting sender script...")
    parser = argparse.ArgumentParser(description="Screen Share Sender")
    parser.add_argument("--signaling", type=str, default="ws://localhost:8000",
                        help="WebSocket signaling server URL (e.g., ws://localhost:8000)")
    parser.add_argument("--room", type=str, default="testroom",
                        help="Room ID for pairing sender and receiver")
    args = parser.parse_args()
    print("[DEBUG] Parsed arguments:", args)

    pc = RTCPeerConnection()
    print("[DEBUG] Created RTCPeerConnection.")

    try:
        loop = asyncio.get_running_loop()
        print("[DEBUG] Using existing event loop.")
    except RuntimeError:
        print("[DEBUG] No running event loop found. Creating a new event loop.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        print("[DEBUG] Running async event loop for sender...")
        loop.run_until_complete(run(pc, args.signaling, args.room))
    except KeyboardInterrupt:
        print("[DEBUG] Sender script interrupted by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"[ERROR] Unexpected error in main execution: {e}")
