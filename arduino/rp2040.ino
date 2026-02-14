#include <Arduino.h>
#include <DMD_RGB.h>
#include <SPI.h>
#include <Ethernet.h>
#include <EthernetUdp.h>

#define useRBG 1 // cheap P2.5 panlels have green/blue swapped, set to 0 for normal RGB

#define DISPLAYS_ACROSS 2
#define DISPLAYS_DOWN 1
#define PANEL_WIDTH 64
#define PANEL_HEIGHT 32

#define W5500_MISO 0
#define W5500_CS 1
#define W5500_SCK 2
#define W5500_MOSI 3
#define W5500_RST 4

#define DMD_PIN_R0 5
#define DMD_PIN_G0 6
#define DMD_PIN_B0 7
#define DMD_PIN_R1 8
#define DMD_PIN_G1 9
#define DMD_PIN_B1 10

#define DMD_PIN_A 11
#define DMD_PIN_B 12
#define DMD_PIN_C 13
#define DMD_PIN_D 14
#define DMD_PIN_E 255

#define DMD_PIN_SCLK 15
#define DMD_PIN_LAT 26
#define DMD_PIN_nOE 27

uint8_t custom_rgbpins[] = {DMD_PIN_SCLK, DMD_PIN_R0, DMD_PIN_G0, DMD_PIN_B0, DMD_PIN_R1, DMD_PIN_G1, DMD_PIN_B1};

uint8_t mux_list[] = {DMD_PIN_A, DMD_PIN_B, DMD_PIN_C, DMD_PIN_D, DMD_PIN_E};

uint8_t currentBrightness = 150;

DMD_RGB<RGB64x32plainS16, COLOR_4BITS> dmd(
    mux_list,
    DMD_PIN_nOE,
    DMD_PIN_LAT,
    custom_rgbpins,
    DISPLAYS_ACROSS,
    DISPLAYS_DOWN,
    true);

byte mac[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED};
IPAddress ip(10, 0, 0, 10);
unsigned int localPort = 5555;

EthernetUDP udp;

#define PANE_WIDTH (PANEL_WIDTH * DISPLAYS_ACROSS)
#define PANE_HEIGHT PANEL_HEIGHT
#define FULL_FRAME_PIXELS (PANE_WIDTH * PANE_HEIGHT)
#define FULL_FRAME_BYTES (FULL_FRAME_PIXELS * 3)

#define SYNC_MARKER 0xAA55
#define PROTOCOL_VERSION 0x05
#define HEADER_SIZE 13

#define PACKET_TYPE_CMD 0x01
#define PACKET_TYPE_FRAME 0x02
#define PACKET_TYPE_INFO 0x03
#define PACKET_TYPE_ACK 0x04

#define FRAME_FLAG_COMPRESSED 0x01

#define CMD_BRIGHTNESS 0x01

#define MAX_BUFFER_SIZE 65500

uint8_t inputBuffer[MAX_BUFFER_SIZE];
size_t bufferIndex = 0;
uint8_t discardBuffer[256];

struct PacketHeader
{
    uint16_t sync;
    uint8_t version;
    uint8_t type;
    uint16_t seq;
    uint16_t offset;
    uint16_t length;
    uint16_t totalLen;
    uint8_t crc8;
};

struct FramePayload
{
    uint16_t frameId;
    uint8_t frameFlags;
    uint8_t *pixels;
    size_t pixelCount;
};

// ============================================================================
// Shared State (Core 0 <-> Core 1)
// ============================================================================
uint8_t sharedFrameBuffer[FULL_FRAME_BYTES];
volatile bool isFrameReady = false;

volatile uint8_t sharedBrightness = 150;
volatile bool brightnessChanged = false;

uint8_t reassemblyBuffer[16384];
uint16_t currentReassemblyTotal = 0;
uint16_t currentReassemblySeq = 0;

// ============================================================================
// Forward Declarations
// ============================================================================
void processBinaryData();
void processFramePacket(uint8_t *payload, size_t length);
void processCmdPacket(uint8_t *payload, size_t length);
void updateDisplayFromBuffer();
bool queueFrame(const uint8_t *pixels, size_t pixelCount);
bool decodeFramePixels(const uint8_t *data, size_t length, uint8_t *output, size_t expectedBytes);
uint8_t crc8(const uint8_t *data, size_t length);
void drawTestPatterns();

