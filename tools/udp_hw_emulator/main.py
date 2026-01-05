#!/usr/bin/env python3

import sys
import struct
import socket
import threading
from typing import Optional
from dataclasses import dataclass

import pygame


# Protocol constants
SYNC = 0xAA55
PROTOCOL_VERSION = 0x04

TYPE_CMD = 0x01
TYPE_FRAME = 0x02
TYPE_INFO = 0x03
TYPE_LED_STRIP_FRAME = 0x05
TYPE_BUTTON = 0x06

FRAME_FLAG_COMPRESSED = 1 << 0

CMD_BRIGHTNESS = 0x01

MATRIX_WIDTH = 128
MATRIX_HEIGHT = 32
LED_STRIP_MAX = 16


def crc8(data: bytes) -> int:
    """CRC-8 (poly 0x07) - SMBus variant"""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def rle_decode(data: bytes, expected_pixels: int) -> bytes:
    """Decodes RLE compressed RGB888 pixels"""
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


@dataclass
class Packet:
    """UDP protocol packet (v4)"""
    sync: int
    ver: int
    ptype: int
    length: int
    seq: int
    crc8: int
    payload: bytes
    
    HEADER_SIZE = 9
    
    @classmethod
    def unpack(cls, data: bytes) -> 'Packet':
        """Parses raw bytes into Packet"""
        if len(data) < cls.HEADER_SIZE:
            raise ValueError('Data too short for header')
        
        header_without_crc = data[:cls.HEADER_SIZE - 1]
        crc8_in_packet = data[cls.HEADER_SIZE - 1]
        
        calc_crc8 = crc8(header_without_crc)
        if calc_crc8 != crc8_in_packet:
            raise ValueError(f'Header CRC8 mismatch: got {crc8_in_packet:#02x}, calc {calc_crc8:#02x}')
        
        sync, ver, ptype, length, seq = struct.unpack('<HBBHH', header_without_crc)
        
        if sync != SYNC:
            raise ValueError(f'Bad SYNC: {sync:#04x}')
        
        total_len = cls.HEADER_SIZE + length
        if len(data) < total_len:
            raise ValueError('Data too short for full packet')
        
        payload = data[cls.HEADER_SIZE:total_len]
        
        return cls(
            sync=sync,
            ver=ver,
            ptype=ptype,
            length=length,
            seq=seq,
            crc8=crc8_in_packet,
            payload=payload
        )
    
    @classmethod
    def make_button(cls, button_id: int, seq: int = 0) -> bytes:
        """Creates a BUTTON packet"""
        payload = struct.pack('B', button_id)
        
        header_without_crc = struct.pack('<HBBHH', SYNC, PROTOCOL_VERSION, TYPE_BUTTON, len(payload), seq)
        header_crc = crc8(header_without_crc)
        
        return header_without_crc + struct.pack('B', header_crc) + payload


