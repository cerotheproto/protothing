import struct
from typing import Dict, Any
from fastcrc.crc8 import smbus as _crc8_impl


def crc8(data: bytes) -> int:
    """CRC-8 (poly 0x07) using fastcrc's SMBus variant (equivalent to previous implementation)."""
    return int(_crc8_impl(data))


# константы протокола UDP (v4)
SYNC = 0xAA55
PROTOCOL_VERSION = 0x04

TYPE_CMD = 0x01
TYPE_FRAME = 0x02
TYPE_INFO = 0x03
TYPE_LED_STRIP_FRAME = 0x05
TYPE_BUTTON = 0x06

# флаги кадра
FRAME_FLAG_COMPRESSED = 1 << 0


def rle_encode(pixels: bytes) -> bytes:
    """
    RLE сжатие RGB888 пикселей.
    Формат:
    - control byte: старший бит = тип (1=run, 0=literal), младшие 7 бит = длина-1
    - run: 3 байта RGB повторяются (control & 0x7F) + 1 раз
    - literal: следующие ((control & 0x7F) + 1) * 3 байт - сырые пиксели
    """
    if len(pixels) == 0 or len(pixels) % 3 != 0:
        return pixels
    
    result = bytearray()
    pixel_count = len(pixels) // 3
    i = 0
    
    while i < pixel_count:
        r, g, b = pixels[i*3], pixels[i*3+1], pixels[i*3+2]
        
        # считаем сколько одинаковых пикселей подряд
        run_length = 1
        while (i + run_length < pixel_count and 
               run_length < 128 and
               pixels[(i + run_length)*3] == r and
               pixels[(i + run_length)*3 + 1] == g and
               pixels[(i + run_length)*3 + 2] == b):
            run_length += 1
        
        if run_length >= 3:
            # выгодно использовать run
            control = 0x80 | (run_length - 1)
            result.append(control)
            result.extend([r, g, b])
            i += run_length
        else:
            # собираем литералы пока не встретим серию >= 3
            literal_start = i
            literal_count = 0
            
            while i < pixel_count and literal_count < 128:
                r2, g2, b2 = pixels[i*3], pixels[i*3+1], pixels[i*3+2]
                run_ahead = 1
                while (i + run_ahead < pixel_count and 
                       run_ahead < 128 and
                       pixels[(i + run_ahead)*3] == r2 and
                       pixels[(i + run_ahead)*3 + 1] == g2 and
                       pixels[(i + run_ahead)*3 + 2] == b2):
                    run_ahead += 1
                
                if run_ahead >= 3 and literal_count > 0:
                    break
                
                literal_count += 1
                i += 1
            
            if literal_count > 0:
                control = (literal_count - 1)
                result.append(control)
                result.extend(pixels[literal_start*3 : (literal_start + literal_count)*3])
    
    return bytes(result)


def rle_decode(data: bytes, expected_pixels: int) -> bytes:
    """Декодирование RLE сжатых RGB888 пикселей."""
    result = bytearray()
    expected_bytes = expected_pixels * 3
    read_offset = 0
    
    while read_offset < len(data) and len(result) < expected_bytes:
        control = data[read_offset]
        read_offset += 1
        
        is_run = (control & 0x80) != 0
        count = (control & 0x7F) + 1
        
        if is_run:
            if read_offset + 3 > len(data):
                break
            r, g, b = data[read_offset], data[read_offset+1], data[read_offset+2]
            read_offset += 3
            for _ in range(count):
                result.extend([r, g, b])
        else:
            literal_bytes = count * 3
            if read_offset + literal_bytes > len(data):
                break
            result.extend(data[read_offset:read_offset + literal_bytes])
            read_offset += literal_bytes
    
    return bytes(result)