void logPrintln(const char *s) { Serial.println(s); }
void logPrintf(const char *fmt, ...)
{
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

void setup()
{
    Serial.begin(115200);
    delay(1000);

    logPrintln("RP2040 DMD Matrix Display v5 (UDP/W5500) - Core 0");

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

    if (Ethernet.hardwareStatus() == EthernetNoHardware)
    {
        logPrintln("[WARN] W5500 hardware detection failed, but continuing anyway");
    }

    if (Ethernet.linkStatus() == LinkOFF)
    {
        logPrintln("[WARN] Ethernet cable not connected");
    }
    else
    {
        logPrintln("[ETH] Link detected");
    }

    logPrintf("[ETH] IP: %s\n", Ethernet.localIP().toString().c_str());

    udp.begin(localPort);
    logPrintf("[UDP] Port: %d\n", localPort);
}

void recoverSync()
{
    // Scan for sync marker 0xAA55
    size_t foundAt = 0;
    bool found = false;

    // We need at least 2 bytes for sync
    if (bufferIndex < 2)
    {
        bufferIndex = 0;
        return;
    }

    for (size_t i = 0; i < bufferIndex - 1; i++)
    {
        if (inputBuffer[i] == 0x55 && inputBuffer[i + 1] == 0xAA)
        { // Little Endian 0xAA55
            foundAt = i;
            found = true;
            break;
        }
    }

    if (found)
    {
        logPrintf("[WARN] Recovered sync at index %d\n", foundAt);
        memmove(inputBuffer, inputBuffer + foundAt, bufferIndex - foundAt);
        bufferIndex -= foundAt;
    }
    else
    {
        logPrintln("[WARN] No sync found in full buffer. Hard reset.");
        bufferIndex = 0;
    }
}

void loop()
{
    int packetSize = udp.parsePacket();
    if (packetSize > 0)
    {
        if (packetSize > (int)MAX_BUFFER_SIZE)
        {
            logPrintln("[ERROR] UDP packet exceeds buffer, dropping");
            while (udp.available())
            {
                udp.read(discardBuffer, min((int)sizeof(discardBuffer), udp.available()));
            }
            return;
        }

        size_t freeSpace = MAX_BUFFER_SIZE - bufferIndex;
        if ((size_t)packetSize > freeSpace)
        {
            // Instead of blind reset, try to recover space by finding next sync
            recoverSync();

            // Check again
            freeSpace = MAX_BUFFER_SIZE - bufferIndex;
            if ((size_t)packetSize > freeSpace)
            {
                logPrintln("[ERROR] Buffer full after sync recovery, dropping packet");
                while (udp.available())
                {
                    udp.read(discardBuffer, min((int)sizeof(discardBuffer), udp.available()));
                }
                return;
            }
        }

        int bytesRead = udp.read(inputBuffer + bufferIndex, packetSize);
        if (bytesRead > 0)
        {

            bufferIndex += bytesRead;
            processBinaryData();
        }
    }

    Ethernet.maintain();
}

// ============================================================================
// Setup1 & Loop1 (Core 1 - Display Driving)
// ============================================================================

void setup1()
{
    delay(100);
    dmd.init();
    dmd.setBrightness(currentBrightness);
    drawTestPatterns();
}

void loop1()
{
    if (brightnessChanged)
    {
        dmd.setBrightness(sharedBrightness);
        brightnessChanged = false;
    }

    if (isFrameReady)
    {
        updateDisplayFromBuffer();
        isFrameReady = false;
    }

    delayMicroseconds(200);
}

// ============================================================================
// Drawing Functions
// ============================================================================

void updateDisplayFromBuffer()
{
    if (!dmd.blitRGB888(PANE_WIDTH, PANE_HEIGHT, sharedFrameBuffer, FULL_FRAME_BYTES))
    {
        logPrintln("[ERROR] blit failed");
        return;
    }
    dmd.swapBuffers(true);
}

void drawTestPatterns()
{
    dmd.fillScreen(dmd.Color888(255, 0, 0));
    dmd.swapBuffers(true);
    delay(500);

    dmd.fillScreen(dmd.Color888(0, 255, 0));
    dmd.swapBuffers(true);
    delay(500);

    dmd.fillScreen(dmd.Color888(0, 0, 255));
    dmd.swapBuffers(true);
}

bool queueFrame(const uint8_t *pixels, size_t pixelCount)
{
    if (pixelCount != FULL_FRAME_BYTES)
    {
        return false;
    }

    if (pixels != sharedFrameBuffer)
    {
        for (size_t i = 0; i < FULL_FRAME_PIXELS; i++)
        {

            sharedFrameBuffer[i * 3 + 0] = pixels[i * 3 + 0]; // R
#if useRBG
            sharedFrameBuffer[i * 3 + 1] = pixels[i * 3 + 2]; // B
            sharedFrameBuffer[i * 3 + 2] = pixels[i * 3 + 1]; // G
#elif
            sharedFrameBuffer[i * 3 + 1] = pixels[i * 3 + 1]; // G
            sharedFrameBuffer[i * 3 + 2] = pixels[i * 3 + 2]; // B
#endif
        }
    }
    else
    {
    }
    isFrameReady = true;
    return true;
}

void processBinaryData()
{
    size_t processed = 0;
    while (processed < bufferIndex)
    {
        // Fast exit if not enough data for header
        if (bufferIndex - processed < HEADER_SIZE)
            break;

        // Peak sync marker first to avoid overhead
        uint16_t sync = *(uint16_t *)(inputBuffer + processed);
        if (sync != SYNC_MARKER)
        {
            processed++;
            continue;
        }

        PacketHeader header;
        header.sync = sync;
        header.version = inputBuffer[processed + 2];
        header.type = inputBuffer[processed + 3];
        header.seq = *(uint16_t *)(inputBuffer + processed + 4);
        header.offset = *(uint16_t *)(inputBuffer + processed + 6);
        header.length = *(uint16_t *)(inputBuffer + processed + 8);
        header.totalLen = *(uint16_t *)(inputBuffer + processed + 10);
        header.crc8 = inputBuffer[processed + 12];

        uint8_t calculatedCrc = crc8(inputBuffer + processed, 12);
        if (calculatedCrc != header.crc8)
        {
            logPrintf("[ERROR] Header CRC mismatch: got 0x%02X, calc 0x%02X\n", header.crc8, calculatedCrc);
            processed++;
            continue;
        }

        size_t packetSize = HEADER_SIZE + header.length;

        if (processed + packetSize > bufferIndex)
            break;

        if (header.type == PACKET_TYPE_FRAME)
        {
            if (header.offset == 0)
            {
                currentReassemblySeq = header.seq;
                currentReassemblyTotal = header.totalLen;
            }

            if (header.seq == currentReassemblySeq && header.totalLen == currentReassemblyTotal && header.totalLen <= sizeof(reassemblyBuffer))
            {
                if (header.offset + header.length <= header.totalLen)
                {
                    memcpy(reassemblyBuffer + header.offset, inputBuffer + processed + HEADER_SIZE, header.length);
                    if (header.offset + header.length == header.totalLen)
                    {
                        processFramePacket(reassemblyBuffer, header.totalLen);
                        currentReassemblyTotal = 0;
                    }
                }
            }
        }
        else if (header.type == PACKET_TYPE_CMD)
        {
            processCmdPacket(inputBuffer + processed + HEADER_SIZE, header.length);
        }

        processed += packetSize;
    }

    if (processed > 0)
    {
        memmove(inputBuffer, inputBuffer + processed, bufferIndex - processed);
        bufferIndex -= processed;
    }
}

void processFramePacket(uint8_t *payload, size_t length)
{
    if (length < 3)
    {
        logPrintln("[WARN] Frame payload too small");
        return;
    }

    FramePayload frame;
    frame.frameId = *(uint16_t *)payload;
    frame.frameFlags = payload[2];
    frame.pixels = payload + 3;
    frame.pixelCount = length - 3;

    if ((frame.frameFlags & FRAME_FLAG_COMPRESSED) != 0)
    {
        if (!decodeFramePixels(frame.pixels, frame.pixelCount, sharedFrameBuffer, FULL_FRAME_BYTES))
        {
            return;
        }
        isFrameReady = true;
        return;
    }

    queueFrame(frame.pixels, frame.pixelCount);
}

void processCmdPacket(uint8_t *payload, size_t length)
{
    if (length < 1)
        return;

    uint8_t cmdId = payload[0];
    uint8_t *cmdData = payload + 1;
    size_t cmdDataLen = length - 1;

    if (cmdId == CMD_BRIGHTNESS && cmdDataLen >= 1)
    {
        uint8_t brightness = cmdData[0];
        currentBrightness = brightness;
        sharedBrightness = brightness;
        brightnessChanged = true;
        logPrintf("[CMD] Brightness set to: %d\n", brightness);
    }
}

uint8_t crc8(const uint8_t *data, size_t length)
{
    uint8_t crc = 0;
    for (size_t i = 0; i < length; i++)
    {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++)
        {
            if (crc & 0x80)
                crc = ((crc << 1) ^ 0x07) & 0xFF;
            else
                crc = (crc << 1) & 0xFF;
        }
    }
    return crc;
}

