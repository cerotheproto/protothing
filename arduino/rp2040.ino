#include <Arduino.h>
#include <DMD_RGB.h>
#include <SPI.h>
#include <Ethernet.h>
#include <EthernetUdp.h>

// ============================================================================
// HUB75 Panel Configuration for RP2040
// ============================================================================
#define DISPLAYS_ACROSS 2
#define DISPLAYS_DOWN   1
#define PANEL_WIDTH     64
#define PANEL_HEIGHT    32

// W5500 Pinout (GPx)
#define W5500_MISO 0
#define W5500_CS   1
#define W5500_SCK  2
#define W5500_MOSI 3
#define W5500_RST  4

// HUB75 Data pins (top / bottom half canvas)
#define DMD_PIN_R0 5
#define DMD_PIN_G0 6
#define DMD_PIN_B0 7
#define DMD_PIN_R1 8
#define DMD_PIN_G1 9
#define DMD_PIN_B1 10

// Address lines and signals
#define DMD_PIN_A 11
#define DMD_PIN_B 12
#define DMD_PIN_C 13
#define DMD_PIN_D 14
#define DMD_PIN_E 255

#define DMD_PIN_SCLK 15
#define DMD_PIN_LAT 26
#define DMD_PIN_nOE 27

// Data pins: CLK, R0, G0, B0, R1, G1, B1
uint8_t custom_rgbpins[] = { DMD_PIN_SCLK, DMD_PIN_R0, DMD_PIN_G0, DMD_PIN_B0, DMD_PIN_R1, DMD_PIN_G1, DMD_PIN_B1 };

// MUX pins
uint8_t mux_list[] = { DMD_PIN_A, DMD_PIN_B, DMD_PIN_C, DMD_PIN_D, DMD_PIN_E };

// Current display brightness
uint8_t currentBrightness = 150;

// Dual buffer enabled (last argument true)
DMD_RGB<RGB64x32plainS16, COLOR_4BITS> dmd(
    mux_list,
    DMD_PIN_nOE,
    DMD_PIN_LAT,
    custom_rgbpins,
    DISPLAYS_ACROSS,
    DISPLAYS_DOWN,
    true);
// ============================================================================
// W5500 Ethernet Configuration
// ============================================================================
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };
IPAddress ip(10, 0, 0, 10);
unsigned int localPort = 5555;

EthernetUDP udp;

// ============================================================================
// Protocol Configuration
// ============================================================================
#define PANE_WIDTH (PANEL_WIDTH * DISPLAYS_ACROSS)
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

#define FRAME_FLAG_COMPRESSED 0x01

// Commands
#define CMD_BRIGHTNESS 0x01

#define MAX_BUFFER_SIZE 65500

// All large buffers in global scope (heap), NOT on the stack
uint8_t inputBuffer[MAX_BUFFER_SIZE];
size_t bufferIndex = 0;
uint8_t discardBuffer[256];

// Packet header structure
struct PacketHeader {
    uint16_t sync;
    uint8_t version;
    uint8_t type;
    uint16_t length;
    uint16_t seq;
    uint8_t crc8;
};

struct FramePayload {
    uint16_t frameId;
    uint8_t frameFlags;
    uint8_t* pixels;
    size_t pixelCount;
};

// ============================================================================
// Shared State (Core 0 <-> Core 1)
// ============================================================================
uint8_t sharedFrameBuffer[FULL_FRAME_BYTES];
volatile bool isFrameReady = false;

volatile uint8_t sharedBrightness = 150;
volatile bool brightnessChanged = false;

// ============================================================================
// Forward Declarations
// ============================================================================
void processBinaryData();
void processFramePacket(uint8_t* payload, size_t length);
void processCmdPacket(uint8_t* payload, size_t length);
void updateDisplayFromBuffer();
bool queueFrame(const uint8_t* pixels, size_t pixelCount);
bool decodeFramePixels(const uint8_t* data, size_t length, uint8_t* output, size_t expectedBytes);
uint8_t crc8(const uint8_t* data, size_t length);
void drawTestPatterns();

void logPrintln(const char* s) { return; Serial.println(s); }
void logPrintf(const char* fmt, ...) {
    return; // Disable logging
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.print(buf);
}

// ============================================================================
// Setup & Loop (Core 0 - Networking)
// ============================================================================

