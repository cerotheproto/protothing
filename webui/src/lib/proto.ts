export const SYNC_MARKER = 0xAA55;
export const PROTOCOL_VERSION = 0x04;

export function crc8(data: Uint8Array): number {
    let crc = 0;
    for (const byte of data) {
        crc ^= byte;
        for (let i = 0; i < 8; i++) {
            if (crc & 0x80) {
                crc = ((crc << 1) ^ 0x07) & 0xFF;
            } else {
                crc = (crc << 1) & 0xFF;
            }
        }
    }
    return crc;
}

export enum PacketType {
    CMD = 0x01,
    FRAME = 0x02,
    INFO = 0x03,
    LED = 0x05,
}

export enum FrameFlags {
    COMPRESSED = 1 << 0
}

// заголовок v4 - 9 байт (упрощенный для UDP)
export interface Header {
    sync: number;          // 2 bytes
    version: number;       // 1 byte
    type: PacketType;      // 1 byte
    length: number;        // 2 bytes
    seq: number;           // 2 bytes
    crc8: number;          // 1 byte  
}

export interface FramePayload {
    frameId: number;       // 2 bytes
    frameFlags: number;    // 1 byte
    pixels: Uint8Array;    // декодированные пиксели
}

export interface InfoPayload {
    fwVersion: number;     // 2 bytes
    brightness: number;    // 1 byte
}

const FULL_FRAME_PIXELS = 128 * 32;


// RLE сжатие RGB888 пикселей
export function rleEncode(pixels: Uint8Array): Uint8Array {
    if (pixels.length === 0 || pixels.length % 3 !== 0) {
        return pixels;
    }
    
    const result: number[] = [];
    const pixelCount = pixels.length / 3;
    let i = 0;
    
    while (i < pixelCount) {
        const r = pixels[i * 3];
        const g = pixels[i * 3 + 1];
        const b = pixels[i * 3 + 2];
        
        let runLength = 1;
        while (i + runLength < pixelCount && 
               runLength < 128 &&
               pixels[(i + runLength) * 3] === r &&
               pixels[(i + runLength) * 3 + 1] === g &&
               pixels[(i + runLength) * 3 + 2] === b) {
            runLength++;
        }
        
        if (runLength >= 3) {
            const control = 0x80 | (runLength - 1);
            result.push(control, r, g, b);
            i += runLength;
        } else {
            const literalStart = i;
            let literalCount = 0;
            
            while (i < pixelCount && literalCount < 128) {
                const r2 = pixels[i * 3];
                const g2 = pixels[i * 3 + 1];
                const b2 = pixels[i * 3 + 2];
                
                let runAhead = 1;
                while (i + runAhead < pixelCount && 
                       runAhead < 128 &&
                       pixels[(i + runAhead) * 3] === r2 &&
                       pixels[(i + runAhead) * 3 + 1] === g2 &&
                       pixels[(i + runAhead) * 3 + 2] === b2) {
                    runAhead++;
                }
                
                if (runAhead >= 3 && literalCount > 0) {
                    break;
                }
                
                literalCount++;
                i++;
            }
            
            if (literalCount > 0) {
                const control = literalCount - 1;
                result.push(control);
                for (let j = 0; j < literalCount * 3; j++) {
                    result.push(pixels[literalStart * 3 + j]);
                }
            }
        }
    }
    
    return new Uint8Array(result);
}


// RLE декодирование
export function rleDecode(data: Uint8Array, expectedPixels: number): Uint8Array {
    const result: number[] = [];
    const expectedBytes = expectedPixels * 3;
    let readOffset = 0;
    
    while (readOffset < data.length && result.length < expectedBytes) {
        const control = data[readOffset++];
        const isRun = (control & 0x80) !== 0;
        const count = (control & 0x7F) + 1;
        
        if (isRun) {
            if (readOffset + 3 > data.length) break;
            const r = data[readOffset++];
            const g = data[readOffset++];
            const b = data[readOffset++];
            for (let i = 0; i < count; i++) {
                result.push(r, g, b);
            }
        } else {
            const literalBytes = count * 3;
            if (readOffset + literalBytes > data.length) break;
            for (let i = 0; i < literalBytes; i++) {
                result.push(data[readOffset++]);
            }
        }
    }
    
    return new Uint8Array(result);
}


export class ProtocolParser {
    static parseHeader(arrayBuffer: ArrayBuffer): Header {
        if (arrayBuffer.byteLength < 9) {
            throw new Error("Buffer too small for header");
        }
        const view = new DataView(arrayBuffer);
        const header = {
            sync: view.getUint16(0, true),
            version: view.getUint8(2),
            type: view.getUint8(3),
            length: view.getUint16(4, true),
            seq: view.getUint16(6, true),
            crc8: view.getUint8(8),
        };

        const headerWithoutCrc = new Uint8Array(arrayBuffer, 0, 8);
        const calculatedCrc8 = crc8(headerWithoutCrc);
        if (calculatedCrc8 !== header.crc8) {
            throw new Error(`Header CRC8 mismatch`);
        }

        return header;
    }

