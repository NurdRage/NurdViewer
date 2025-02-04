import asyncio
import argparse
import json
import cv2
from aiortc import RTCPeerConnection, RTCSessionDescription
import websockets

# This function removes unwanted RTX lines from the SDP,
# because our aiortc library doesn't support the RTX codec.
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

# The main function to run the receiver.
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

            # Set up an event handler for when a track is received.
            @pc.on("track")
            def on_track(track):
                print(f"[DEBUG] Track event fired. Track kind: {track.kind}")
                if track.kind == "video":
                    print("[DEBUG] Video track detected! Starting video display coroutine...")

                    # This asynchronous function will display the incoming video frames.
                    async def display_video():
                        frame_count = 0  # Counter to track number of frames received.
                        while True:
                            try:
                                # Wait for the next video frame from the track.
                                frame = await track.recv()
                                frame_count += 1
                                print(f"[DEBUG] Received video frame #{frame_count}")
                                # Convert the frame to a NumPy array that OpenCV can use.
                                img = frame.to_ndarray(format="bgr24")
                                # Display the image in a window titled "Remote Desktop".
                                cv2.imshow("Remote Desktop", img)
                                # Call cv2.waitKey to process GUI events (1 millisecond delay).
                                if cv2.waitKey(1) & 0xFF == ord('q'):
                                    print("[DEBUG] User pressed 'q'. Exiting video display loop.")
                                    break
                            except Exception as e:
                                print(f"[ERROR] Exception while processing video frame: {e}")
                                break
                        # Once the loop is done, destroy the OpenCV window.
                        print("[DEBUG] Exiting video display coroutine. Destroying OpenCV windows.")
                        cv2.destroyAllWindows()
                    
                    # Schedule the display_video() coroutine to run concurrently.
                    asyncio.ensure_future(display_video())
                else:
                    # For non-video tracks, simply log their receipt.
                    print(f"[DEBUG] Non-video track received: {track.kind}")

            # Keep the connection alive indefinitely by waiting on a never-ending future.
            print("[DEBUG] Entering indefinite wait state for further events.")
            await asyncio.Future()

    except Exception as e:
        print(f"[ERROR] Exception occurred in run(): {e}")

# The entry point for the receiver script.
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

    # Try to get the currently running asyncio event loop.
    try:
        loop = asyncio.get_running_loop()
        print("[DEBUG] Using existing event loop.")
    except RuntimeError:
        print("[DEBUG] No running event loop found. Creating a new event loop.")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        # Run the receiver's main async function until it completes (which it won't unless interrupted).
        print("[DEBUG] Running async event loop for receiver...")
        loop.run_until_complete(run(pc, args.signaling, args.room))
    except KeyboardInterrupt:
        print("[DEBUG] Receiver script interrupted by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"[ERROR] Unexpected error in main execution: {e}")