void setup() {
    //Serial.begin(115200);

    //logPrintln("RP2040 DMD Matrix Display v4 (UDP/W5500) - Core 0");

    pinMode(W5500_RST, OUTPUT);
    digitalWrite(W5500_RST, LOW);
    delay(50);
    digitalWrite(W5500_RST, HIGH);
    delay(500);

    SPI.setRX(W5500_MISO);
    SPI.setCS(W5500_CS);
    SPI.setSCK(W5500_SCK);
    SPI.setTX(W5500_MOSI);
    SPI.begin();

    SPI.beginTransaction(SPISettings(80000000, MSBFIRST, SPI_MODE0));
    SPI.endTransaction();

    Ethernet.init(W5500_CS);
    Ethernet.begin(mac, ip);

    logPrintln("[ETH] Ethernet initialized with static IP");

    if (Ethernet.hardwareStatus() == EthernetNoHardware) {
        logPrintln("[WARN] W5500 hardware detection failed, but continuing anyway");
    }

    if (Ethernet.linkStatus() == LinkOFF) {
        logPrintln("[WARN] Ethernet cable not connected");
    } else {
        logPrintln("[ETH] Link detected");
    }

    logPrintf("[ETH] IP: %s\n", Ethernet.localIP().toString().c_str());

    udp.begin(localPort);
    logPrintf("[UDP] Port: %d\n", localPort);
}


void recoverSync() {
    // Scan for sync marker 0xAA55
    size_t foundAt = 0;
    bool found = false;
    
    // We need at least 2 bytes for sync
    if (bufferIndex < 2) {
        bufferIndex = 0;
        return;
    }

    for (size_t i = 0; i < bufferIndex - 1; i++) {
        if (inputBuffer[i] == 0x55 && inputBuffer[i+1] == 0xAA) { // Little Endian 0xAA55
           foundAt = i;
           found = true;
           break;
        }
    }

    if (found) {
        logPrintf("[WARN] Recovered sync at index %d\n", foundAt);
        memmove(inputBuffer, inputBuffer + foundAt, bufferIndex - foundAt);
        bufferIndex -= foundAt;
    } else {
        logPrintln("[WARN] No sync found in full buffer. Hard reset.");
        bufferIndex = 0;
    }
}

void loop() {
    int packetSize = udp.parsePacket();
    if (packetSize > 0) {
        if (packetSize > (int)MAX_BUFFER_SIZE) {
            logPrintln("[ERROR] UDP packet exceeds buffer, dropping");
            while (udp.available()) {
                udp.read(discardBuffer, min((int)sizeof(discardBuffer), udp.available()));
            }
            return;
        }

        size_t freeSpace = MAX_BUFFER_SIZE - bufferIndex;
        if ((size_t)packetSize > freeSpace) {
             // Instead of blind reset, try to recover space by finding next sync
             recoverSync();
             
             // Check again
             freeSpace = MAX_BUFFER_SIZE - bufferIndex;
             if ((size_t)packetSize > freeSpace) {
                logPrintln("[ERROR] Buffer full after sync recovery, dropping packet");
                while (udp.available()) {
                    udp.read(discardBuffer, min((int)sizeof(discardBuffer), udp.available()));
                }
                return;
             }
        }

        int bytesRead = udp.read(inputBuffer + bufferIndex, packetSize);
        if (bytesRead > 0) {
            bufferIndex += bytesRead;
            processBinaryData();
        }
    }

    Ethernet.maintain();
}

// ============================================================================
// Setup1 & Loop1 (Core 1 - Display Driving)
// ============================================================================

void setup1() {
    delay(100);
    dmd.init();
    dmd.setBrightness(currentBrightness);
    drawTestPatterns();
}

void loop1() {
    if (brightnessChanged) {
        dmd.setBrightness(sharedBrightness);
        brightnessChanged = false;
    }

    if (isFrameReady) {
        updateDisplayFromBuffer();
        isFrameReady = false;
    }

    delayMicroseconds(200);
}

// ============================================================================
// Drawing Functions
// ============================================================================

void updateDisplayFromBuffer() {
    if (!dmd.blitRGB888(PANE_WIDTH, PANE_HEIGHT, sharedFrameBuffer, FULL_FRAME_BYTES)) {
        logPrintln("[ERROR] blit failed");
        return;
    }
    dmd.swapBuffers(true);
}

void drawTestPatterns() {
    dmd.fillScreen(dmd.Color888(255, 0, 0));
    dmd.swapBuffers(true);
    delay(500);

    dmd.fillScreen(dmd.Color888(0, 255, 0));
    dmd.swapBuffers(true);
    delay(500);

    dmd.fillScreen(dmd.Color888(0, 0, 255));
    dmd.swapBuffers(true);
}

bool queueFrame(const uint8_t* pixels, size_t pixelCount) {
    if (pixelCount != FULL_FRAME_BYTES) {
        logPrintf("[ERROR] Frame size mismatch: %d, expected %d\n", (int)pixelCount, (int)FULL_FRAME_BYTES);
        return false;
    }

    if (pixels != sharedFrameBuffer) {
        memcpy(sharedFrameBuffer, pixels, FULL_FRAME_BYTES);
    }
    isFrameReady = true;
    return true;
}

