import logging
import asyncio
from typing import Optional, Tuple, Callable
from transport.base import TransportBase
from transport.proto import Packet, TYPE_BUTTON


logger = logging.getLogger(__name__)

# Команды (для TYPE_CMD)
CMD_BRIGHTNESS = 0x01


class UDPTransport(TransportBase):
    """UDP транспорт для отправки кадров на W5500/RP2040"""
    
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
            logger.info(f"UDP транспорт запущен: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Ошибка запуска UDP транспорта: {e}")
            raise
    
    async def stop(self) -> None:
        """Останавливает UDP транспорт"""
        if self._transport:
            self._transport.close()
        logger.info("UDP транспорт остановлен")
    
    def set_button_callback(self, callback: Callable[[int], None]) -> None:
        """Устанавливает коллбек для обработки нажатий кнопки"""
        self._button_callback = callback
    
    async def send_frame(self, frame_data: bytes) -> None:
        """Отправляет кадр 128x32 на устройство"""
        if not self._transport:
            logger.warning("UDP транспорт не инициализирован")
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
            logger.error(f"Ошибка отправки кадра: {e}")
    

    async def send_led_strip_frame(self, pixels: bytes) -> None:
        """Отправляет кадр для LED ленты на устройство"""
        if not self._transport:
            logger.warning("UDP транспорт не инициализирован")
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
            logger.error(f"Ошибка отправки LED кадра: {e}")
    
    async def is_connected(self) -> bool:
        """Проверяет подключение (UDP не имеет состояния соединения, возвращает True если инициализирован)"""
        return self._transport is not None
    
    def set_brightness(self, level: int) -> None:
        """Устанавливает яркость дисплея"""
        if not self._transport:
            logger.warning("UDP транспорт не инициализирован")
            return
        
        if level < 0 or level > 255:
            logger.warning(f"Некорректный уровень яркости: {level}")
            return
        
        self._brightness = level
        
        packet = Packet.make_cmd(CMD_BRIGHTNESS, bytes([level]), seq=self._seq)
        self._seq = (self._seq + 1) & 0xFFFF
        
        try:
            data = packet.pack()
            self._transport.sendto(data)
        except Exception as e:
            logger.error(f"Ошибка отправки команды яркости: {e}")
    
    def get_brightness(self) -> int:
        """Возвращает текущий уровень яркости дисплея"""
        return self._brightness


class _UDPProtocol(asyncio.DatagramProtocol):
    """Внутренний протокол для обработки UDP пакетов"""
    
    def __init__(self, button_callback: Optional[Callable[[int], None]] = None):
        self.button_callback = button_callback
    
    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Обрабатывает входящие UDP пакеты"""
        try:
            packet = Packet.unpack(data)
            logger.debug(f"UDP пакет от {addr}: {packet}")
            
            if packet.ptype == TYPE_BUTTON:
                payload = packet.parse_payload()
                button_id = payload.get('button_id', 0)
                logger.info(f"Получено нажатие кнопки: {button_id}")
                if self.button_callback:
                    self.button_callback(button_id)
                    
        except ValueError as e:
            logger.warning(f"Ошибка парсинга UDP пакета: {e}")
    
    def error_received(self, exc: Exception) -> None:
        """Обрабатывает ошибки UDP"""
        logger.error(f"Ошибка UDP: {exc}")
    
    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Вызывается когда соединение потеряно"""
        if exc:
            logger.error(f"UDP соединение потеряно: {exc}")
