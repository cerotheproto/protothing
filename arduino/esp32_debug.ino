/*
    This sketch I used to debug HUB75 and other hardware over Wifi
 */

#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#include <FastLED.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <stdarg.h>

// WiFi credentials
const char* ssid = "MT_FREE";
const char* password = "RLoztPcQ";

// WebSocket server
const char* ws_host = "192.168.1.221";
const uint16_t ws_port = 8000;
const char* ws_path = "/api/ws";

// Panel config
#define PANEL_WIDTH 64
#define PANEL_HEIGHT 32
#define PANELS_NUMBER 2
#define PIN_E -1

// LED strip config (ws2812b)
#define LED_STRIP_PIN 25
#define LED_STRIP_MAX_LEDS 300

#define PANE_WIDTH (PANEL_WIDTH * PANELS_NUMBER)
#define PANE_HEIGHT PANEL_HEIGHT
#define FULL_FRAME_PIXELS (PANE_WIDTH * PANE_HEIGHT)
#define FULL_FRAME_BYTES (FULL_FRAME_PIXELS * 3)

// Protocol v4 constants
#define SYNC_MARKER 0xAA55
#define PROTOCOL_VERSION 0x04
#define HEADER_SIZE 9

#define PACKET_TYPE_CMD 0x01
#define PACKET_TYPE_FRAME 0x02
#define PACKET_TYPE_INFO 0x03
#define PACKET_TYPE_ACK 0x04
#define PACKET_TYPE_LED_STRIP_FRAME 0x05

#define FRAME_FLAG_COMPRESSED 0x01

MatrixPanel_I2S_DMA *dma_display = nullptr;
WebSocketsClient webSocket;

// LED strip
CRGB ledStrip[LED_STRIP_MAX_LEDS];
uint16_t currentLedCount = 0;
uint8_t ledStripBuffer[LED_STRIP_MAX_LEDS * 3];

#define MAX_BUFFER_SIZE 16384
uint8_t wsBuffer[MAX_BUFFER_SIZE];
size_t bufferIndex = 0;
uint8_t decompressedFrame[FULL_FRAME_BYTES];

// CRC functions
uint8_t crc8(const uint8_t* data, size_t length) {
    uint8_t crc = 0;
    for (size_t i = 0; i < length; i++) {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x80) {
                crc = ((crc << 1) ^ 0x07) & 0xFF;
            } else {
                crc = (crc << 1) & 0xFF;
            }
        }
    }
    return crc;
}

uint16_t crc16(const uint8_t* data, size_t length) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; i++) {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x0001) {
                crc = (crc >> 1) ^ 0xA001;
            } else {
                crc >>= 1;
            }
        }
    }
    return crc & 0xFFFF;
}

// RLE декодирование
bool decodeFramePixels(const uint8_t* data, size_t length, uint8_t* output, size_t expectedBytes) {
    size_t readOffset = 0;
    size_t writeOffset = 0;
    uint32_t runCount = 0;
    uint32_t literalCount = 0;

    while (readOffset < length && writeOffset < expectedBytes) {
        if (readOffset >= length) break;
        
        uint8_t control = data[readOffset++];
        bool isRun = (control & 0x80) != 0;
        uint8_t count = (control & 0x7F) + 1;

        if (isRun) {
            runCount++;
            if (readOffset + 3 > length) {
                logPrintf("[ERROR] RLE run: not enough data at offset %d\n", (int)readOffset);
                return false;
            }
            uint8_t r = data[readOffset++];
            uint8_t g = data[readOffset++];
            uint8_t b = data[readOffset++];
            for (uint8_t i = 0; i < count; i++) {
                if (writeOffset + 3 > expectedBytes) {
                    logPrintf("[ERROR] RLE run: write overflow at offset %d, count %d\n", (int)writeOffset, (int)count);
                    return false;
                }
                output[writeOffset++] = r;
                output[writeOffset++] = g;
                output[writeOffset++] = b;
            }
        } else {
            literalCount++;
            size_t literalBytes = (size_t)count * 3;
            if (readOffset + literalBytes > length) {
                logPrintf("[ERROR] RLE literal: not enough data at offset %d, need %d\n", (int)readOffset, (int)literalBytes);
                return false;
            }
            if (writeOffset + literalBytes > expectedBytes) {
                logPrintf("[ERROR] RLE literal: write overflow at offset %d, need %d\n", (int)writeOffset, (int)literalBytes);
                return false;
            }
            memcpy(output + writeOffset, data + readOffset, literalBytes);
            readOffset += literalBytes;
            writeOffset += literalBytes;
        }
    }

    if (writeOffset != expectedBytes) {
        logPrintf("[ERROR] RLE incomplete: wrote %d of %d (runs: %d, literals: %d)\n", 
                  (int)writeOffset, (int)expectedBytes, (int)runCount, (int)literalCount);
    }
    return writeOffset == expectedBytes;
}

