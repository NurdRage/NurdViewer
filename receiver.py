#!/usr/bin/env python3
import os
import asyncio
import argparse
import json
import logging
import logging.handlers
import threading  # (May be used for future enhancements)
import cv2       # (Optional: if you later want to process or display frames)
from aiortc import RTCPeerConnection, RTCSessionDescription
import websockets

from log_config import configure_logging
from video_consumer import consume_video  # <--- Our new modular consumer

logger = configure_logging(__name__)
logger.debug("Receiver module loaded.")

def remove_rtx_from_sdp(sdp: str) -> str:
    logger.debug("Starting SDP filtering for RTX lines.")
    lines = sdp.splitlines()
    new_lines = []
    for line in lines:
        if "video/rtx" in line or "apt=" in line:
            logger.debug("Filtering out line: %s", line)
            continue
        new_lines.append(line)
    filtered_sdp = "\r\n".join(new_lines)
    logger.debug("Finished SDP filtering. Filtered SDP length: %d characters.", len(filtered_sdp))
    return filtered_sdp

async def run(pc, signaling_uri, room_id):
    logger.debug("Attempting to connect to signaling server at %s/ws/%s", signaling_uri, room_id)
    async with websockets.connect(f"{signaling_uri}/ws/{room_id}") as websocket:
        logger.debug("Successfully connected to signaling server.")
        logger.debug("Waiting for WebRTC offer message...")

        offer_msg = await websocket.recv()
        logger.debug("Raw offer message received (first 100 chars): %s", offer_msg[:100])
        try:
            data = json.loads(offer_msg)
            logger.debug("Offer message successfully parsed as JSON.")
        except Exception as e:
            logger.error("Failed to parse offer message as JSON: %s", e)
            return

        if data.get("type") != "offer":
            logger.error("Expected offer message but received: %s", data)
            return

        logger.debug("Received WebRTC offer. Beginning SDP filtering process...")
        filtered_sdp = remove_rtx_from_sdp(data["sdp"])
        logger.debug("Filtered SDP (first 200 chars): %s", filtered_sdp[:200])
        offer = RTCSessionDescription(sdp=filtered_sdp, type=data["type"])
        logger.debug("Setting remote description with filtered SDP...")

        # -------------------------------------
        # **Add a forced recvonly transceiver** before applying the remote desc.
        logger.debug("Adding forced recvonly transceiver for video on the receiver side.")
        trans = pc.addTransceiver("video", direction="recvonly")
        logger.debug("Created transceiver: %s", trans)
        # -------------------------------------

        await pc.setRemoteDescription(offer)
        logger.debug("Remote description set successfully.")

        logger.debug("Creating WebRTC answer...")
        answer = await pc.createAnswer()
        logger.debug("Answer created. Setting local description...")
        await pc.setLocalDescription(answer)
        logger.debug("Local description set successfully.")

        logger.debug("Sending WebRTC answer back to signaling server...")
        answer_payload = json.dumps({"type": "answer", "sdp": pc.localDescription.sdp})
        await websocket.send(answer_payload)
        logger.debug("Answer sent (first 100 chars): %s", answer_payload[:100])

        @pc.on("track")
        def on_track(track):
            logger.debug("Receiver got track of kind=%s", track.kind)
            if track.kind == "video":
                logger.debug("Launching video consumer for track.")
                logger.debug("About to call consume_video for track: %s", track)
                asyncio.ensure_future(consume_video(track))

        @pc.on("iceconnectionstatechange")
        def on_ice_state_change():
            logger.debug("ICE connection state changed to %s", pc.iceConnectionState)

        logger.debug("WebRTC connection established. Waiting for video track...")
        await asyncio.Future()  # Keep running indefinitely

def main():
    parser = argparse.ArgumentParser(description="Receiver for WebRTC Screen Share")
    parser.add_argument("--signaling", required=True, help="Signaling server URI")
    parser.add_argument("--room", required=True, help="Room ID")
    args = parser.parse_args()

    logger.debug("Starting receiver script...")
    logger.debug("Parsed arguments: %s", args)

    pc = RTCPeerConnection()
    logger.debug("Created RTCPeerConnection.")

    try:
        asyncio.run(run(pc, args.signaling, args.room))
    except KeyboardInterrupt:
        logger.info("Receiver shutting down due to KeyboardInterrupt.")
    except Exception as e:
        logger.error("Unexpected error in receiver: %s", e)

if __name__ == '__main__':
    main()
