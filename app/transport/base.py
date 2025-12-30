from abc import ABC, abstractmethod


class TransportBase(ABC):
    """Базовый класс для всех транспортов"""
    
    @abstractmethod
    async def send_frame(self, frame_data: bytes) -> None:
        """Отправляет кадр RGB888 128x32 в транспорт"""
        pass
    
    @abstractmethod
    async def send_led_strip_frame(self, pixels: bytes) -> None:
        """Отправляет кадр для LED ленты в транспорт"""
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """Проверяет подключен ли транспорт"""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Запускает транспорт"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Останавливает транспорт"""
        pass

    @abstractmethod
    def set_brightness(self, level: int) -> None:
        """Устанавливает яркость дисплея"""
        pass

    @abstractmethod
    def get_brightness(self) -> int:
        """Возвращает текущий уровень яркости дисплея"""
        pass