void logPrintln(const char* s) {
    Serial.println(s);
}

void logPrint(const char* s) {
    Serial.print(s);
}

void logPrintln(const __FlashStringHelper* s) {
    Serial.println(s);
}

void logPrint(const __FlashStringHelper* s) {
    Serial.print(s);
}

void logPrintf(const char* fmt, ...) {
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.print(buf);
}

// заголовок пакета v4 (9 байт)
struct PacketHeader {
    uint16_t sync;
    uint8_t version;
    uint8_t type;
    uint16_t length;
    uint16_t seq;
    uint8_t crc8;
};

// WebSocket event handler
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            logPrintln("[WS] Disconnected!");
            break;
        case WStype_CONNECTED:
            logPrintf("[WS] Connected to %s\n", payload);
            break;
        case WStype_BIN:
            processBinaryData(payload, length);
            break;
        case WStype_TEXT:
            logPrintf("[WS] Received text: %s\n", payload);
            break;
        default:
            break;
    }
}

void processBinaryData(uint8_t* data, size_t length) {
    if (bufferIndex + length > MAX_BUFFER_SIZE) {
        logPrintln("[ERROR] Buffer overflow!");
        bufferIndex = 0;
        return;
    }

    memcpy(wsBuffer + bufferIndex, data, length);
    bufferIndex += length;

    size_t processed = 0;
    while (processed < bufferIndex) {
        if (bufferIndex - processed < HEADER_SIZE) break;

        uint16_t sync;
        memcpy(&sync, wsBuffer + processed, sizeof(sync));
        if (sync != SYNC_MARKER) {
            logPrintf("[ERROR] Invalid sync marker: 0x%04X\n", sync);
            processed++;
            continue;
        }

        // парсим заголовок v4 (9 байт)
        PacketHeader header;
        header.sync = sync;
        header.version = wsBuffer[processed + 2];
        header.type = wsBuffer[processed + 3];
        uint16_t length_val;
        memcpy(&length_val, wsBuffer + processed + 4, sizeof(length_val));
        header.length = length_val;
        uint16_t seq_val;
        memcpy(&seq_val, wsBuffer + processed + 6, sizeof(seq_val));
        header.seq = seq_val;
        header.crc8 = wsBuffer[processed + 8];

        // проверяем CRC8 заголовка (первые 8 байт)
        uint8_t calculatedCrc = crc8(wsBuffer + processed, 8);
        if (calculatedCrc != header.crc8) {
            logPrintf("[ERROR] Header CRC mismatch: got 0x%02X, calc 0x%02X\n", header.crc8, calculatedCrc);
            processed++;
            continue;
        }

        size_t packetSize = HEADER_SIZE + header.length;

        if (processed + packetSize > bufferIndex) break;

        if (header.type == PACKET_TYPE_FRAME) {
            processFramePacket(wsBuffer + processed + HEADER_SIZE, header.length);
        } else if (header.type == PACKET_TYPE_LED_STRIP_FRAME) {
            processLedStripPacket(wsBuffer + processed + HEADER_SIZE, header.length);
        }

        processed += packetSize;
    }

    if (processed > 0) {
        memmove(wsBuffer, wsBuffer + processed, bufferIndex - processed);
        bufferIndex -= processed;
    }
}

void processFramePacket(uint8_t* payload, size_t length) {
    if (length < 3) {
        logPrintln("[ERROR] Frame payload too short");
        return;
    }

    uint16_t frameId;
    memcpy(&frameId, payload, sizeof(frameId));
    uint8_t frameFlags = payload[2];
    uint8_t* compressedData = payload + 3;
    size_t compressedSize = length - 3;

    if ((frameFlags & FRAME_FLAG_COMPRESSED) != 0) {
        memset(decompressedFrame, 0, FULL_FRAME_BYTES);
        if (!decodeFramePixels(compressedData, compressedSize, decompressedFrame, FULL_FRAME_BYTES)) {
            logPrintf("[ERROR] Failed to decode compressed frame, compressed size: %d\n", (int)compressedSize);
            return;
        }
        drawFrame(decompressedFrame, FULL_FRAME_BYTES);
    } else {
        if (compressedSize != FULL_FRAME_BYTES) {
            logPrintf("[ERROR] Uncompressed frame size mismatch: %d, expected %d\n", (int)compressedSize, (int)FULL_FRAME_BYTES);
            return;
        }
        drawFrame(compressedData, FULL_FRAME_BYTES);
    }
}

