import asyncio
import argparse
import json
import cv2
from aiortc import RTCPeerConnection, RTCSessionDescription
import websockets

def remove_rtx_from_sdp(sdp: str) -> str:
    """
    Remove RTX-related lines from the SDP to prevent aiortc from trying to create
    a decoder for the unsupported MIME type 'video/rtx'.
    """
    lines = sdp.splitlines()
    new_lines = []
    for line in lines:
        # Skip lines that reference RTX or the 'apt' parameter used for RTX
        if "video/rtx" in line or "apt=" in line:
            continue
        new_lines.append(line)
    return "\r\n".join(new_lines)

async def run(pc, signaling_uri, room_id):
    print(f"[DEBUG] Connecting to signaling server at {signaling_uri}, room {room_id}...")

    try:
        async with websockets.connect(f"{signaling_uri}/ws/{room_id}") as websocket:
            print("[DEBUG] Connected to signaling server.")

            print("[DEBUG] Waiting for WebRTC offer...")
            offer_msg = await websocket.recv()
            data = json.loads(offer_msg)

            if data["type"] != "offer":
                print("[ERROR] Expected offer message but received:", data)
                return

            print("[DEBUG] Received WebRTC offer.")
            # Filter out RTX lines from the SDP before setting the remote description
            filtered_sdp = remove_rtx_from_sdp(data["sdp"])
            offer = RTCSessionDescription(sdp=filtered_sdp, type=data["type"])
            await pc.setRemoteDescription(offer)

            print("[DEBUG] Creating WebRTC answer...")
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            print("[DEBUG] Sending WebRTC answer to signaling server...")
            await websocket.send(json.dumps({"type": "answer", "sdp": pc.localDescription.sdp}))

            print("[DEBUG] WebRTC connection established. Waiting for video track...")

            @pc.on("track")
            def on_track(track):
                print(f"[DEBUG] Track received: {track.kind}")
                if track.kind == "video":
                    print("[DEBUG] Video track detected! Starting display...")
                    async def display_video():
                        while True:
                            try:
                                frame = await track.recv()
                                print("[DEBUG] Received a video frame")
                                img = frame.to_ndarray(format="bgr24")
                                cv2.imshow("Remote Desktop", img)
                                # cv2.waitKey is needed to process GUI events.
                                if cv2.waitKey(1) & 0xFF == ord('q'):
                                    print("[DEBUG] Video window closed by user.")
                                    break
                            except Exception as e:
                                print(f"[ERROR] Issue processing video frame: {e}")
                                break
                        cv2.destroyAllWindows()
                    # Schedule the video display coroutine
                    asyncio.ensure_future(display_video())

            # Keep the connection open indefinitely.
            await asyncio.Future()

    except Exception as e:
        print(f"[ERROR] Exception occurred in WebSocket connection: {e}")

if __name__ == "__main__":
    print("[DEBUG] Starting receiver script...")

    parser = argparse.ArgumentParser(description="Screen Share Receiver")
    parser.add_argument("--signaling", type=str, default="ws://localhost:8000",
                        help="WebSocket signaling server URL (e.g., ws://localhost:8000)")
    parser.add_argument("--room", type=str, default="testroom",
                        help="Room ID for pairing sender and receiver")
    args = parser.parse_args()

    print("[DEBUG] Arguments parsed.")

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
        print("[DEBUG] Receiver script interrupted.")
    except Exception as e:
        print(f"[ERROR] Unexpected error in main execution: {e}")