bool decodeFramePixels(const uint8_t *data, size_t length, uint8_t *output, size_t expectedBytes)
{
    size_t readPos = 0;
    size_t writePos = 0;
    uint8_t inputChannels = 3;

    if (length > 14 && data[0] == 'q' && data[1] == 'o' && data[2] == 'i' && data[3] == 'f')
    {
        readPos = 14;
        uint32_t width = (data[4] << 24) | (data[5] << 16) | (data[6] << 8) | data[7];
        uint32_t height = (data[8] << 24) | (data[9] << 16) | (data[10] << 8) | data[11];
        inputChannels = data[12];
        uint8_t colorspace = data[13];
    }

    uint8_t r = 0, g = 0, b = 0, a = 255;
    uint8_t index[64][4];
    memset(index, 0, sizeof(index));

    while (readPos < length && writePos < expectedBytes)
    {
        uint8_t b1 = data[readPos++];

        if (b1 == 0xFE)
        {
            if (readPos + 3 > length)
                break;
            r = data[readPos++];
            g = data[readPos++];
            b = data[readPos++];
        }
        else if (b1 == 0xFF)
        {
            if (readPos + 4 > length)
                break;
            r = data[readPos++];
            g = data[readPos++];
            b = data[readPos++];
            a = data[readPos++];
        }
        else if ((b1 & 0xC0) == 0x00)
        {
            uint8_t idx = b1 & 0x3F;
            r = index[idx][0];
            g = index[idx][1];
            b = index[idx][2];
            a = index[idx][3];
        }
        else if ((b1 & 0xC0) == 0x40)
        {
            r += ((b1 >> 4) & 0x03) - 2;
            g += ((b1 >> 2) & 0x03) - 2;
            b += (b1 & 0x03) - 2;
        }
        else if ((b1 & 0xC0) == 0x80)
        {
            if (readPos + 1 > length)
                break;
            uint8_t b2 = data[readPos++];
            uint8_t vg = (b1 & 0x3F) - 32;
            r += vg - 8 + ((b2 >> 4) & 0x0F);
            g += vg;
            b += vg - 8 + (b2 & 0x0F);
        }
        else if ((b1 & 0xC0) == 0xC0)
        {
            uint8_t run = (b1 & 0x3F);
            for (int i = 0; i < run + 1; i++)
            {
                if (writePos + 3 > expectedBytes)
                    break;
                output[writePos++] = r;
#if useRBG
                output[writePos++] = b;
                output[writePos++] = g;
#elif
                output[writePos++] = g;
                output[writePos++] = b;
#endif
            }
            continue;
        }

        uint8_t indexPos = (r * 3 + g * 5 + b * 7 + a * 11) % 64;
        index[indexPos][0] = r;
        index[indexPos][1] = g;
        index[indexPos][2] = b;
        index[indexPos][3] = a;

        if (writePos + 3 <= expectedBytes)
        {
            output[writePos++] = r;
            output[writePos++] = b;
            output[writePos++] = g;
        }
    }

    return writePos == expectedBytes;
}
