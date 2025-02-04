import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List

app = FastAPI()

rooms: Dict[str, List[WebSocket]] = {}

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    if room_id not in rooms:
        rooms[room_id] = []
    rooms[room_id].append(websocket)
    
    print(f"[DEBUG] WebSocket connection opened in room: {room_id}.")

    try:
        while True:
            # Wait indefinitely for incoming messages
            data = await websocket.receive_text()
            print(f"[DEBUG] Received message in room {room_id}: {data}")

            # Relay the message to all other clients in the same room.
            for connection in rooms[room_id]:
                if connection != websocket:
                    await connection.send_text(data)
    except WebSocketDisconnect:
        print(f"[DEBUG] WebSocket disconnected from room: {room_id}.")
    finally:
        rooms[room_id].remove(websocket)
        if not rooms[room_id]:
            del rooms[room_id]
            print(f"[DEBUG] Room {room_id} is now empty and removed.")

if __name__ == "__main__":
    print("[DEBUG] Starting signaling server on ws://0.0.0.0:8000...")
    uvicorn.run("signaling_server:app", host="0.0.0.0", port=8000)
