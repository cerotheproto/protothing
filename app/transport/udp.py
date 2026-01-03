import logging
import asyncio
from typing import Optional, Tuple, Callable
from transport.base import TransportBase
from transport.proto import Packet, TYPE_BUTTON


logger = logging.getLogger(__name__)

# Команды (для TYPE_CMD)
CMD_BRIGHTNESS = 0x01


class UDPTransport(TransportBase):    
    def __init__(self, host: str = "192.168.1.100", port: int = 5555):
        """
        Инициализирует UDP транспорт
        host - IP адрес устройства
        port - UDP порт
        """
        self.host = host
        self.port = port
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional[asyncio.DatagramProtocol] = None
        self._seq = 0
        self._led_seq = 0
        self._button_callback: Optional[Callable[[int], None]] = None
        self._brightness: int = 255
    
    async def start(self) -> None:
        """Запускает UDP транспорт"""
        loop = asyncio.get_event_loop()
        try:
            # Создаем UDP сокет для отправки
            protocol = _UDPProtocol(self._button_callback)
            self._transport, self._protocol = await loop.create_datagram_endpoint(
                lambda: protocol,
                remote_addr=(self.host, self.port)
            )
            logger.info(f"UDP transport started: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Error starting UDP transport: {e}")
            raise
    
    async def stop(self) -> None:
        """Останавливает UDP транспорт"""
        if self._transport:
            self._transport.close()
        logger.info("UDP transport stopped")
    
    def set_button_callback(self, callback: Callable[[int], None]) -> None:
        """Устанавливает коллбек для обработки нажатий кнопки"""
        self._button_callback = callback
    
    async def send_frame(self, frame_data: bytes) -> None:
        """Отправляет кадр 128x32 на устройство"""
        if not self._transport:
            logger.warning("UDP transport not initialized")
            return
        
        packet = Packet.make_frame(
            frame_id=self._seq,
            pixels=frame_data,
            seq=self._seq,
            compress=True
        )
        self._seq = (self._seq + 1) & 0xFFFF
        
        try:
            data = packet.pack()
            self._transport.sendto(data)
        except Exception as e:
            logger.error(f"Error sending frame: {e}")
    

    async def send_led_strip_frame(self, pixels: bytes) -> None:
        """Отправляет кадр для LED ленты на устройство"""
        if not self._transport:
            logger.warning("UDP transport is not initialized")
            return
        
        packet = Packet.make_led_strip_frame(
            frame_id=self._led_seq,
            pixels=pixels,
            seq=self._led_seq,
            compress=True
        )
        self._led_seq = (self._led_seq + 1) & 0xFFFF
        
        try:
            data = packet.pack()
            self._transport.sendto(data)
        except Exception as e:
            logger.error(f"Error sending LED frame: {e}")
    
    async def is_connected(self) -> bool:
        """Checks connection (UDP has no connection state, returns True if initialized)"""
        return self._transport is not None
    
    def set_brightness(self, level: int) -> None:
        """Sets the display brightness level (0-255)"""
        if not self._transport:
            logger.warning("UDP transport is not initialized")
            return
        
        if level < 0 or level > 255:
            logger.warning(f"Invalid brightness level: {level}")
            return
        
        self._brightness = level
        
        packet = Packet.make_cmd(CMD_BRIGHTNESS, bytes([level]), seq=self._seq)
        self._seq = (self._seq + 1) & 0xFFFF
        
        try:
            data = packet.pack()
            self._transport.sendto(data)
        except Exception as e:
            logger.error(f"Error sending brightness command: {e}")
    
    def get_brightness(self) -> int:
        """Returns the current display brightness level"""
        return self._brightness


class _UDPProtocol(asyncio.DatagramProtocol):
    """Internal protocol for handling UDP packets"""
    
    def __init__(self, button_callback: Optional[Callable[[int], None]] = None):
        self.button_callback = button_callback
    
    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handles incoming UDP packets"""
        try:
            packet = Packet.unpack(data)
            logger.debug(f"UDP packet from {addr}: {packet}")
            
            if packet.ptype == TYPE_BUTTON:
                payload = packet.parse_payload()
                button_id = payload.get('button_id', 0)
                logger.info(f"Received button press: {button_id}")
                if self.button_callback:
                    self.button_callback(button_id)
                    
        except ValueError as e:
            logger.warning(f"Error parsing UDP packet: {e}")
    
    def error_received(self, exc: Exception) -> None:
        """Handles UDP errors"""
        logger.error(f"UDP error: {exc}")
    
    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called when the connection is lost"""
        if exc:
            logger.error(f"UDP connection lost: {exc}")
