import asyncio
import argparse
import json
import cv2
import threading
from aiortc import RTCPeerConnection, RTCSessionDescription
import websockets

# Global variable to hold the main event loop reference.
global_loop = None

def remove_rtx_from_sdp(sdp: str) -> str:
    """
    Remove RTX-related lines from the SDP to prevent aiortc from trying to create
    a decoder for the unsupported MIME type 'video/rtx'.
    """
    print("[DEBUG] Starting SDP filtering for RTX lines.")
    lines = sdp.splitlines()
    new_lines = []
    for line in lines:
        if "video/rtx" in line or "apt=" in line:
            print(f"[DEBUG] Filtering out line: {line}")
            continue
        new_lines.append(line)
    filtered_sdp = "\r\n".join(new_lines)
    print("[DEBUG] Finished SDP filtering.")
    return filtered_sdp

async def run(pc, signaling_uri, room_id):
    print(f"[DEBUG] Attempting to connect to signaling server at {signaling_uri}, room {room_id}...")
    try:
        async with websockets.connect(f"{signaling_uri}/ws/{room_id}") as websocket:
            print("[DEBUG] Successfully connected to signaling server.")
            
            print("[DEBUG] Waiting for WebRTC offer message...")
            offer_msg = await websocket.recv()
            print(f"[DEBUG] Raw offer message received (first 100 chars): {offer_msg[:100]}...")
            data = json.loads(offer_msg)
            if data.get("type") != "offer":
                print(f"[ERROR] Expected offer message but received: {data}")
                return

            print("[DEBUG] Received WebRTC offer. Beginning SDP filtering process...")
            filtered_sdp = remove_rtx_from_sdp(data["sdp"])
            print("[DEBUG] Filtered SDP (first 200 chars):", filtered_sdp[:200])
            offer = RTCSessionDescription(sdp=filtered_sdp, type=data["type"])
            print("[DEBUG] Setting remote description with filtered SDP...")
            await pc.setRemoteDescription(offer)
            print("[DEBUG] Remote description set successfully.")

            print("[DEBUG] Creating WebRTC answer...")
            answer = await pc.createAnswer()
            print("[DEBUG] Answer created. Setting local description...")
            await pc.setLocalDescription(answer)
            print("[DEBUG] Local description set successfully.")

            print("[DEBUG] Sending WebRTC answer back to signaling server...")
            answer_payload = json.dumps({"type": "answer", "sdp": pc.localDescription.sdp})
            await websocket.send(answer_payload)
            print(f"[DEBUG] Answer sent (first 100 chars): {answer_payload[:100]}...")

            # ICE connection state logging
            @pc.on("iceconnectionstatechange")
            def on_ice_state_change():
                print(f"[DEBUG] ICE connection state changed to {pc.iceConnectionState}")

            print("[DEBUG] WebRTC connection established. Waiting for video track...")

            @pc.on("track")
            def on_track(track):
                print(f"[DEBUG] Track event fired. Track kind: {track.kind}")
                if track.kind == "video":
                    print("[DEBUG] Video track detected! Starting video display in a separate thread...")
                    
                    def run_display():
                        cv2.namedWindow("Remote Desktop", cv2.WINDOW_NORMAL)
                        frame_count = 0
                        while True:
                            try:
                                future = asyncio.run_coroutine_threadsafe(track.recv(), global_loop)
                                frame = future.result(timeout=5)
                                frame_count += 1
                                print(f"[DEBUG] (Thread) Received video frame #{frame_count}")
                                img = frame.to_ndarray(format="bgr24")
                                cv2.imshow("Remote Desktop", img)
                                if cv2.waitKey(1) & 0xFF == ord('q'):
                                    print("[DEBUG] (Thread) User pressed 'q'. Exiting video display loop.")
                                    break
                            except Exception as e:
                                print(f"[ERROR] (Thread) Exception while processing video frame: {e}")
                                break
                        print("[DEBUG] (Thread) Exiting video display thread. Destroying OpenCV windows.")
                        cv2.destroyAllWindows()
                    t = threading.Thread(target=run_display, daemon=True)
                    t.start()
                else:
                    print(f"[DEBUG] Non-video track received: {track.kind}")

            print("[DEBUG] Entering indefinite wait state for further events.")
            await asyncio.Future()

    except Exception as e:
        print(f"[ERROR] Exception occurred in run(): {e}")

if __name__ == "__main__":
    print("[DEBUG] Starting receiver script...")
    parser = argparse.ArgumentParser(description="Screen Share Receiver")
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

    global_loop = loop

    try:
        print("[DEBUG] Running async event loop for receiver...")
        loop.run_until_complete(run(pc, args.signaling, args.room))
    except KeyboardInterrupt:
        print("[DEBUG] Receiver script interrupted by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"[ERROR] Unexpected error in main execution: {e}")
