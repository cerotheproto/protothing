/*
    This sketch is not tested on actual hardware at the moment, but I will test it later. I'll use it for my main setup
 */

#include <Arduino.h>
#include <DMD_RGB.h>
#include <FastLED.h>
#include <SPI.h>
#include <Ethernet.h>
#include <EthernetUdp.h>

// ============================================================================
// Конфигурация Панели (HUB75) для RP2040
// ============================================================================
#define DISPLAYS_ACROSS 2  // Количество панелей по горизонтали
#define DISPLAYS_DOWN   1  // Количество панелей по вертикали
#define PANEL_WIDTH     64
#define PANEL_HEIGHT    32

// Распиновка (GPx)
// W5500
#define W5500_MISO 0
#define W5500_CS   1
#define W5500_SCK  2
#define W5500_MOSI 3
#define W5500_RST  4

// HUB75 данные (верхняя / нижняя половина полотно)
#define DMD_PIN_R0 5
#define DMD_PIN_G0 6
#define DMD_PIN_B0 7
#define DMD_PIN_R1 8
#define DMD_PIN_G1 9
#define DMD_PIN_B1 10

// Кнопка (с подтяжкой к VCC, нажатие = LOW)
#define BUTTON_PIN 28

// Адресные линии и сигналы
#define DMD_PIN_A 11
#define DMD_PIN_B 12
#define DMD_PIN_C 13
#define DMD_PIN_D 14
#define DMD_PIN_E 255 // не используется 

#define DMD_PIN_SCLK 15 // CLK панели
#define DMD_PIN_LAT 26
#define DMD_PIN_nOE 27

// Пины данных: CLK, R0, G0, B0, R1, G1, B1
uint8_t custom_rgbpins[] = { DMD_PIN_SCLK, DMD_PIN_R0, DMD_PIN_G0, DMD_PIN_B0, DMD_PIN_R1, DMD_PIN_G1, DMD_PIN_B1 };

// Пины MUX
uint8_t mux_list[] = { DMD_PIN_A, DMD_PIN_B, DMD_PIN_C, DMD_PIN_D, DMD_PIN_E }; 

// Текущая яркость дисплея
uint8_t currentBrightness = 150; 

// Инициализация объекта DMD
DMD_RGB <RGB64x32plainS16, COLOR_4BITS> dmd(mux_list, DMD_PIN_nOE, DMD_PIN_SCLK, custom_rgbpins, DISPLAYS_ACROSS, DISPLAYS_DOWN, true); 
// true в конце включает двойную буферизацию

// ============================================================================
// Конфигурация W5500 Ethernet
// ============================================================================
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };
IPAddress ip(192, 168, 1, 10);
unsigned int localPort = 5555;

// Адрес хоста для отправки button пакетов
IPAddress hostIP;
unsigned int hostPort = 0;

EthernetUDP udp;

// ============================================================================
// Конфигурация LED ленты
// ============================================================================
#define LED_STRIP_PIN 29
#define LED_STRIP_MAX_LEDS 300
CRGB ledStrip[LED_STRIP_MAX_LEDS];
uint8_t ledStripBuffer[LED_STRIP_MAX_LEDS * 3];
uint16_t currentLedCount = 0;

// ============================================================================
// Обработка кнопки
// ============================================================================
bool lastButtonState = HIGH;
bool currentButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;

// ============================================================================
// Логика протокола и буферы
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
#define PACKET_TYPE_LED_STRIP_FRAME 0x05
#define PACKET_TYPE_BUTTON 0x06

#define FRAME_FLAG_COMPRESSED 0x01

// Команды
#define CMD_BRIGHTNESS 0x01

#define MAX_BUFFER_SIZE 32768 // Увеличил, так как у RP2040 много RAM (264KB)
uint8_t inputBuffer[MAX_BUFFER_SIZE];
size_t bufferIndex = 0;
uint8_t decompressedFrame[FULL_FRAME_BYTES];

// Структуры пакетов
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
// Forward Declarations
// ============================================================================
void processBinaryData(uint8_t* data, size_t length);
void processFramePacket(uint8_t* payload, size_t length);
void processLedStripPacket(uint8_t* payload, size_t length);
void processCmdPacket(uint8_t* payload, size_t length);
void drawFrame(uint8_t* pixels, size_t pixelCount);
void drawLedStrip(uint8_t* pixels, size_t pixelCount);
bool decodeFramePixels(const uint8_t* data, size_t length, uint8_t* output, size_t expectedBytes);
uint8_t crc8(const uint8_t* data, size_t length);
uint16_t crc16(const uint8_t* data, size_t length);
void sendButtonPacket(uint8_t buttonId);
void checkButton();

void logPrintln(const char* s) { Serial.println(s); }
void logPrintf(const char* fmt, ...) {
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.print(buf);
}

// ============================================================================
// Setup & Loop
// ============================================================================

