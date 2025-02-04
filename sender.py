import asyncio
import argparse
import json
import cv2
import numpy as np
from mss import mss
from av import VideoFrame
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
import websockets

class ScreenShareTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        print("[DEBUG] Initializing screen capture...")
        self.sct = mss()
        self.monitor = self.sct.monitors[1]
        self.kind = "video"  # Explicitly mark as video track
        print("[DEBUG] Screen capture initialized.")

    async def recv(self):
        print("[DEBUG] Capturing screen frame...")
        pts, time_base = await self.next_timestamp()
        img = np.array(self.sct.grab(self.monitor))
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        print("[DEBUG] Frame captured and formatted.")
        return frame

async def run(pc, signaling_uri, room_id):
    print(f"[DEBUG] Connecting to signaling server at {signaling_uri}, room {room_id}...")

    try:
        async with websockets.connect(f"{signaling_uri}/ws/{room_id}") as websocket:
            print("[DEBUG] Connected to signaling server.")

            track = ScreenShareTrack()
            print("[DEBUG] Adding video track to WebRTC connection...")
            pc.addTrack(track)

            # Force WebRTC to renegotiate if necessary
            @pc.on("negotiationneeded")
            async def on_negotiationneeded():
                print("[DEBUG] WebRTC renegotiation triggered.")
                try:
                    offer = await pc.createOffer()
                    await pc.setLocalDescription(offer)
                    print(f"[DEBUG] WebRTC offer created:\n{offer.sdp[:200]}...")  # Log first 200 chars of SDP

                    print("[DEBUG] Sending offer to signaling server...")
                    await websocket.send(json.dumps({"type": "offer", "sdp": pc.localDescription.sdp}))
                except Exception as e:
                    print(f"[ERROR] Failed to create/send offer: {e}")

            # Ensure offer is sent immediately
            print("[DEBUG] Triggering initial negotiation...")
            await on_negotiationneeded()

            async for message in websocket:
                print(f"[DEBUG] Message received from signaling server: {message[:100]}...")  # Log first 100 chars
                try:
                    data = json.loads(message)
                    if data["type"] == "answer":
                        print("[DEBUG] Received answer from server.")
                        answer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                        await pc.setRemoteDescription(answer)
                        print("[DEBUG] WebRTC connection established.")
                        break
                except json.JSONDecodeError:
                    print("[ERROR] Received invalid JSON from signaling server.")
                except Exception as e:
                    print(f"[ERROR] Error processing message from signaling server: {e}")

            print("[DEBUG] Waiting indefinitely for video stream...")
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

    pc = RTCPeerConnection()

    try:
        loop = asyncio.get_running_loop()
        print("[DEBUG] Using existing event loop.")
    except RuntimeError:
        print("[DEBUG] Creating a new event loop.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        print("[DEBUG] Running async event loop.")
        loop.run_until_complete(run(pc, args.signaling, args.room))
    except KeyboardInterrupt:
        print("[DEBUG] Sender script interrupted.")
    except Exception as e:
        print(f"[ERROR] Unexpected error in main execution: {e}")
