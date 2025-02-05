#!/usr/bin/env python3
import cv2
import numpy as np
from mss import mss
from aiortc import VideoStreamTrack
from av import VideoFrame
import asyncio
import logging

logger = logging.getLogger(__name__)

class ScreenShareTrack(VideoStreamTrack):
    """
    A VideoStreamTrack that captures the screen using mss and converts frames
    to VideoFrame objects for WebRTC.
    """
    def __init__(self, monitor: dict = None, frame_rate: float = 15.0):
        super().__init__()  # initialize the parent class
        self.sct = mss()
        # If no monitor is provided, use the first available monitor.
        self.monitor = monitor if monitor is not None else self.sct.monitors[1]
        self.frame_rate = frame_rate
        # Calculate the delay between frames.
        self._frame_delay = 1 / frame_rate
        logger.debug(f"ScreenShareTrack initialized with monitor: {self.monitor} and frame_rate: {frame_rate}")

    async def recv(self):
        # Wait for the next frame timestamp.
        pts, time_base = await self.next_timestamp()

        # Sleep to regulate frame rate
        await asyncio.sleep(self._frame_delay)

        # Capture the screen using mss.
        screenshot = self.sct.grab(self.monitor)
        img = np.array(screenshot)

        # Convert the image from BGRA to BGR (if needed)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        # Create a VideoFrame from the numpy array.
        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        logger.debug(f"Captured frame: pts={pts}, shape={img.shape}")
        return frame