void setup() {
    Serial.begin(115200);

    logPrintln("RP2040 DMD_STM32 Display v4 (UDP/W5500)");

    // Инициализация W5500 (используем указанные GP0..GP4)
    // Аппаратный ресет модуля
    pinMode(W5500_RST, OUTPUT);
    digitalWrite(W5500_RST, LOW);
    delay(50);
    digitalWrite(W5500_RST, HIGH);
    delay(250);

    // Инициализация SPI на нужных ножках и CS для W5500
    SPI.begin(W5500_SCK, W5500_MISO, W5500_MOSI);
    Ethernet.init(W5500_CS);

    if (!Ethernet.begin(mac, ip)) {
        logPrintln("[ERROR] Не удалось получить IP для W5500");
        // продолжим, но сообщим об ошибке
    }
    
    if (Ethernet.hardwareStatus() == EthernetNoHardware) {
        logPrintln("[ERROR] W5500 не найден!");
        while (true) { delay(1); }
    }

    logPrintf("[ETH] IP: %s\n", Ethernet.localIP().toString().c_str());

    udp.begin(localPort);
    logPrintf("[UDP] Порт: %d\n", localPort);

    // Инициализация DMD
    dmd.init();
    dmd.setBrightness(currentBrightness);

    // Тестовый паттерн при запуске
    dmd.fillScreen(dmd.Color888(255, 0, 0)); delay(500);
    dmd.fillScreen(dmd.Color888(0, 255, 0)); delay(500);
    dmd.fillScreen(dmd.Color888(0, 0, 255)); delay(500);
    dmd.fillScreen(dmd.Color888(0, 0, 0));

    // Инициализация LED ленты
    FastLED.addLeds<WS2812B, LED_STRIP_PIN, GRB>(ledStrip, LED_STRIP_MAX_LEDS);
    FastLED.setBrightness(150);
    FastLED.clear();
    FastLED.show();
    logPrintln("[LED] LED strip initialized");
    
    // Инициализация кнопки
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    logPrintln("[BUTTON] Button initialized");
}

void loop() {
    // Проверяем кнопку
    checkButton();
    
    // Проверяем UDP пакеты (polling)
    int packetSize = udp.parsePacket();
    if (packetSize > 0) {
        // Сохраняем адрес хоста для ответных пакетов
        hostIP = udp.remoteIP();
        hostPort = udp.remotePort();
        
        uint8_t chunk[2048];
        size_t toRead = min(packetSize, (int)sizeof(chunk));
        int bytesRead = udp.read(chunk, toRead);
        
        if (bytesRead > 0) {
            processBinaryData(chunk, bytesRead);
        }
    }

    // Поддержка Ethernet
    Ethernet.maintain();
}

// ============================================================================
// Функции отрисовки
// ============================================================================

// Рисуем кадр на дисплее
void drawFrame(uint8_t* pixels, size_t pixelCount) {
    if (pixelCount != FULL_FRAME_BYTES) {
        logPrintf("[ERROR] Frame size mismatch: %d, expected %d\n", (int)pixelCount, (int)FULL_FRAME_BYTES);
        return;
    }

    for (int y = 0; y < PANE_HEIGHT; y++) {
        for (int x = 0; x < PANE_WIDTH; x++) {
            int pixelIndex = (y * PANE_WIDTH + x) * 3;
            uint8_t r = pixels[pixelIndex];
            uint8_t g = pixels[pixelIndex + 1];
            uint8_t b = pixels[pixelIndex + 2];
            
            dmd.drawPixel(x, y, dmd.Color888(r, g, b));
        }
    }
    

    dmd.swapBuffers(); 
}

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