class Packet:
    """
    Пакет протокола UDP (v4).
    
    Заголовок (9 байт): SYNC(2), VER(1), TYPE(1), LEN(2), SEQ(2), CRC8(1)
    Упрощенный протокол для UDP - только CRC8 для целостности заголовка.
    """

    HEADER_FMT_NO_CRC = '<H B B H H'  # SYNC, VER, TYPE, LEN, SEQ
    HEADER_FMT = HEADER_FMT_NO_CRC + ' B'  # + CRC8
    HEADER_SIZE = struct.calcsize(HEADER_FMT)  # 9 байт

    def __init__(self, ptype: int, seq: int = 0,
                 version: int = PROTOCOL_VERSION, payload: bytes = b""):
        self.sync = SYNC
        self.ver = version
        self.ptype = ptype
        self.len = len(payload)
        self.seq = seq
        self.payload = payload or b""
        self.crc8 = 0

    def pack_header(self) -> bytes:
        """Упаковывает заголовок без CRC8, вычисляет CRC8 и возвращает полный заголовок."""
        header_without_crc = struct.pack(
            self.HEADER_FMT_NO_CRC,
            self.sync,
            self.ver,
            self.ptype,
            self.len,
            self.seq,
        )
        self.crc8 = crc8(header_without_crc)
        return header_without_crc + struct.pack('B', self.crc8)

    def pack(self) -> bytes:
        """Упаковывает весь пакет для отправки."""
        header = self.pack_header()
        return header + (self.payload or b"")

    @classmethod
    def unpack(cls, data: bytes) -> 'Packet':
        """Парсит сырые байты в Packet."""
        if len(data) < cls.HEADER_SIZE:
            raise ValueError('data too short for header')

        header_without_crc = data[: cls.HEADER_SIZE - 1]
        crc8_in_packet = data[cls.HEADER_SIZE - 1]

        calc_crc8 = crc8(header_without_crc)
        if calc_crc8 != crc8_in_packet:
            raise ValueError(f'header CRC8 mismatch: got {crc8_in_packet:#02x}, calc {calc_crc8:#02x}')

        sync, ver, ptype, length, seq = struct.unpack(cls.HEADER_FMT_NO_CRC, header_without_crc)

        if sync != SYNC:
            raise ValueError(f'bad SYNC: {sync:#04x}')

        total_len = cls.HEADER_SIZE + length
        if len(data) < total_len:
            raise ValueError('data too short for full packet')

        payload_start = cls.HEADER_SIZE
        payload_end = payload_start + length
        payload = data[payload_start:payload_end]

        pkt = cls(ptype=ptype, seq=seq, version=ver, payload=payload)
        pkt.crc8 = crc8_in_packet
        return pkt

    @classmethod
    def make_cmd(cls, cmd_id: int, args: bytes = b"", seq: int = 0) -> 'Packet':
        payload = struct.pack('B', cmd_id) + (args or b"")
        return cls(ptype=TYPE_CMD, seq=seq, payload=payload)

    @classmethod
    def make_frame(cls, frame_id: int, pixels: bytes, seq: int = 0, compress: bool = True) -> 'Packet':
        """
        Создает FRAME пакет. Всегда ожидает полный кадр 128x32.
        pixels - RGB888 байты (128*32*3 = 12288 байт).
        compress - использовать RLE сжатие.
        """
        frame_flags = 0
        pixel_data = pixels
        
        if compress:
            compressed = rle_encode(pixels)
            if len(compressed) < len(pixels):
                pixel_data = compressed
                frame_flags |= FRAME_FLAG_COMPRESSED
        
        payload = struct.pack('<H B', frame_id, frame_flags) + pixel_data
        return cls(ptype=TYPE_FRAME, seq=seq, payload=payload)

    @classmethod
    def make_info(cls, brightness: int, seq: int = 0) -> 'Packet':
        payload = struct.pack('<B', brightness)
        return cls(ptype=TYPE_INFO, seq=seq, payload=payload)

    @classmethod
    def make_led_strip_frame(cls, frame_id: int, pixels: bytes, seq: int = 0, compress: bool = True) -> 'Packet':
        """
        Создает LED_STRIP_FRAME пакет для ws2812b ленты.
        pixels - RGB888 байты произвольной длины.
        compress - использовать RLE сжатие.
        """
        frame_flags = 0
        pixel_data = pixels
        
        if compress:
            compressed = rle_encode(pixels)
            if len(compressed) < len(pixels):
                pixel_data = compressed
                frame_flags |= FRAME_FLAG_COMPRESSED
        
        payload = struct.pack('<H B', frame_id, frame_flags) + pixel_data
        return cls(ptype=TYPE_LED_STRIP_FRAME, seq=seq, payload=payload)

    def parse_payload(self) -> Dict[str, Any]:
        """Декодирует полезную нагрузку в соответствии с типом пакета."""
        if self.ptype == TYPE_CMD:
            if not self.payload:
                return {'id': None, 'data': b''}
            cmd_id = self.payload[0]
            data = self.payload[1:]
            return {'id': cmd_id, 'data': data}

        if self.ptype == TYPE_FRAME:
            if len(self.payload) < 3:
                raise ValueError('frame payload too short')
            frame_id, frame_flags = struct.unpack('<H B', self.payload[:3])
            pixel_data = self.payload[3:]
            
            if frame_flags & FRAME_FLAG_COMPRESSED:
                pixels = rle_decode(pixel_data, 128 * 32)
            else:
                pixels = pixel_data
            
            return {'frame_id': frame_id, 'frame_flags': frame_flags, 'pixels': pixels}

        if self.ptype == TYPE_INFO:
            if len(self.payload) < 3:
                raise ValueError('info payload too short')
            fw_ver, brightness = struct.unpack('<H B', self.payload[:3])
            return {'fw_ver': fw_ver, 'brightness': brightness}

        if self.ptype == TYPE_BUTTON:
            if len(self.payload) < 1:
                raise ValueError('button payload too short')
            button_id = self.payload[0]
            return {'button_id': button_id}

        return {'raw': self.payload}

    def __repr__(self) -> str:
        return f"Packet(type={self.ptype:#02x}, seq={self.seq}, len={self.len})"

    