    static parseFramePayload(arrayBuffer: ArrayBuffer): FramePayload {
        if (arrayBuffer.byteLength < 3) {
            throw new Error("Buffer too small for frame payload");
        }
        const view = new DataView(arrayBuffer);
        const frameId = view.getUint16(0, true);
        const frameFlags = view.getUint8(2);
        const pixelData = new Uint8Array(arrayBuffer, 3);
        
        let pixels: Uint8Array;
        if (frameFlags & FrameFlags.COMPRESSED) {
            pixels = rleDecode(pixelData, FULL_FRAME_PIXELS);
        } else {
            pixels = pixelData;
        }
        
        return { frameId, frameFlags, pixels };
    }

    static parseInfoPayload(arrayBuffer: ArrayBuffer): InfoPayload {
        if (arrayBuffer.byteLength < 3) {
            throw new Error("Buffer too small for info payload");
        }
        const view = new DataView(arrayBuffer);
        return {
            fwVersion: view.getUint16(0, true),
            brightness: view.getUint8(2),
        };
    }

    static async parsePacket(data: ArrayBuffer | Blob) {
        let arrayBuffer: ArrayBuffer;
        
        if (data instanceof Blob) {
            arrayBuffer = await data.arrayBuffer();
        } else {
            arrayBuffer = data;
        }
        
        const header = this.parseHeader(arrayBuffer.slice(0, 9));
        if (header.sync !== SYNC_MARKER) {
            throw new Error("Invalid sync marker");
        }
        if (header.version !== PROTOCOL_VERSION) {
            throw new Error("Unsupported protocol version");
        }

        const expectedLength = 9 + header.length;
        
        if (arrayBuffer.byteLength < expectedLength) {
            throw new Error(`Buffer too small`);
        }

        const payloadBuffer = arrayBuffer.slice(9, 9 + header.length);

        let parsedPayload;
        switch (header.type) {
            case PacketType.FRAME:
                parsedPayload = this.parseFramePayload(payloadBuffer);
                break;
            case PacketType.INFO:
                parsedPayload = this.parseInfoPayload(payloadBuffer);
                break;
            case PacketType.CMD:
                parsedPayload = new Uint8Array(payloadBuffer);
                break;
            case PacketType.LED:
                parsedPayload = new Uint8Array(payloadBuffer);
                break;
            default:
                console.log("Debug - header.type:", header.type, "available types:", PacketType);
                throw new Error(`Unknown packet type: ${header.type}`);
        }
        return { header, payload: parsedPayload };
    }
}


export class PacketBuilder {
    static buildPacket(
        type: PacketType,
        payload: Uint8Array,
        seq: number = 0,
        version: number = PROTOCOL_VERSION
    ): ArrayBuffer {
        const payloadLength = payload.length;
        const totalLength = 9 + payloadLength;
        
        const buffer = new ArrayBuffer(totalLength);
        const view = new DataView(buffer);
        
        view.setUint16(0, SYNC_MARKER, true);
        view.setUint8(2, version);
        view.setUint8(3, type);
        view.setUint16(4, payloadLength, true);
        view.setUint16(6, seq, true);
        
        const headerWithoutCrc = new Uint8Array(buffer, 0, 8);
        const headerCrc8 = crc8(headerWithoutCrc);
        view.setUint8(8, headerCrc8);
        
        const payloadView = new Uint8Array(buffer, 9, payloadLength);
        payloadView.set(payload);
        
        return buffer;
    }

    static buildFrame(
        frameId: number,
        pixels: Uint8Array,
        seq: number = 0,
        compress: boolean = true
    ): ArrayBuffer {
        let frameFlags = 0;
        let pixelData = pixels;
        
        if (compress) {
            const compressed = rleEncode(pixels);
            if (compressed.length < pixels.length) {
                pixelData = compressed;
                frameFlags |= FrameFlags.COMPRESSED;
            }
        }
        
        const payload = new Uint8Array(3 + pixelData.length);
        const view = new DataView(payload.buffer);
        view.setUint16(0, frameId, true);
        view.setUint8(2, frameFlags);
        payload.set(pixelData, 3);
        
        return this.buildPacket(PacketType.FRAME, payload, seq);
    }

    static buildInfo(
        fwVersion: number,
        brightness: number,
        seq: number = 0
    ): ArrayBuffer {
        const payload = new Uint8Array(3);
        const view = new DataView(payload.buffer);
        view.setUint16(0, fwVersion, true);
        view.setUint8(2, brightness);
        
        return this.buildPacket(PacketType.INFO, payload, seq);
    }

    static buildCmd(
        cmdId: number,
        cmdData: Uint8Array = new Uint8Array(0),
        seq: number = 0
    ): ArrayBuffer {
        const payload = new Uint8Array(1 + cmdData.length);
        payload[0] = cmdId;
        payload.set(cmdData, 1);
        
        return this.buildPacket(PacketType.CMD, payload, seq);
    }
}