void processBinaryData(uint8_t* data, size_t length) {
    if (bufferIndex + length > MAX_BUFFER_SIZE) {
        logPrintln("[ERROR] Buffer overflow!");
        bufferIndex = 0;
        return;
    }

    memcpy(inputBuffer + bufferIndex, data, length);
    bufferIndex += length;

    size_t processed = 0;
    while (processed < bufferIndex) {
        if (bufferIndex - processed < HEADER_SIZE) break;

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
            logPrintf("[ERROR] Header CRC mismatch: got 0x%02X, calc 0x%02X\n", header.crc8, calculatedCrc);
            processed++;
            continue;
        }

        size_t packetSize = HEADER_SIZE + header.length;

        if (processed + packetSize > bufferIndex) break;

        if (header.type == PACKET_TYPE_FRAME) {
            processFramePacket(inputBuffer + processed + HEADER_SIZE, header.length);
        } else if (header.type == PACKET_TYPE_LED_STRIP_FRAME) {
            processLedStripPacket(inputBuffer + processed + HEADER_SIZE, header.length);
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

    uint8_t* pixelsToDraw = frame.pixels;
    size_t bytesToDraw = frame.pixelCount;

    if ((frame.frameFlags & FRAME_FLAG_COMPRESSED) != 0) {
        if (!decodeFramePixels(frame.pixels, frame.pixelCount, decompressedFrame, FULL_FRAME_BYTES)) {
            logPrintln("[ERROR] Failed to decode compressed frame");
            return;
        }
        pixelsToDraw = decompressedFrame;
        bytesToDraw = FULL_FRAME_BYTES;
    }

    drawFrame(pixelsToDraw, bytesToDraw);
}

void processLedStripPacket(uint8_t* payload, size_t length) {
    if (length < 3) return;

    uint8_t frameFlags = payload[2];
    uint8_t* pixelData = payload + 3;
    size_t pixelDataLen = length - 3;

    uint8_t* pixelsToDraw = pixelData;
    size_t bytesToDraw = pixelDataLen;

    if ((frameFlags & FRAME_FLAG_COMPRESSED) != 0) {
        size_t maxPixels = LED_STRIP_MAX_LEDS;
        size_t expectedBytes = maxPixels * 3;
        
        if (!decodeFramePixels(pixelData, pixelDataLen, ledStripBuffer, expectedBytes)) {
             // Попытка декодировать меньшее количество
            for (size_t tryPixels = maxPixels; tryPixels >= 1; tryPixels--) {
                if (decodeFramePixels(pixelData, pixelDataLen, ledStripBuffer, tryPixels * 3)) {
                    bytesToDraw = tryPixels * 3;
                    break;
                }
            }
             // Ошибка уже не обрабатывается детально, просто рисуем что вышло
        } else {
            bytesToDraw = expectedBytes;
        }
        pixelsToDraw = ledStripBuffer;
    }

    drawLedStrip(pixelsToDraw, bytesToDraw);
}

void processCmdPacket(uint8_t* payload, size_t length) {
    if (length < 1) return;

    uint8_t cmdId = payload[0];
    uint8_t* cmdData = payload + 1;
    size_t cmdDataLen = length - 1;

    if (cmdId == CMD_BRIGHTNESS && cmdDataLen >= 1) {
        uint8_t brightness = cmdData[0];
        currentBrightness = brightness;
        dmd.setBrightness(brightness);
        logPrintf("[CMD] Brightness set to: %d\n", brightness);
    }
}

// ============================================================================
// Утилиты (CRC, RLE)
// ============================================================================

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

uint16_t crc16(const uint8_t* data, size_t length) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; i++) {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x0001) crc = (crc >> 1) ^ 0xA001;
            else crc >>= 1;
        }
    }
    return crc & 0xFFFF;
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

// ============================================================================
// Обработка кнопки
// ============================================================================

void checkButton() {
    int reading = digitalRead(BUTTON_PIN);
    
    if (reading != lastButtonState) {
        lastDebounceTime = millis();
    }
    
    if ((millis() - lastDebounceTime) > debounceDelay) {
        if (reading != currentButtonState) {
            currentButtonState = reading;
            
            // Отправляем пакет при нажатии (LOW = нажата)
            if (currentButtonState == LOW) {
                logPrintln("[BUTTON] Button pressed!");
                sendButtonPacket(0); // ID кнопки = 0
            }
        }
    }
    
    lastButtonState = reading;
}

void sendButtonPacket(uint8_t buttonId) {
    // Проверяем что есть адрес хоста
    if (hostPort == 0) {
        logPrintln("[BUTTON] No host address, skipping");
        return;
    }
    
    // Формируем пакет с типом PACKET_TYPE_BUTTON
    // Заголовок: SYNC(2), VER(1), TYPE(1), LEN(2), SEQ(2), CRC8(1)
    // Payload: button_id(1)
    
    uint8_t packet[HEADER_SIZE + 1];
    static uint16_t seq = 0;
    
    // Формируем заголовок без CRC8
    packet[0] = SYNC_MARKER & 0xFF;
    packet[1] = (SYNC_MARKER >> 8) & 0xFF;
    packet[2] = PROTOCOL_VERSION;
    packet[3] = PACKET_TYPE_BUTTON;
    packet[4] = 1; // length = 1 байт (button_id)
    packet[5] = 0;
    packet[6] = seq & 0xFF;
    packet[7] = (seq >> 8) & 0xFF;
    
    // Вычисляем CRC8 для заголовка
    uint8_t headerCrc = crc8(packet, 8);
    packet[8] = headerCrc;
    
    // Добавляем payload
    packet[9] = buttonId;
    
    // Отправляем через UDP на сохраненный адрес хоста
    udp.beginPacket(hostIP, hostPort);
    udp.write(packet, HEADER_SIZE + 1);
    udp.endPacket();
    
    seq++;
    
    logPrintf("[BUTTON] Sent button packet: id=%d, seq=%d to %s:%d\n", 
              buttonId, seq - 1, hostIP.toString().c_str(), hostPort);
}