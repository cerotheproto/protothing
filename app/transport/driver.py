import logging
from typing import Optional
from urllib.parse import urlparse

from transport.base import TransportBase
from transport.ws import WSTransport
from transport.udp import UDPTransport
from render.frame import Frame


logger = logging.getLogger(__name__)


class Driver:
    """Драйвер для отправки кадров в транспорт"""
    
    def __init__(self):
        self._transport: Optional[TransportBase] = None
        self._ws_transport: Optional[WSTransport] = None
    
    def init_from_config(self, transport_uri: str, ws_enabled: bool = False) -> None:
        """
        Инициализирует транспорт из URI конфига.
        Примеры:
            - udp://192.168.1.100:5555 - UDP на конкретный IP и порт
            - udp://192.168.1.100 - UDP на порт 5555 по умолчанию
        
        WS транспорт инициализируется отдельно через флаг ws_enabled и всегда слушает на /ws
        Приложение может работать только с WS если основной транспорт не указан
        """
        # инициализируем основной транспорт если указан
        if transport_uri:
            parsed = urlparse(transport_uri)
            scheme = parsed.scheme
            
            if scheme == 'udp':
                host = parsed.hostname or "10.0.0.2"
                port = parsed.port or 5555
                self._transport = UDPTransport(host=host, port=port)
                logger.info(f"Инициализирован UDP транспорт: {host}:{port}")
            else:
                raise ValueError(f"Неизвестный тип транспорта: {scheme}")
        
        # WS транспорт инициализируется отдельно если включен в конфиге
        if ws_enabled:
            self._ws_transport = WSTransport()
            logger.info("Инициализирован WS транспорт на /ws (вспомогательный для отладки)")
        
        # убедимся что хотя бы один транспорт инициализирован
        if not self._transport and not self._ws_transport:
            raise ValueError("Должен быть указан хотя бы один транспорт (основной или ws_enabled)")
    
    async def start(self) -> None:
        """Запускает транспорт"""
        if self._transport:
            await self._transport.start()
        if self._ws_transport:
            await self._ws_transport.start()
    
    async def stop(self) -> None:
        """Останавливает транспорт"""
        if self._transport:
            await self._transport.stop()
        if self._ws_transport:
            await self._ws_transport.stop()
    
    async def display_frame(self, frame: Frame) -> None:
        """Отправляет готовый RGB888 кадр 128x32 в транспорт"""
        frame_data = frame.to_bytes()
        if self._transport:
            await self._transport.send_frame(frame_data)
        if self._ws_transport:
            await self._ws_transport.send_frame(frame_data)
    
    async def send_led_strip_frame(self, pixels: bytes) -> None:
        """Отправляет кадр для LED ленты в транспорт"""
        if self._transport:
            await self._transport.send_led_strip_frame(pixels)
        if self._ws_transport:
            await self._ws_transport.send_led_strip_frame(pixels)
    
    def get_ws_transport(self) -> Optional[WSTransport]:
        """Возвращает WS транспорт для регистрации эндпоинта"""
        return self._ws_transport
    
    def set_brightness(self, level: int) -> None:
        if self._transport:
            self._transport.set_brightness(level)
        # для ws не преминимо 

    @property
    def transport(self) -> Optional[TransportBase]:
        return self._transport
    

