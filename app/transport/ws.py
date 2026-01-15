import logging
from typing import Optional, Set
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from transport.base import TransportBase
from transport.proto import Packet, CMD_BRIGHTNESS


logger = logging.getLogger(__name__)


class WSTransport(TransportBase):
    """WebSocket транспорт для отправки кадров через WS соединение"""
    
    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._seq: int = 0
        self._led_seq: int = 0
        self._brightness: int = 150
    
    async def send_frame(self, frame_data: bytes) -> None:
        """Отправляет кадр всем подключенным клиентам"""
        if not self._connections:
            return
        
        packet = Packet.make_frame(
            frame_id=self._seq,
            pixels=frame_data,
            seq=self._seq,
            compress=True
        )
        self._seq = (self._seq + 1) & 0xFFFF
        
        data = packet.pack()
        
        disconnected = set()
        for ws in self._connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_bytes(data)
                else:
                    disconnected.add(ws)
            except Exception as e:
                logger.error(f"Error sending to WS: {e}")
                disconnected.add(ws)
        
        self._connections -= disconnected
    
    async def send_led_strip_frame(self, pixels: bytes) -> None:
        """Отправляет кадр для LED ленты всем подключенным клиентам"""
        if not self._connections:
            return
        
        packet = Packet.make_led_strip_frame(
            frame_id=self._led_seq,
            pixels=pixels,
            seq=self._led_seq,
            compress=True
        )
        self._led_seq = (self._led_seq + 1) & 0xFFFF
        
        data = packet.pack()
        
        disconnected = set()
        for ws in self._connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_bytes(data)
                else:
                    disconnected.add(ws)
            except Exception as e:
                logger.error(f"Error sending LED to WS: {e}")
                disconnected.add(ws)
        
        self._connections -= disconnected
    
    async def _broadcast_brightness(self) -> None:
        """Отправляет текущий уровень яркости всем подключенным клиентам"""
        if not self._connections:
            return
        
        packet = Packet.make_cmd(CMD_BRIGHTNESS, bytes([self._brightness]), seq=self._seq)
        self._seq = (self._seq + 1) & 0xFFFF
        data = packet.pack()
        
        disconnected = set()
        for ws in self._connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_bytes(data)
                else:
                    disconnected.add(ws)
            except Exception as e:
                logger.error(f"Error sending brightness to WS: {e}")
                disconnected.add(ws)
        
        self._connections -= disconnected
    
    async def is_connected(self) -> bool:
        return len(self._connections) > 0
    
    async def start(self) -> None:
        logger.info("WS transport started")
    
    async def stop(self) -> None:
        for ws in list(self._connections):
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()
        logger.info("WS transport stopped")
    
    async def add_connection(self, websocket: WebSocket) -> None:
        """Добавляет новое WS соединение"""
        await websocket.accept()
        self._connections.add(websocket)
        logger.info(f"WS client connected, total: {len(self._connections)}")
        
        # send current brightness to new client
        try:
            packet = Packet.make_cmd(CMD_BRIGHTNESS, bytes([self._brightness]), seq=self._seq)
            self._seq = (self._seq + 1) & 0xFFFF
            data = packet.pack()
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_bytes(data)
        except Exception as e:
            logger.error(f"Error sending initial brightness to WS: {e}")
    
    async def remove_connection(self, websocket: WebSocket) -> None:
        """Удаляет WS соединение"""
        self._connections.discard(websocket)
        logger.info(f"WS client disconnected, total: {len(self._connections)}")
    
    async def handle_connection(self, websocket: WebSocket) -> None:
        """Обрабатывает WS соединение"""
        await self.add_connection(websocket)
        try:
            while websocket.client_state == WebSocketState.CONNECTED:
                try:
                    data = await websocket.receive_bytes()
                    await self._handle_incoming(data)
                except Exception:
                    break
        finally:
            await self.remove_connection(websocket)
    
    async def _handle_incoming(self, data: bytes) -> None:
        """Обрабатывает входящие данные от клиента"""
        try:
            packet = Packet.unpack(data)
            logger.debug(f"Received packet: {packet}")
        except ValueError as e:
            logger.warning(f"Error parsing packet: {e}")

    async def get_brightness(self):
        return self._brightness

    async def set_brightness(self, brightness: int):
        self._brightness = brightness
        await self._broadcast_brightness()