import asyncio
import argparse
import json
import cv2
import threading
from aiortc import RTCPeerConnection, RTCSessionDescription
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

# Global variable to hold the main event loop reference.
global_loop = None

def remove_rtx_from_sdp(sdp: str) -> str:
    """
    Remove RTX-related lines from the SDP to prevent aiortc from trying to create
    a decoder for the unsupported MIME type 'video/rtx'.
    """
    logging.debug("Starting SDP filtering for RTX lines.")
    lines = sdp.splitlines()
    new_lines = []
    for line in lines:
        if "video/rtx" in line or "apt=" in line:
            logging.debug(f"Filtering out line: {line}")
            continue
        new_lines.append(line)
    filtered_sdp = "\r\n".join(new_lines)
    logging.debug("Finished SDP filtering.")
    return filtered_sdp

async def run(pc, signaling_uri, room_id):
    logging.debug(f"Attempting to connect to signaling server at {signaling_uri}, room {room_id}...")
    try:
        async with websockets.connect(f"{signaling_uri}/ws/{room_id}") as websocket:
            logging.debug("Successfully connected to signaling server.")
            
            logging.debug("Waiting for WebRTC offer message...")
            offer_msg = await websocket.recv()
            logging.debug(f"Raw offer message received (first 100 chars): {offer_msg[:100]}...")
            data = json.loads(offer_msg)
            if data.get("type") != "offer":
                logging.error(f"Expected offer message but received: {data}")
                return

            logging.debug("Received WebRTC offer. Beginning SDP filtering process...")
            filtered_sdp = remove_rtx_from_sdp(data["sdp"])
            logging.debug(f"Filtered SDP (first 200 chars): {filtered_sdp[:200]}")
            offer = RTCSessionDescription(sdp=filtered_sdp, type=data["type"])
            logging.debug("Setting remote description with filtered SDP...")
            await pc.setRemoteDescription(offer)
            logging.debug("Remote description set successfully.")

            logging.debug("Creating WebRTC answer...")
            answer = await pc.createAnswer()
            logging.debug("Answer created. Setting local description...")
            await pc.setLocalDescription(answer)
            logging.debug("Local description set successfully.")

            logging.debug("Sending WebRTC answer back to signaling server...")
            answer_payload = json.dumps({"type": "answer", "sdp": pc.localDescription.sdp})
            await websocket.send(answer_payload)
            logging.debug(f"Answer sent (first 100 chars): {answer_payload[:100]}...")

            @pc.on("iceconnectionstatechange")
            def on_ice_state_change():
                logging.debug(f"ICE connection state changed to {pc.iceConnectionState}")

            logging.debug("WebRTC connection established. Waiting for video track...")

            @pc.on("track")
            def on_track(track):
                logging.debug(f"Track event fired. Track kind: {track.kind}")
                if track.kind == "video":
                    logging.debug("Video track detected! Starting video display in a separate thread...")
                    
                    def run_display():
                        cv2.namedWindow("Remote Desktop", cv2.WINDOW_NORMAL)
                        frame_count = 0
                        while True:
                            try:
                                future = asyncio.run_coroutine_threadsafe(track.recv(), global_loop)
                                frame = future.result(timeout=5)
                                frame_count += 1
                                logging.debug(f"(Thread) Received video frame #{frame_count}")
                                img = frame.to_ndarray(format="bgr24")
                                cv2.imshow("Remote Desktop", img)
                                if cv2.waitKey(1) & 0xFF == ord('q'):
                                    logging.debug("(Thread) User pressed 'q'. Exiting video display loop.")
                                    break
                            except Exception as e:
                                logging.error(f"(Thread) Exception while processing video frame: {e}")
                                break
                        logging.debug("(Thread) Exiting video display thread. Destroying OpenCV windows.")
                        cv2.destroyAllWindows()

                    t = threading.Thread(target=run_display, daemon=True)
                    t.start()
                else:
                    logging.debug(f"Non-video track received: {track.kind}")

            logging.debug("Entering indefinite wait state for further events.")
            await asyncio.Future()

    except Exception as e:
        logging.error(f"Exception occurred in run(): {e}")

if __name__ == "__main__":
    logging.debug("Starting receiver script...")
    parser = argparse.ArgumentParser(description="Screen Share Receiver")
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

    global_loop = loop

    try:
        logging.debug("Running async event loop for receiver...")
        loop.run_until_complete(run(pc, args.signaling, args.room))
    except KeyboardInterrupt:
        logging.debug("Receiver script interrupted by user (KeyboardInterrupt).")
    except Exception as e:
        logging.error(f"Unexpected error in main execution: {e}")
