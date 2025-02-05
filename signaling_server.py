import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List
import logging
import logging.handlers
import os
from log_config import get_central_logging_ip

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

# Configure centralized logging if an IP is provided.
central_ip = get_central_logging_ip()
if central_ip:
    logging.debug(f"Using central logging IP: {central_ip}")
    central_handler = logging.handlers.SocketHandler(central_ip, 9020)
    logging.getLogger().addHandler(central_handler)
else:
    logging.debug("Central logging is disabled.")

# Create a new FastAPI application instance.
app = FastAPI()

# Dictionary to store active rooms.
rooms: Dict[str, List[WebSocket]] = {}

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    logging.debug(f"New connection attempt to room: {room_id}")
    await websocket.accept()
    logging.debug(f"Connection accepted for room: {room_id}")

    if room_id not in rooms:
        rooms[room_id] = []
        logging.debug(f"Created new room entry for: {room_id}")
    
    rooms[room_id].append(websocket)
    logging.debug(f"Current number of connections in room {room_id}: {len(rooms[room_id])}")

    try:
        while True:
            logging.debug(f"Waiting for message in room {room_id}...")
            data = await websocket.receive_text()
            logging.debug(f"Received message in room {room_id}: {data}")

            for connection in rooms[room_id]:
                if connection != websocket:
                    logging.debug(f"Relaying message to a different connection in room {room_id}")
                    await connection.send_text(data)
            logging.debug(f"Finished relaying message in room {room_id}.")
    except WebSocketDisconnect:
        logging.debug(f"WebSocket disconnected from room: {room_id}.")
    except Exception as e:
        logging.error(f"Exception in room {room_id}: {e}")
    finally:
        if websocket in rooms.get(room_id, []):
            rooms[room_id].remove(websocket)
            logging.debug(f"Removed disconnected socket from room {room_id}.")
        if not rooms.get(room_id):
            del rooms[room_id]
            logging.debug(f"Room {room_id} is now empty and removed.")

if __name__ == "__main__":
    logging.debug("Starting signaling server on ws://0.0.0.0:8000...")
    uvicorn.run("signaling_server:app", host="0.0.0.0", port=8000, log_level="debug")
