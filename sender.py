import asyncio
import argparse
import json
import cv2
import numpy as np
import sys  # Added for same-line logging
from mss import mss
from av import VideoFrame
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
import websockets

# Helper function for updating debug logs on the same line.
def log_same_line(message: str):
    sys.stdout.write("\r" + message)
    sys.stdout.flush()

# This class is a custom VideoStreamTrack that captures the screen.
class ScreenShareTrack(VideoStreamTrack):
    def __init__(self):
        # Call the parent class's initializer.
        super().__init__()
        print("[DEBUG] Initializing screen capture...")
        # Create an mss instance for screen capture.
        self.sct = mss()
        # Choose the primary monitor (index 1) for capturing.
        self.monitor = self.sct.monitors[1]
        # Mark this track as a video track.
        self.kind = "video"
        print(f"[DEBUG] Screen capture initialized. Monitor info: {self.monitor}")

    async def recv(self):
        # Instead of printing new lines for every frame, we update the same line.
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

# The main function to run the sender.
async def run(pc, signaling_uri, room_id):
    print(f"[DEBUG] Connecting to signaling server at {signaling_uri}, room {room_id}...")
    try:
        # Open a WebSocket connection to the signaling server for the given room.
        async with websockets.connect(f"{signaling_uri}/ws/{room_id}") as websocket:
            print("[DEBUG] Connected to signaling server.")

            # Create an instance of our custom screen capture track.
            track = ScreenShareTrack()
            print("[DEBUG] Adding video track to WebRTC connection...")
            # Add the video track to the RTCPeerConnection.
            pc.addTrack(track)
            print("[DEBUG] Video track added successfully.")

            # Define an event handler that is triggered when renegotiation is needed.
            @pc.on("negotiationneeded")
            async def on_negotiationneeded():
                print("[DEBUG] Negotiation needed triggered.")
                try:
                    # Create an SDP offer based on the current connection state.
                    offer = await pc.createOffer()
                    print(f"[DEBUG] Offer created. SDP (first 200 chars): {offer.sdp[:200]}...")
                    # Set the local description with the created offer.
                    await pc.setLocalDescription(offer)
                    print("[DEBUG] Local description set successfully.")
                    # Create a JSON payload containing the SDP offer.
                    offer_payload = json.dumps({"type": "offer", "sdp": pc.localDescription.sdp})
                    print(f"[DEBUG] Sending offer payload (first 100 chars): {offer_payload[:100]}...")
                    # Send the offer payload to the signaling server.
                    await websocket.send(offer_payload)
                    print("[DEBUG] Offer sent to signaling server.")
                except Exception as e:
                    print(f"[ERROR] Exception during negotiation: {e}")

            # Trigger the initial negotiation.
            print("[DEBUG] Triggering initial negotiation...")
            await on_negotiationneeded()

            # Listen for messages from the signaling server.
            async for message in websocket:
                print(f"[DEBUG] Message received from signaling server (first 100 chars): {message[:100]}...")
                try:
                    # Parse the incoming message from JSON.
                    data = json.loads(message)
                    if data.get("type") == "answer":
                        print("[DEBUG] Answer received from signaling server.")
                        # Create an RTCSessionDescription from the answer.
                        answer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                        # Set the remote description with the answer.
                        await pc.setRemoteDescription(answer)
                        print("[DEBUG] Remote description set. WebRTC connection established.")
                        # Exit the loop after processing the answer.
                        break
                except json.JSONDecodeError:
                    print("[ERROR] Received invalid JSON from signaling server.")
                except Exception as e:
                    print(f"[ERROR] Exception processing signaling message: {e}")

            print("[DEBUG] Entering indefinite wait for video stream...")
            # After the SDP exchange, wait indefinitely for video frames.
            await asyncio.Future()  # This never completes unless an error occurs.

    except Exception as e:
        print(f"[ERROR] Exception in WebSocket/WebRTC connection: {e}")

# The entry point for the sender script.
if __name__ == "__main__":
    print("[DEBUG] Starting sender script...")
    
    # Set up command-line argument parsing.
    parser = argparse.ArgumentParser(description="Screen Share Sender")
    parser.add_argument("--signaling", type=str, default="ws://localhost:8000",
                        help="WebSocket signaling server URL (e.g., ws://localhost:8000)")
    parser.add_argument("--room", type=str, default="testroom",
                        help="Room ID for pairing sender and receiver")
    args = parser.parse_args()
    print("[DEBUG] Parsed arguments:", args)

    # Create a new RTCPeerConnection for handling WebRTC.
    pc = RTCPeerConnection()
    print("[DEBUG] Created RTCPeerConnection.")

    # Try to obtain the current asyncio event loop; if none, create one.
    try:
        loop = asyncio.get_running_loop()
        print("[DEBUG] Using existing event loop.")
    except RuntimeError:
        print("[DEBUG] No running event loop found. Creating a new event loop.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        # Run the sender's main async function until it completes (which it won't unless interrupted).
        print("[DEBUG] Running async event loop for sender...")
        loop.run_until_complete(run(pc, args.signaling, args.room))
    except KeyboardInterrupt:
        print("[DEBUG] Sender script interrupted by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"[ERROR] Unexpected error in main execution: {e}")
