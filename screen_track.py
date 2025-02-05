#!/usr/bin/env python3
import cv2
import numpy as np
from mss import mss
from aiortc import VideoStreamTrack
from av import VideoFrame
import asyncio
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.debug("ScreenTrack module loaded.")

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
        logger.debug("ScreenShareTrack initialized with monitor: %s and frame_rate: %s", self.monitor, frame_rate)

    async def recv(self):
        logger.debug("Waiting for next frame timestamp...")
        pts, time_base = await self.next_timestamp()

        logger.debug("Sleeping for frame delay: %f seconds", self._frame_delay)
        await asyncio.sleep(self._frame_delay)

        logger.debug("Capturing screenshot from monitor: %s", self.monitor)
        screenshot = self.sct.grab(self.monitor)
        img = np.array(screenshot)
        logger.debug("Screenshot captured; raw image shape: %s", img.shape)

        logger.debug("Converting image from BGRA to BGR")
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        logger.debug("Captured frame: pts=%s, shape=%s", pts, img.shape)
        return frame