class HardwareEmulator:
    """Hardware emulator with GUI"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 5555):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.running = False
        self.client_addr: Optional[tuple] = None
        
        # Display buffers
        self.matrix_buffer = bytearray(MATRIX_WIDTH * MATRIX_HEIGHT * 3)
        self.led_strip_buffer = bytearray(LED_STRIP_MAX * 3)
        self.led_strip_count = 0
        self.brightness = 255
        self.button_seq = 0
        
        # GUI
        pygame.init()
        
        # Window dimensions
        self.matrix_pixel_size = 4
        self.led_pixel_size = 8
        self.leds_per_row = 30
        self.padding = 20
        self.button_height = 60
        
        matrix_width = MATRIX_WIDTH * self.matrix_pixel_size
        matrix_height = MATRIX_HEIGHT * self.matrix_pixel_size
        led_width = self.leds_per_row * self.led_pixel_size
        led_height = 10 * self.led_pixel_size
        
        window_width = matrix_width + self.padding * 2
        window_height = matrix_height + led_height + self.button_height + self.padding * 4 + 80
        
        self.screen = pygame.display.set_mode((window_width, window_height))
        pygame.display.set_caption("Hardware Emulator")
        
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        
        # Button rect
        button_width = 300
        button_x = (window_width - button_width) // 2
        button_y = matrix_height + led_height + self.padding * 3 + 40
        self.button_rect = pygame.Rect(button_x, button_y, button_width, self.button_height)
        
        # Clock for FPS
        self.clock = pygame.time.Clock()
        
    def _draw_gui(self):
        """Draws the entire GUI"""
        self.screen.fill((30, 30, 30))
        
        # Title
        title = self.font.render(f"UDP Emulator - {self.host}:{self.port}", True, (255, 255, 255))
        self.screen.blit(title, (self.padding, 10))
        
        # Client status
        client_text = f"Client: {self.client_addr[0]}:{self.client_addr[1]}" if self.client_addr else "No client"
        client = self.small_font.render(client_text, True, (200, 200, 200))
        self.screen.blit(client, (self.padding, 35))
        
        # Draw matrix
        self._draw_matrix()
        
        # Draw LED strip
        self._draw_led_strip()
        
        # Draw button
        self._draw_button()
        
        # Brightness
        brightness_text = f"Brightness: {self.brightness}"
        brightness = self.small_font.render(brightness_text, True, (200, 200, 200))
        brightness_y = self.button_rect.bottom + 10
        self.screen.blit(brightness, (self.padding, brightness_y))
        
        pygame.display.flip()
        
    def _draw_matrix(self):
        """Draws matrix display"""
        y_offset = 60
        
        for y in range(MATRIX_HEIGHT):
            for x in range(MATRIX_WIDTH):
                idx = (y * MATRIX_WIDTH + x) * 3
                r = self.matrix_buffer[idx]
                g = self.matrix_buffer[idx + 1]
                b = self.matrix_buffer[idx + 2]
                
                # Apply brightness
                r = int(r * self.brightness / 255)
                g = int(g * self.brightness / 255)
                b = int(b * self.brightness / 255)
                
                color = (r, g, b)
                
                rect = pygame.Rect(
                    self.padding + x * self.matrix_pixel_size,
                    y_offset + y * self.matrix_pixel_size,
                    self.matrix_pixel_size,
                    self.matrix_pixel_size
                )
                pygame.draw.rect(self.screen, color, rect)
    
    def _draw_led_strip(self):
        """Draws LED strip"""
        y_offset = 60 + MATRIX_HEIGHT * self.matrix_pixel_size + self.padding
        
        for i in range(min(self.led_strip_count, LED_STRIP_MAX)):
            idx = i * 3
            r = self.led_strip_buffer[idx]
            g = self.led_strip_buffer[idx + 1]
            b = self.led_strip_buffer[idx + 2]
            
            # Apply brightness
            r = int(r * self.brightness / 255)
            g = int(g * self.brightness / 255)
            b = int(b * self.brightness / 255)
            
            color = (r, g, b)
            
            x = (i % self.leds_per_row) * self.led_pixel_size
            y = (i // self.leds_per_row) * self.led_pixel_size
            
            center = (
                self.padding + x + self.led_pixel_size // 2,
                y_offset + y + self.led_pixel_size // 2
            )
            radius = self.led_pixel_size // 2 - 1
            
            pygame.draw.circle(self.screen, color, center, radius)
            pygame.draw.circle(self.screen, (100, 100, 100), center, radius, 1)
    
    def _draw_button(self):
        """Draws the button"""
        # Button background
        pygame.draw.rect(self.screen, (70, 130, 180), self.button_rect, border_radius=5)
        pygame.draw.rect(self.screen, (255, 255, 255), self.button_rect, 2, border_radius=5)
        
        # Button text
        text = self.font.render("Boop", True, (255, 255, 255))
        text_rect = text.get_rect(center=self.button_rect.center)
        self.screen.blit(text, text_rect)
    
    def on_button_press(self):
        """Handles button press - sends event to client"""
        if not self.client_addr:
            print("No client connected, cannot send button event")
            return
        
        packet = Packet.make_button(button_id=0, seq=self.button_seq)
        self.button_seq = (self.button_seq + 1) & 0xFFFF
        
        try:
            self.sock.sendto(packet, self.client_addr)
            print(f"Button pressed, sent event to {self.client_addr}")
        except Exception as e:
            print(f"Error sending button event: {e}")
    
    def process_packet(self, packet: Packet):
        """Processes received packet"""
        if packet.ptype == TYPE_FRAME:
            self._process_frame(packet)
        elif packet.ptype == TYPE_LED_STRIP_FRAME:
            self._process_led_strip(packet)
        elif packet.ptype == TYPE_CMD:
            self._process_cmd(packet)
    
    def _process_frame(self, packet: Packet):
        """Processes frame packet"""
        if len(packet.payload) < 3:
            print("Frame payload too short")
            return
        
        frame_id, frame_flags = struct.unpack('<HB', packet.payload[:3])
        pixel_data = packet.payload[3:]
        
        if frame_flags & FRAME_FLAG_COMPRESSED:
            pixels = rle_decode(pixel_data, MATRIX_WIDTH * MATRIX_HEIGHT)
        else:
            pixels = pixel_data
        
        expected_size = MATRIX_WIDTH * MATRIX_HEIGHT * 3
        if len(pixels) != expected_size:
            print(f"Frame size mismatch: {len(pixels)}, expected {expected_size}")
            return
        
        self.matrix_buffer[:] = pixels
    
    def _process_led_strip(self, packet: Packet):
        """Processes LED strip frame packet"""
        if len(packet.payload) < 3:
            print("LED strip payload too short")
            return
        
        frame_id, frame_flags = struct.unpack('<HB', packet.payload[:3])
        pixel_data = packet.payload[3:]
        
        if frame_flags & FRAME_FLAG_COMPRESSED:
            pixels = rle_decode(pixel_data, LED_STRIP_MAX)
        else:
            pixels = pixel_data
        
        if len(pixels) % 3 != 0:
            print(f"LED strip data not aligned to RGB: {len(pixels)}")
            return
        
        self.led_strip_count = len(pixels) // 3
        self.led_strip_buffer[:len(pixels)] = pixels
    
    def _process_cmd(self, packet: Packet):
        """Processes command packet"""
        if not packet.payload:
            return
        
        cmd_id = packet.payload[0]
        cmd_data = packet.payload[1:]
        
        if cmd_id == CMD_BRIGHTNESS and len(cmd_data) >= 1:
            self.brightness = cmd_data[0]
            print(f"Brightness set to: {self.brightness}")
    
    def udp_receiver_thread(self):
        """UDP receiver thread"""
        print(f"UDP receiver started on {self.host}:{self.port}")
        
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65536)
                
                # Save client address for button events
                if addr != self.client_addr:
                    self.client_addr = addr
                    print(f"Client connected from {addr}")
                
                # Parse packet
                try:
                    packet = Packet.unpack(data)
                    self.process_packet(packet)
                except ValueError as e:
                    print(f"Error parsing packet: {e}")
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"UDP receiver error: {e}")
    
    def start(self):
        """Starts the emulator"""
        # Setup UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.settimeout(1.0)
        
        self.running = True
        
        # Start UDP receiver thread
        receiver = threading.Thread(target=self.udp_receiver_thread, daemon=True)
        receiver.start()
        
        # Main event loop
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.button_rect.collidepoint(event.pos):
                        self.on_button_press()
            
            self._draw_gui()
            self.clock.tick(30)  # 30 FPS
        
        # Cleanup
        if self.sock:
            self.sock.close()
        pygame.quit()


def main():
    host = "0.0.0.0"
    port = 5555
    
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    
    emulator = HardwareEmulator(host=host, port=port)
    emulator.start()


if __name__ == "__main__":
    main()
