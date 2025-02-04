import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List

# Create a new FastAPI application instance.
app = FastAPI()

# This dictionary will store active rooms.
# Each room (a key) will map to a list of connected WebSocket objects.
rooms: Dict[str, List[WebSocket]] = {}

# Define a WebSocket endpoint that clients will connect to.
# The {room_id} in the URL is used to group clients into rooms.
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    print(f"[DEBUG] New connection attempt to room: {room_id}")
    
    # Accept the incoming WebSocket connection.
    await websocket.accept()
    print(f"[DEBUG] Connection accepted for room: {room_id}")

    # If this room_id doesn't exist in our dictionary, create a new list for it.
    if room_id not in rooms:
        rooms[room_id] = []
        print(f"[DEBUG] Created new room entry for: {room_id}")
    
    # Add the current WebSocket connection to the room's list.
    rooms[room_id].append(websocket)
    print(f"[DEBUG] Current number of connections in room {room_id}: {len(rooms[room_id])}")

    try:
        # This loop will run indefinitely to keep the connection alive
        # and to continuously process incoming messages.
        while True:
            print(f"[DEBUG] Waiting for message in room {room_id}...")
            # Wait for a text message from the client.
            data = await websocket.receive_text()
            print(f"[DEBUG] Received message in room {room_id}: {data}")

            # Loop over every connection in this room.
            for connection in rooms[room_id]:
                # Do not send the message back to the sender.
                if connection != websocket:
                    print(f"[DEBUG] Relaying message to a different connection in room {room_id}")
                    await connection.send_text(data)
            print(f"[DEBUG] Finished relaying message in room {room_id}.")
    except WebSocketDisconnect:
        # This exception is raised when a client disconnects.
        print(f"[DEBUG] WebSocket disconnected from room: {room_id}.")
    except Exception as e:
        # Catch any unexpected exceptions and log them.
        print(f"[ERROR] Exception in room {room_id}: {e}")
    finally:
        # Remove the WebSocket connection from the room list.
        if websocket in rooms.get(room_id, []):
            rooms[room_id].remove(websocket)
            print(f"[DEBUG] Removed disconnected socket from room {room_id}.")
        # If no connections remain in the room, delete the room.
        if not rooms.get(room_id):
            del rooms[room_id]
            print(f"[DEBUG] Room {room_id} is now empty and removed.")

# The following code is executed when this script is run directly.
if __name__ == "__main__":
    print("[DEBUG] Starting signaling server on ws://0.0.0.0:8000...")
    # uvicorn.run() starts the server with our FastAPI app.
    uvicorn.run("signaling_server:app", host="0.0.0.0", port=8000, log_level="debug")