void processBinaryData() {
    size_t processed = 0;
    while (processed < bufferIndex) {
        // Fast exit if not enough data for header
        if (bufferIndex - processed < HEADER_SIZE) break;

        // Peak sync marker first to avoid overhead
        uint16_t sync = *(uint16_t*)(inputBuffer + processed);
        if (sync != SYNC_MARKER) {
            processed++;
            continue;
        }


        PacketHeader header;
        header.sync = sync;
        header.version = inputBuffer[processed + 2];
        header.type = inputBuffer[processed + 3];
        header.length = *(uint16_t*)(inputBuffer + processed + 4);
        header.seq = *(uint16_t*)(inputBuffer + processed + 6);
        header.crc8 = inputBuffer[processed + 8];

        uint8_t calculatedCrc = crc8(inputBuffer + processed, 8);
        if (calculatedCrc != header.crc8) {
            //logPrintf("[ERROR] Header CRC mismatch: got 0x%02X, calc 0x%02X\n", header.crc8, calculatedCrc);
            processed++;
            continue;
        }

        size_t packetSize = HEADER_SIZE + header.length;

        if (processed + packetSize > bufferIndex) break;

        if (header.type == PACKET_TYPE_FRAME) {
            processFramePacket(inputBuffer + processed + HEADER_SIZE, header.length);
        } else if (header.type == PACKET_TYPE_CMD) {
            processCmdPacket(inputBuffer + processed + HEADER_SIZE, header.length);
        }

        processed += packetSize;
    }

    if (processed > 0) {
        memmove(inputBuffer, inputBuffer + processed, bufferIndex - processed);
        bufferIndex -= processed;
    }
}

void processFramePacket(uint8_t* payload, size_t length) {
    if (length < 3) return;

    FramePayload frame;
    frame.frameId = *(uint16_t*)payload;
    frame.frameFlags = payload[2];
    frame.pixels = payload + 3;
    frame.pixelCount = length - 3;

    if ((frame.frameFlags & FRAME_FLAG_COMPRESSED) != 0) {
        if (!decodeFramePixels(frame.pixels, frame.pixelCount, sharedFrameBuffer, FULL_FRAME_BYTES)) {
            logPrintln("[ERROR] Failed to decode compressed frame");
            return;
        }
        queueFrame(sharedFrameBuffer, FULL_FRAME_BYTES);
        return;
    }

    queueFrame(frame.pixels, frame.pixelCount);
}

void processCmdPacket(uint8_t* payload, size_t length) {
    if (length < 1) return;

    uint8_t cmdId = payload[0];
    uint8_t* cmdData = payload + 1;
    size_t cmdDataLen = length - 1;

    if (cmdId == CMD_BRIGHTNESS && cmdDataLen >= 1) {
        uint8_t brightness = cmdData[0];
        currentBrightness = brightness;
        sharedBrightness = brightness;
        brightnessChanged = true;
        logPrintf("[CMD] Brightness set to: %d\n", brightness);
    }
}

uint8_t crc8(const uint8_t* data, size_t length) {
    uint8_t crc = 0;
    for (size_t i = 0; i < length; i++) {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x80) crc = ((crc << 1) ^ 0x07) & 0xFF;
            else crc = (crc << 1) & 0xFF;
        }
    }
    return crc;
}

bool decodeFramePixels(const uint8_t* data, size_t length, uint8_t* output, size_t expectedBytes) {
    size_t readOffset = 0;
    size_t writeOffset = 0;

    while (readOffset < length && writeOffset < expectedBytes) {
        uint8_t control = data[readOffset++];
        bool isRun = (control & 0x80) != 0;
        uint8_t count = (control & 0x7F) + 1;

        if (isRun) {
            if (readOffset + 3 > length) return false;
            uint8_t r = data[readOffset++];
            uint8_t g = data[readOffset++];
            uint8_t b = data[readOffset++];
            for (uint8_t i = 0; i < count; i++) {
                if (writeOffset + 3 > expectedBytes) return false;
                output[writeOffset++] = r;
                output[writeOffset++] = g;
                output[writeOffset++] = b;
            }
        } else {
            size_t literalBytes = (size_t)count * 3;
            if (readOffset + literalBytes > length) return false;
            if (writeOffset + literalBytes > expectedBytes) return false;
            memcpy(output + writeOffset, data + readOffset, literalBytes);
            readOffset += literalBytes;
            writeOffset += literalBytes;
        }
    }
    return writeOffset == expectedBytes;
}
