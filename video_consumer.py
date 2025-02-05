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
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.debug("Video consumer module loaded.")

async def consume_video(track: MediaStreamTrack):
    """
    Continuously read frames from the given track and display them
    in an OpenCV window titled 'Remote Screen'.

    Press 'q' in the OpenCV window to exit the display loop.
    """
    logger.debug("Starting video consumption from track: %s", track)
    try:
        while True:
            logger.debug("Awaiting next video frame...")
            frame = await track.recv()
            logger.debug("Frame received with pts: %s", frame.pts)

            img = frame.to_ndarray(format="bgr24")
            logger.debug("Converted frame to ndarray with shape: %s", img.shape)

            cv2.imshow("Remote Screen", img)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                logger.debug("Detected 'q' key press; exiting video consumer loop.")
                break

    except asyncio.CancelledError:
        logger.debug("Video consumption cancelled (likely due to track closure).")
    except Exception as e:
        logger.error("Error while consuming video: %s", e)
    finally:
        logger.debug("Cleaning up OpenCV windows in video consumer.")
        cv2.destroyAllWindows()
