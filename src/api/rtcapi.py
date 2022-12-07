import asyncio
import logging

from aiortc import RTCPeerConnection, RTCSessionDescription

class RTCPeerConnectionManager:
    def __init__(self):
        self.connections = []

    async def answer(self):
        pass
