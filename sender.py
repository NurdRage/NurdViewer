#!/usr/bin/env python3
import os
import asyncio
import json
import websockets
from log_config import configure_logging
from aiortc import RTCPeerConnection, RTCSessionDescription
from screen_track import ScreenShareTrack  # new component for screen capture

logger = configure_logging(__name__)
logger.debug("Sender module loaded.")

async def on_negotiationneeded(pc, websocket):
    logger.debug("Negotiation needed; creating offer...")
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    logger.debug("Offer created and local description set. SDP (first 200 chars): %s", str(offer)[:200])
    logger.debug("Full local SDP (sender):\n%s", pc.localDescription.sdp)

    payload = json.dumps({"type": "offer", "sdp": pc.localDescription.sdp})
    logger.debug("Sending offer payload: %s", payload[:200])
    await websocket.send(payload)
    logger.debug("Offer sent to signaling server.")

async def run(pc, signaling_uri, room_id):
    logger.debug("Connecting to signaling server at %s/ws/%s", signaling_uri, room_id)
    async with websockets.connect(f"{signaling_uri}/ws/{room_id}") as websocket:
        logger.debug("Connected to signaling server.")

        logger.debug("Initializing screen capture...")
        monitor_info = {'left': 0, 'top': 0, 'width': 1920, 'height': 1080}
        logger.debug("Screen capture initialized. Monitor info: %s", monitor_info)

        video_track = ScreenShareTrack(monitor=monitor_info, frame_rate=15.0)
        logger.debug("ScreenShareTrack created. Replacing old pc.addTrack approach with a sendonly transceiver.")

        # Use the older aiortc signature: pass "video" as a positional arg, direction="sendonly"
        transceiver = pc.addTransceiver("video", direction="sendonly")
        logger.debug("Transceiver created with direction=sendonly.")
        transceiver.sender.replaceTrack(video_track)
        logger.debug("Track replaced in transceiver.sender successfully.")

        logger.debug("Triggering initial negotiation...")
        await on_negotiationneeded(pc, websocket)
        logger.debug("Offer sent; awaiting answer...")

        while True:
            try:
                message = await websocket.recv()
                logger.debug("Received message from signaling server: %s", message[:100])
            except websockets.ConnectionClosed:
                logger.error("WebSocket connection closed unexpectedly.")
                return

            try:
                data = json.loads(message)
                logger.debug("Parsed signaling message: %s", data)
            except json.JSONDecodeError:
                logger.error("Received non-JSON message on signaling channel: %s", message)
                continue

            if data.get("type") == "answer":
                logger.debug("Received answer. Setting remote description.")
                answer_sdp = data["sdp"]
                await pc.setRemoteDescription(RTCSessionDescription(sdp=answer_sdp, type="answer"))
                logger.debug("Remote description set. WebRTC handshake complete.")
                logger.debug("Final remote SDP (sender sees answer):\n%s", pc.remoteDescription.sdp)
                break
            else:
                logger.debug("Received non-answer message: %s", data)

        logger.debug("WebRTC connection established. Keeping sender alive...")
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
        logger.info("Sender shutting down due to KeyboardInterrupt.")
    except Exception as e:
        logger.error("Unexpected error in sender: %s", e)

if __name__ == '__main__':
    main()
