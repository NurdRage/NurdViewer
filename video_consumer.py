#!/usr/bin/env python3
"""
video_consumer.py

A standalone module for consuming (displaying) video frames
from an aiortc MediaStreamTrack in an OpenCV window.

Usage Example (in your receiver.py or similar file):

    from aiortc import RTCPeerConnection
    import asyncio
    from video_consumer import consume_video

    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            # Launch an async task to display frames from this track
            asyncio.ensure_future(consume_video(track))

    # rest of your code...

Press 'q' in the OpenCV window to close the viewer.
"""

import asyncio
import cv2
from aiortc import MediaStreamTrack

async def consume_video(track: MediaStreamTrack):
    """
    Continuously read frames from the given track and display them
    in an OpenCV window titled 'Remote Screen'.

    Press 'q' in the OpenCV window to exit the display loop.
    """
    try:
        while True:
            # Receive the next frame from the track
            frame = await track.recv()

            # Convert the aiortc frame to a NumPy array
            img = frame.to_ndarray(format="bgr24")

            # Show the frame in a named OpenCV window
            cv2.imshow("Remote Screen", img)

            # If 'q' is pressed, exit the loop
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except asyncio.CancelledError:
        # This may be raised if the track is closed or the app is shutting down
        pass
    finally:
        # Clean up the OpenCV window to avoid dangling GUI issues
        cv2.destroyAllWindows()

