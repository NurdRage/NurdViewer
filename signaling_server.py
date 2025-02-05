#!/usr/bin/env python3
import os
import asyncio
import websockets
from log_config import configure_logging

logger = configure_logging(__name__)
logger.debug("Signaling server module loaded.")

ROOMS = {}

async def handler(websocket, path=None):
    if path is None:
        try:
            path = websocket.path
        except AttributeError:
            path = "/"
    room_id = path.strip("/").split("/")[-1]
    logger.debug("New connection attempt to room: %s", room_id)
    if room_id not in ROOMS:
        ROOMS[room_id] = set()
        logger.debug("Created new room entry for: %s", room_id)
    ROOMS[room_id].add(websocket)
    logger.debug("Room %s now has %d connection(s).", room_id, len(ROOMS[room_id]))
    try:
        async for message in websocket:
            logger.debug("Received message in room %s (first 100 chars): %s", room_id, message[:100])
            for peer in ROOMS[room_id]:
                if peer != websocket:
                    logger.debug("Relaying message to peer in room %s", room_id)
                    await peer.send(message)
            logger.debug("Finished relaying message in room %s.", room_id)
    except Exception as e:
        logger.error("Error in handler for room %s: %s", room_id, e)
    finally:
        if websocket in ROOMS[room_id]:
            ROOMS[room_id].remove(websocket)
        logger.debug("Connection closed for room %s. Current connections: %d", room_id, len(ROOMS[room_id]))

async def main():
    host = "0.0.0.0"
    port = 8000
    logger.debug("Starting signaling server on ws://%s:%d...", host, port)
    async with websockets.serve(handler, host, port):
        logger.debug("Signaling server started successfully.")
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Signaling server shut down due to KeyboardInterrupt.")
    except Exception as e:
        logger.error("Unexpected error in signaling server: %s", e)
