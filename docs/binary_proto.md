# Protocol v4

All multi-byte fields are transmitted in Little Endian (LE) byte order.
Display frames are always sent as a complete canvas 128x32.

## Header (9 bytes)

| Offset | Size | Field | Description                                                |
| ------ | ---- | ----- | ---------------------------------------------------------- |
| 0      | 2B   | SYNC  | `0xAA55` - packet start marker                             |
| 2      | 1B   | VER   | protocol version (`0x04`)                                  |
| 3      | 1B   | TYPE  | packet type (see Packet Types)                             |
| 4      | 2B   | LEN   | payload length (LE)                                        |
| 6      | 2B   | SEQ   | packet sequence number (LE)                                |
| 8      | 1B   | CRC8  | header checksum (CRC-8 of first 8 bytes)                   |

## Packet Types

| Type | ID   | Name             | Description                      |
| ---- | ---- | ---------------- | -------------------------------- |
| CMD  | 0x01 | Command          | Device command                   |
| FRAME| 0x02 | Display Frame    | 128x32 display frame data        |
| INFO | 0x03 | Device Info      | Device information response      |
| LED_STRIP_FRAME | 0x05 | LED Strip Frame  | Variable-length RGB LED data |
| BUTTON | 0x06 | Button Event | Button press event               |

## Packet Format Details

### CMD (0x01)

Sends a command to the device.

| Field | Size | Description    |
|-------|------|-----------------|
| ID    | 1B   | Command ID      |
| DATA  | N    | Command data    |

### FRAME (0x02)

Sends a display frame (128x32 pixels).

| Field       | Size | Description              |
|-------------|------|--------------------------|
| FRAME_ID    | 2B   | Frame identifier (LE)    |
| FRAME_FLAGS | 1B   | Frame flags (see below)  |
| PIXELS      | N    | RGB888 pixel data        |

**Frame Flags:**

| Bit | Name       | Description     |
|-----|------------|-----------------|
| 0   | COMPRESSED | Pixels are RLE-compressed |

### INFO (0x03)

Device information response.

| Field      | Size | Description      |
|------------|------|------------------|
| BRIGHTNESS | 1B   | Current brightness (0-255) |

### LED_STRIP_FRAME (0x05)

Sends pixel data for an addressable LED strip (WS2812B, etc.).

| Field       | Size | Description              |
|-------------|------|--------------------------|
| FRAME_ID    | 2B   | Frame identifier (LE)    |
| FRAME_FLAGS | 1B   | Frame flags (see FRAME flags) |
| PIXELS      | N    | RGB888 pixel data        |

### BUTTON (0x06)

Button press event from device.

| Field     | Size | Description   |
|-----------|------|-----------------|
| BUTTON_ID | 1B   | Button ID      |

## RLE Compression

RLE (Run-Length Encoding) for RGB888 pixel data:

Each block starts with a control byte:
- **Run block** (control byte MSB = 1): Repeated pixels
  - Control format: `10xxxxxx` where `xxxxxx + 1` = repeat count
  - Followed by 3 bytes (R, G, B) to repeat
  - Example: `0x85` = repeat next 6 pixels

- **Literal block** (control byte MSB = 0): Raw pixel data
  - Control format: `0xxxxxxx` where `xxxxxxx + 1` = byte count
  - Followed by that many RGB triplets (bytes × 3)
  - Example: `0x02` = 3 raw pixels (9 bytes)

Maximum run length: 128 pixels
Maximum literal block: 128 pixels

Example:
```
0x82          # Run: 3 pixels
FF 00 00      # Red color
0x01          # Literal: 2 pixels
00 FF 00      # Green
00 00 FF      # Blue
```

## Checksum

**CRC-8** (polynomial 0x07, initial value 0x00)

Calculated over the first 8 bytes of the header (SYNC, VER, TYPE, LEN, SEQ).
Stored in byte 8 of the header.