// обработка пакета LED ленты
void processLedStripPacket(uint8_t* payload, size_t length) {
    if (length < 3) {
        logPrintln("[ERROR] LED strip payload too short");
        return;
    }

    uint16_t frameId;
    memcpy(&frameId, payload, sizeof(frameId));
    uint8_t frameFlags = payload[2];
    uint8_t* pixelData = payload + 3;
    size_t pixelDataLen = length - 3;

    uint8_t* pixelsToDraw = pixelData;
    size_t bytesToDraw = pixelDataLen;

    if ((frameFlags & FRAME_FLAG_COMPRESSED) != 0) {
        // Пробуем разжать с максимальным количеством LED
        size_t expectedBytes = LED_STRIP_MAX_LEDS * 3;
        
        if (decodeFramePixels(pixelData, pixelDataLen, ledStripBuffer, expectedBytes)) {
            bytesToDraw = expectedBytes;
        } else {
            // Пробуем с меньшим количеством пикселей, если максимум не прошел
            bool decoded = false;
            for (size_t tryPixels = LED_STRIP_MAX_LEDS; tryPixels >= 1; tryPixels--) {
                size_t tryBytes = tryPixels * 3;
                if (decodeFramePixels(pixelData, pixelDataLen, ledStripBuffer, tryBytes)) {
                    bytesToDraw = tryBytes;
                    decoded = true;
                    break;
                }
            }
            if (!decoded) {
                logPrintln("[ERROR] Failed to decode LED strip frame");
                return;
            }
        }
        pixelsToDraw = ledStripBuffer;
    }

    drawLedStrip(pixelsToDraw, bytesToDraw);
}

// отрисовка LED ленты
void drawLedStrip(uint8_t* pixels, size_t pixelCount) {
    uint16_t numLeds = pixelCount / 3;
    if (numLeds > LED_STRIP_MAX_LEDS) {
        numLeds = LED_STRIP_MAX_LEDS;
    }
    
    currentLedCount = numLeds;
    
    for (uint16_t i = 0; i < numLeds; i++) {
        uint8_t r = pixels[i * 3];
        uint8_t g = pixels[i * 3 + 1];
        uint8_t b = pixels[i * 3 + 2];
        ledStrip[i] = CRGB(r, g, b);
    }
    
    FastLED.show();
}

// Рисуем кадр на дисплее
void drawFrame(uint8_t* pixels, size_t pixelCount) {
    if (pixelCount != FULL_FRAME_BYTES) {
        logPrintf("[ERROR] Frame size mismatch: %d, expected %d\n", (int)pixelCount, (int)FULL_FRAME_BYTES);
        return;
    }

    // Проверим первые пиксели верхней строки
    uint8_t r0 = pixels[0];
    uint8_t g0 = pixels[1];
    uint8_t b0 = pixels[2];
    logPrintf("[FRAME] First pixel: R=%d G=%d B=%d\n", r0, g0, b0);

    for (int y = 0; y < PANE_HEIGHT; y++) {
        for (int x = 0; x < PANE_WIDTH; x++) {
            int pixelIndex = (y * PANE_WIDTH + x) * 3;
            uint8_t r = pixels[pixelIndex];
            uint8_t g = pixels[pixelIndex + 1];
            uint8_t b = pixels[pixelIndex + 2];
            dma_display->drawPixelRGB888(x, y, r, b, g); // RBG порядок для этой панели
        }
    }

    dma_display->flipDMABuffer();
}

void setup() {
    Serial.begin(115200);

    logPrintln(F("ESP32 Matrix Display v4 (WebSocket)"));

    WiFi.begin(ssid, password);
    logPrint("Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        logPrint(".");
    }
    logPrintln("");
    logPrintln("WiFi connected");
    logPrint("IP: ");
    logPrintln(WiFi.localIP().toString().c_str());


    HUB75_I2S_CFG mxconfig;
    mxconfig.mx_height = PANEL_HEIGHT;
    mxconfig.chain_length = PANELS_NUMBER;

    dma_display = new MatrixPanel_I2S_DMA(mxconfig);
    dma_display->setBrightness8(150);

    if (!dma_display->begin()) {
        logPrintln("I2S memory allocation failed");
    }
    
    // тестовый паттерн
    dma_display->fillScreenRGB888(255, 0, 0);
    delay(500);
    dma_display->fillScreenRGB888(0, 255, 0);
    delay(500);
    dma_display->fillScreenRGB888(0, 0, 255);
    delay(500);
    dma_display->fillScreenRGB888(0, 0, 0);

    // инициализация LED ленты
    FastLED.addLeds<WS2812B, LED_STRIP_PIN, GRB>(ledStrip, LED_STRIP_MAX_LEDS);
    FastLED.setBrightness(150);
    FastLED.clear();
    FastLED.show();
    logPrintln("[LED] LED strip initialized");

    webSocket.begin(ws_host, ws_port, ws_path);
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
    logPrintln("[WS] WebSocket initialized");

    logPrintln("Setup complete");
}

void loop() {
    webSocket.loop();
}