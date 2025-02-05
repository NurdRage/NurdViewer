#!/usr/bin/env python3
import os
import asyncio
import websockets
from log_config import configure_logging

logger = configure_logging(__name__)

ROOMS = {}

async def handler(websocket, path):
    room_id = path.strip("/").split("/")[-1]
    logger.debug("New connection attempt to room: %s", room_id)
    if room_id not in ROOMS:
        ROOMS[room_id] = set()
        logger.debug("Created new room entry for: %s", room_id)
    ROOMS[room_id].add(websocket)
    logger.debug("Current number of connections in room %s: %d", room_id, len(ROOMS[room_id]))
    try:
        async for message in websocket:
            logger.debug("Received message in room %s: %s", room_id, message[:100])
            # Relay the message to all other connections in the same room
            for peer in ROOMS[room_id]:
                if peer != websocket:
                    await peer.send(message)
            logger.debug("Finished relaying message in room %s.", room_id)
    except Exception as e:
        logger.error("Error in handler: %s", e)
    finally:
        ROOMS[room_id].remove(websocket)
        logger.debug("Connection closed for room %s. Current connections: %d", room_id, len(ROOMS[room_id]))

async def main():
    host = "0.0.0.0"
    port = 8000
    logger.debug("Starting signaling server on ws://%s:%d...", host, port)
    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # run forever

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Signaling server shut down.")
