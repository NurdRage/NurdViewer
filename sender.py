#!/usr/bin/env python3
import os
import asyncio
import json
import websockets
from log_config import configure_logging
from aiortc import RTCPeerConnection, RTCSessionDescription
from screen_track import ScreenShareTrack  # new component for screen capture

logger = configure_logging(__name__)

async def on_negotiationneeded(pc, websocket):
    # Create an offer and set it as the local description.
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    logger.debug("Offer created. SDP (first 200 chars): %s", str(offer)[:200])

    # Send the offer via signaling.
    payload = json.dumps({"type": "offer", "sdp": pc.localDescription.sdp})
    await websocket.send(payload)
    logger.debug("Offer sent to signaling server.")

async def run(pc, signaling_uri, room_id):
    async with websockets.connect(f"{signaling_uri}/ws/{room_id}") as websocket:
        logger.debug("Connected to signaling server.")

        # Initialize the screen capture (this could be expanded to select monitors, etc.)
        logger.debug("Initializing screen capture...")
        monitor_info = {'left': 0, 'top': 0, 'width': 1920, 'height': 1080}
        logger.debug("Screen capture initialized. Monitor info: %s", monitor_info)

        # Create and add the video track from our new screen capture module.
        video_track = ScreenShareTrack(monitor=monitor_info, frame_rate=15.0)
        pc.addTrack(video_track)
        logger.debug("Video track added successfully.")

        # Trigger the initial negotiation (offer -> answer exchange).
        logger.debug("Triggering initial negotiation...")
        await on_negotiationneeded(pc, websocket)
        logger.debug("Offer sent; waiting for answer...")

        # Wait for the "answer" message from the signaling server.
        # In a minimal broadcast server, each peer gets messages from the other side.
        while True:
            try:
                message = await websocket.recv()
            except websockets.ConnectionClosed:
                logger.error("WebSocket connection closed unexpectedly.")
                return

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                logger.error("Received non-JSON message on signaling channel.")
                continue

            if data.get("type") == "answer":
                logger.debug("Received answer. Setting remote description.")
                answer_sdp = data["sdp"]
                await pc.setRemoteDescription(RTCSessionDescription(sdp=answer_sdp, type="answer"))
                logger.debug("Remote description set. WebRTC handshake complete.")
                break
            else:
                logger.debug("Received non-answer message: %s", data)

        logger.debug("WebRTC connection established. Keeping sender alive...")
        # Keep the connection alive indefinitely.
        await asyncio.Future()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Sender")
    parser.add_argument("--signaling", required=True, help="Signaling server URI")
    parser.add_argument("--room", required=True, help="Room ID")
    args = parser.parse_args()
    logger.debug("Parsed arguments: %s", args)

    pc = RTCPeerConnection()
    logger.debug("Created RTCPeerConnection.")

    try:
        asyncio.run(run(pc, args.signaling, args.room))
    except KeyboardInterrupt:
        logger.info("Sender shutting down.")

if __name__ == '__main__':
    main()
