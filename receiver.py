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
    # Split the SDP string into individual lines.
    lines = sdp.splitlines()
    new_lines = []
    # Loop over every line in the SDP.
    for line in lines:
        # If the line mentions "video/rtx" or "apt=", skip it.
        if "video/rtx" in line or "apt=" in line:
            print(f"[DEBUG] Filtering out line: {line}")
            continue
        # Otherwise, keep the line.
        new_lines.append(line)
    # Reassemble the SDP from the filtered lines.
    filtered_sdp = "\r\n".join(new_lines)
    print("[DEBUG] Finished SDP filtering.")
    return filtered_sdp

async def run(pc, signaling_uri, room_id):
    print(f"[DEBUG] Attempting to connect to signaling server at {signaling_uri}, room {room_id}...")
    try:
        # Connect to the signaling server WebSocket endpoint.
        async with websockets.connect(f"{signaling_uri}/ws/{room_id}") as websocket:
            print("[DEBUG] Successfully connected to signaling server.")
            
            print("[DEBUG] Waiting for WebRTC offer message...")
            # Wait for the incoming SDP offer.
            offer_msg = await websocket.recv()
            print(f"[DEBUG] Raw offer message received (first 100 chars): {offer_msg[:100]}...")
            # Parse the JSON message.
            data = json.loads(offer_msg)

            # Check if the message type is 'offer'.
            if data.get("type") != "offer":
                print(f"[ERROR] Expected offer message but received: {data}")
                return

            print("[DEBUG] Received WebRTC offer. Beginning SDP filtering process...")
            # Remove RTX lines from the SDP.
            filtered_sdp = remove_rtx_from_sdp(data["sdp"])
            print("[DEBUG] Filtered SDP (first 200 chars):", filtered_sdp[:200])
            # Create an RTCSessionDescription object using the filtered SDP.
            offer = RTCSessionDescription(sdp=filtered_sdp, type=data["type"])
            print("[DEBUG] Setting remote description with filtered SDP...")
            # Set the remote description for the WebRTC connection.
            await pc.setRemoteDescription(offer)
            print("[DEBUG] Remote description set successfully.")

            print("[DEBUG] Creating WebRTC answer...")
            # Create an answer based on the offer.
            answer = await pc.createAnswer()
            print("[DEBUG] Answer created. Setting local description...")
            # Set the local description for the connection.
            await pc.setLocalDescription(answer)
            print("[DEBUG] Local description set successfully.")

            print("[DEBUG] Sending WebRTC answer back to signaling server...")
            # Prepare the answer payload as a JSON string.
            answer_payload = json.dumps({"type": "answer", "sdp": pc.localDescription.sdp})
            await websocket.send(answer_payload)
            print(f"[DEBUG] Answer sent (first 100 chars): {answer_payload[:100]}...")

            print("[DEBUG] WebRTC connection established. Waiting for video track...")

            @pc.on("track")
            def on_track(track):
                print(f"[DEBUG] Track event fired. Track kind: {track.kind}")
                if track.kind == "video":
                    print("[DEBUG] Video track detected! Starting video display in a separate thread...")
                    
                    def run_display():
                        # Create a named window (this can help force OpenCV to update properly)
                        cv2.namedWindow("Remote Desktop", cv2.WINDOW_NORMAL)
                        frame_count = 0
                        while True:
                            try:
                                # Use run_coroutine_threadsafe to get the next video frame from the async track.
                                future = asyncio.run_coroutine_threadsafe(track.recv(), global_loop)
                                frame = future.result(timeout=5)  # wait up to 5 seconds for a frame
                                frame_count += 1
                                print(f"[DEBUG] (Thread) Received video frame #{frame_count}")
                                # Convert the frame to a NumPy array that OpenCV can use.
                                img = frame.to_ndarray(format="bgr24")
                                cv2.imshow("Remote Desktop", img)
                                # Process GUI events with a short delay.
                                if cv2.waitKey(1) & 0xFF == ord('q'):
                                    print("[DEBUG] (Thread) User pressed 'q'. Exiting video display loop.")
                                    break
                            except Exception as e:
                                print(f"[ERROR] (Thread) Exception while processing video frame: {e}")
                                break
                        print("[DEBUG] (Thread) Exiting video display thread. Destroying OpenCV windows.")
                        cv2.destroyAllWindows()

                    # Start the display thread.
                    t = threading.Thread(target=run_display, daemon=True)
                    t.start()
                else:
                    print(f"[DEBUG] Non-video track received: {track.kind}")

            print("[DEBUG] Entering indefinite wait state for further events.")
            # Keep the connection alive indefinitely.
            await asyncio.Future()

    except Exception as e:
        print(f"[ERROR] Exception occurred in run(): {e}")

if __name__ == "__main__":
    print("[DEBUG] Starting receiver script...")

    # Set up command-line argument parsing.
    parser = argparse.ArgumentParser(description="Screen Share Receiver")
    parser.add_argument("--signaling", type=str, default="ws://localhost:8000",
                        help="WebSocket signaling server URL (e.g., ws://localhost:8000)")
    parser.add_argument("--room", type=str, default="testroom",
                        help="Room ID for pairing sender and receiver")
    args = parser.parse_args()
    print("[DEBUG] Parsed arguments:", args)

    # Create a new RTCPeerConnection for handling WebRTC.
    pc = RTCPeerConnection()
    print("[DEBUG] Created RTCPeerConnection.")

    # Try to get the current running event loop; if none, create one.
    try:
        loop = asyncio.get_running_loop()
        print("[DEBUG] Using existing event loop.")
    except RuntimeError:
        print("[DEBUG] No running event loop found. Creating a new event loop.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Assign the main event loop to the global variable so that the display thread can use it.
    global_loop = loop

    try:
        # Run the receiver's main async function until it completes.
        print("[DEBUG] Running async event loop for receiver...")
        loop.run_until_complete(run(pc, args.signaling, args.room))
    except KeyboardInterrupt:
        print("[DEBUG] Receiver script interrupted by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"[ERROR] Unexpected error in main execution: {e}")
