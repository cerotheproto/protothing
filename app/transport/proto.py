import struct
import qoi
import numpy as np
import logging
from typing import Dict, Any
from fastcrc.crc8 import smbus as _crc8_impl

logger = logging.getLogger(__name__)

def crc8(data: bytes) -> int:
    """CRC-8 (poly 0x07) using fastcrc's SMBus variant (equivalent to previous implementation)."""
    return int(_crc8_impl(data))


def qoi_encode(pixels: bytes) -> bytes:
    """Encodes RGB888 bytes to QOI format."""
    try:
        arr = np.frombuffer(pixels, dtype=np.uint8)
        if arr.size % 3 != 0:
            return pixels
            
        num_pixels = arr.size // 3
        
        if num_pixels == 128 * 32:
            arr = arr.reshape((32, 128, 3))
        elif num_pixels == 64 * 32:
            arr = arr.reshape((32, 64, 3))
        else:
            arr = arr.reshape((1, num_pixels, 3))
        
        encoded = qoi.encode(arr)
        

            
        return encoded
    except Exception as e:
        logger.error(f"QOI encode failed: {e}")
        return pixels
    
def qoi_decode(data: bytes) -> bytes:
    """Decodes QOI data to RGB888 bytes."""
    try:
        decoded = qoi.decode(data)
        return decoded.tobytes()
    except Exception as e:
        logger.error(f"QOI decode failed: {e}")
        return b""


# константы протокола UDP (v5)
SYNC = 0xAA55
PROTOCOL_VERSION = 0x05

TYPE_CMD = 0x01
TYPE_FRAME = 0x02
TYPE_INFO = 0x03
TYPE_LED_STRIP_FRAME = 0x05
TYPE_BUTTON = 0x06

# Command IDs (for TYPE_CMD)
CMD_BRIGHTNESS = 0x01

# флаги кадра
FRAME_FLAG_COMPRESSED = 1 << 0


class Packet:
    """
    Пакет протокола UDP (v5).
    HEADER: SYNC(2) VER(1) TYPE(1) SEQ(2) OFFSET(2) LENGTH(2) TOTAL_LEN(2) CRC8(1) == 13 bytes
    """

    HEADER_FMT_NO_CRC = '<H B B H H H H'  # SYNC, VER, TYPE, SEQ, OFFSET, LENGTH, TOTAL_LEN
    HEADER_FMT = HEADER_FMT_NO_CRC + ' B'
    HEADER_SIZE = struct.calcsize(HEADER_FMT)

    def __init__(self, ptype: int, seq: int = 0,
                 version: int = PROTOCOL_VERSION, payload: bytes = b"",
                 offset: int = 0, total_len: int = 0):
        self.sync = SYNC
        self.ver = version
        self.ptype = ptype
        self.seq = seq
        self.offset = offset
        self.payload = payload or b""
        self.len = len(self.payload)
        self.total_len = total_len if total_len > 0 else self.len
        self.crc8 = 0

    def pack_header(self) -> bytes:
        header_without_crc = struct.pack(
            self.HEADER_FMT_NO_CRC,
            self.sync,
            self.ver,
            self.ptype,
            self.seq,
            self.offset,
            self.len,
            self.total_len
        )
        self.crc8 = crc8(header_without_crc)
        return header_without_crc + struct.pack('B', self.crc8) # CRC8 is last

    def pack(self) -> bytes:
        header = self.pack_header()
        return header + (self.payload or b"")

    @classmethod
    def unpack(cls, data: bytes) -> 'Packet':
        if len(data) < cls.HEADER_SIZE:
            raise ValueError('data too short for header')

        header_without_crc = data[: cls.HEADER_SIZE - 1]
        crc8_in_packet = data[cls.HEADER_SIZE - 1]

        calc_crc8 = crc8(header_without_crc)
        if calc_crc8 != crc8_in_packet:
            raise ValueError(f'header CRC8 mismatch: got {crc8_in_packet:#02x}, calc {calc_crc8:#02x}')

        sync, ver, ptype, seq, offset, length, total_len = struct.unpack(cls.HEADER_FMT_NO_CRC, header_without_crc)

        if sync != SYNC:
            raise ValueError(f'bad SYNC: {sync:#04x}')

        payload_start = cls.HEADER_SIZE
        payload_end = payload_start + length

        payload = data[payload_start:payload_end]
        
        return cls(ptype=ptype, seq=seq, version=ver, payload=payload, offset=offset, total_len=total_len)

    @classmethod
    def make_cmd(cls, cmd_id: int, args: bytes = b"", seq: int = 0) -> 'Packet':
        payload = struct.pack('B', cmd_id) + (args or b"")
        return cls(ptype=TYPE_CMD, seq=seq, payload=payload)

    @classmethod
    def make_frame(cls, frame_id: int, pixels: bytes, seq: int = 0, compress: bool = True) -> 'Packet':
        frame_flags = 0
        pixel_data = pixels
        
        if compress:
            compressed = qoi_encode(pixels)
            if len(compressed) < len(pixels) and compressed != pixels:
                pixel_data = compressed
                frame_flags |= FRAME_FLAG_COMPRESSED
        
        payload = struct.pack('<H B', frame_id, frame_flags) + pixel_data
        return cls(ptype=TYPE_FRAME, seq=seq, payload=payload)

    @classmethod
    def make_led_strip_frame(cls, frame_id: int, pixels: bytes, seq: int = 0, compress: bool = True) -> 'Packet':
        frame_flags = 0
        pixel_data = pixels
        
        if compress:
            compressed = qoi_encode(pixels)
            if len(compressed) < len(pixels) and compressed != pixels:
                pixel_data = compressed
                frame_flags |= FRAME_FLAG_COMPRESSED
        
        payload = struct.pack('<H B', frame_id, frame_flags) + pixel_data
        return cls(ptype=TYPE_LED_STRIP_FRAME, seq=seq, payload=payload)

    def parse_payload(self) -> Dict[str, Any]:
        if self.ptype == TYPE_CMD:
            if not self.payload:
                return {'id': None, 'data': b''}
            cmd_id = self.payload[0]
            data = self.payload[1:]
            return {'id': cmd_id, 'data': data}

        if self.ptype == TYPE_FRAME:
            if len(self.payload) < 3:
                return {'raw': self.payload, 'partial': True} 
                
            frame_id, frame_flags = struct.unpack('<H B', self.payload[:3])
            pixel_data = self.payload[3:]
            
            if frame_flags & FRAME_FLAG_COMPRESSED:
                pixels = qoi.decode(pixel_data)
            else:
                pixels = pixel_data
            
            return {'frame_id': frame_id, 'frame_flags': frame_flags, 'pixels': pixels}
            
        if self.ptype == TYPE_INFO:
            if len(self.payload) < 3:
                 return {'raw': self.payload}

            fw_ver, brightness = struct.unpack('<H B', self.payload[:3])
            return {'fw_ver': fw_ver, 'brightness': brightness}

        if self.ptype == TYPE_BUTTON:
             if len(self.payload) < 1:
                return {'button_id': 0}
             return {'button_id': self.payload[0]}

        return {'raw': self.payload}

    def __repr__(self) -> str:
        return f"Packet(type={self.ptype:#02x}, seq={self.seq}, off={self.offset}, len={self.len}/{self.total_len})"

    
