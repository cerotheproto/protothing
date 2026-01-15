

#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
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
#define PANE_WIDTH (PANEL_WIDTH * PANELS_NUMBER)  // 128
#define PANE_HEIGHT PANEL_HEIGHT  // 32
#define FULL_FRAME_PIXELS (PANE_WIDTH * PANE_HEIGHT)  // 4096
#define FULL_FRAME_BYTES (FULL_FRAME_PIXELS * 3)  // 12288

// Protocol v4 constants
#define SYNC_MARKER 0xAA55
#define PROTOCOL_VERSION 0x04
#define HEADER_SIZE 9

#define TYPE_CMD 0x01
#define PACKET_TYPE_FRAME 0x02
#define FRAME_FLAG_COMPRESSED 0x01

#define CMD_BRIGHTNESS 0x01

#define MAX_BUFFER_SIZE 16384

MatrixPanel_I2S_DMA *dma_display = nullptr;
WebSocketsClient webSocket;

uint8_t wsBuffer[MAX_BUFFER_SIZE];
size_t bufferIndex = 0;
uint8_t decompressedFrame[FULL_FRAME_BYTES];

// CRC8 calculation (poly 0x07)
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

// RLE decode
bool decodeRLE(const uint8_t* data, size_t length, uint8_t* output, size_t expectedBytes) {
    size_t readOffset = 0;
    size_t writeOffset = 0;

    while (readOffset < length && writeOffset < expectedBytes) {
        uint8_t control = data[readOffset++];
        bool isRun = (control & 0x80) != 0;
        uint8_t count = (control & 0x7F) + 1;

        if (isRun) {
            if (readOffset + 3 > length) {
                logPrintf("[RLE] Run: not enough data at offset %d\n", (int)readOffset);
                return false;
            }
            uint8_t r = data[readOffset++];
            uint8_t g = data[readOffset++];
            uint8_t b = data[readOffset++];
            
            for (uint8_t i = 0; i < count; i++) {
                if (writeOffset + 3 > expectedBytes) {
                    logPrintf("[RLE] Run: write overflow\n");
                    return false;
                }
                output[writeOffset++] = r;
                output[writeOffset++] = g;
                output[writeOffset++] = b;
            }
        } else {
            size_t literalBytes = (size_t)count * 3;
            if (readOffset + literalBytes > length) {
                logPrintf("[RLE] Literal: not enough data\n");
                return false;
            }
            if (writeOffset + literalBytes > expectedBytes) {
                logPrintf("[RLE] Literal: write overflow\n");
                return false;
            }
            memcpy(output + writeOffset, data + readOffset, literalBytes);
            readOffset += literalBytes;
            writeOffset += literalBytes;
        }
    }

    return writeOffset == expectedBytes;
}

void logPrintf(const char* fmt, ...) {
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.print(buf);
}

struct PacketHeader {
    uint16_t sync;
    uint8_t version;
    uint8_t type;
    uint16_t length;
    uint16_t seq;
    uint8_t crc8;
};

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.println("[WS] Disconnected");
            break;
        case WStype_CONNECTED:
            Serial.println("[WS] Connected");
            break;
        case WStype_BIN:
            processBinaryData(payload, length);
            break;
        default:
            break;
    }
}

void processBinaryData(uint8_t* data, size_t length) {
    if (bufferIndex + length > MAX_BUFFER_SIZE) {
        Serial.println("[ERROR] Buffer overflow");
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
            processed++;
            continue;
        }

        // Parse header
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

        // Verify header CRC8
        uint8_t calculatedCrc = crc8(wsBuffer + processed, 8);
        if (calculatedCrc != header.crc8) {
            logPrintf("[ERROR] Header CRC mismatch\n");
            processed++;
            continue;
        }

        size_t packetSize = HEADER_SIZE + header.length;

        if (processed + packetSize > bufferIndex) break;

        if (header.type == PACKET_TYPE_FRAME) {
            processFramePacket(wsBuffer + processed + HEADER_SIZE, header.length);
        } else if (header.type == TYPE_CMD) {
            processCmdPacket(wsBuffer + processed + HEADER_SIZE, header.length);
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
        Serial.println("[ERROR] Frame payload too short");
        return;
    }

    uint16_t frameId;
    memcpy(&frameId, payload, sizeof(frameId));
    uint8_t frameFlags = payload[2];
    uint8_t* pixelData = payload + 3;
    size_t pixelDataLen = length - 3;

    if ((frameFlags & FRAME_FLAG_COMPRESSED) != 0) {
        memset(decompressedFrame, 0, FULL_FRAME_BYTES);
        if (!decodeRLE(pixelData, pixelDataLen, decompressedFrame, FULL_FRAME_BYTES)) {
            logPrintf("[ERROR] Failed to decode frame\n");
            return;
        }
        drawFrame(decompressedFrame, FULL_FRAME_BYTES);
    } else {
        if (pixelDataLen != FULL_FRAME_BYTES) {
            logPrintf("[ERROR] Uncompressed frame size mismatch: %d\n", (int)pixelDataLen);
            return;
        }
        drawFrame(pixelData, FULL_FRAME_BYTES);
    }
}

void processCmdPacket(uint8_t* payload, size_t length) {
    if (length < 1) {
        Serial.println("[ERROR] CMD payload too short");
        return;
    }
    
    uint8_t cmd_id = payload[0];
    uint8_t* cmd_data = payload + 1;
    size_t cmd_data_len = length - 1;
    
    if (cmd_id == CMD_BRIGHTNESS && cmd_data_len >= 1) {
        uint8_t brightness = cmd_data[0];
        dma_display->setBrightness8(brightness);
        logPrintf("[BRIGHTNESS] Set to %d\n", brightness);
    }
}

void drawFrame(uint8_t* pixels, size_t pixelCount) {
    if (pixelCount != FULL_FRAME_BYTES) {
        logPrintf("[ERROR] Frame size mismatch: %d\n", (int)pixelCount);
        return;
    }

    for (int y = 0; y < PANE_HEIGHT; y++) {
        for (int x = 0; x < PANE_WIDTH; x++) {
            int pixelIndex = (y * PANE_WIDTH + x) * 3;
            uint8_t r = pixels[pixelIndex];
            uint8_t g = pixels[pixelIndex + 1];
            uint8_t b = pixels[pixelIndex + 2];
            dma_display->drawPixelRGB888(x, y, r, b, g);
        }
    }

    dma_display->flipDMABuffer();
}

void setup() {
    Serial.begin(115200);

    Serial.println("ESP32 Display (Simplified)");

    WiFi.begin(ssid, password);
    Serial.print("Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("");
    Serial.println("WiFi connected");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP().toString().c_str());

    HUB75_I2S_CFG mxconfig;
    mxconfig.mx_height = PANEL_HEIGHT;
    mxconfig.chain_length = PANELS_NUMBER;

    dma_display = new MatrixPanel_I2S_DMA(mxconfig);
    dma_display->setBrightness8(150);

    if (!dma_display->begin()) {
        Serial.println("I2S memory allocation failed");
    }
    
    // Test pattern
    dma_display->fillScreenRGB888(255, 0, 0);
    delay(500);
    dma_display->fillScreenRGB888(0, 255, 0);
    delay(500);
    dma_display->fillScreenRGB888(0, 0, 255);
    delay(500);
    dma_display->fillScreenRGB888(0, 0, 0);

    webSocket.begin(ws_host, ws_port, ws_path);
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);

    Serial.println("Setup complete");
}

void loop() {
    webSocket.loop();
}
