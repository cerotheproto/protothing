import { decode } from '@jsquash/qoi';

export const SYNC_MARKER = 0xAA55;
export const PROTOCOL_VERSION = 0x05;

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

// заголовок v5 - 13 байт
export interface Header {
    sync: number;          // 2 bytes
    version: number;       // 1 byte
    type: PacketType;      // 1 byte
    seq: number;           // 2 bytes
    offset: number;        // 2 bytes
    length: number;        // 2 bytes
    totalLen: number;      // 2 bytes
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

export class ProtocolParser {
    static parseHeader(arrayBuffer: ArrayBuffer): Header {
        if (arrayBuffer.byteLength < 13) {
            throw new Error("Buffer too small for header");
        }
        const view = new DataView(arrayBuffer);
        const header = {
            sync: view.getUint16(0, true),
            version: view.getUint8(2),
            type: view.getUint8(3),
            seq: view.getUint16(4, true),
            offset: view.getUint16(6, true),
            length: view.getUint16(8, true),
            totalLen: view.getUint16(10, true),
            crc8: view.getUint8(12),
        };

        const headerWithoutCrc = new Uint8Array(arrayBuffer, 0, 12);
        const calculatedCrc8 = crc8(headerWithoutCrc);
        if (calculatedCrc8 !== header.crc8) {
             console.warn("CRC8 mismatch", calculatedCrc8, header.crc8);
        }

        return header;
    }

    static async parseFramePayload(arrayBuffer: ArrayBuffer): Promise<FramePayload> {
        if (arrayBuffer.byteLength < 3) {
            throw new Error("Buffer too small for frame payload");
        }
        const view = new DataView(arrayBuffer);
        const frameId = view.getUint16(0, true);
        const frameFlags = view.getUint8(2);
        const pixelData = new Uint8Array(arrayBuffer, 3);
        
        let pixels: Uint8Array;
        if (frameFlags & FrameFlags.COMPRESSED) {
            const qoiBuffer = arrayBuffer.slice(3);
            const decoded = await decode(qoiBuffer);
            

            const count = decoded.width * decoded.height;
            pixels = new Uint8Array(count * 3);
            const sourceData = decoded.data;
            
            for (let i = 0; i < count; i++) {
                pixels[i * 3] = sourceData[i * 4];         // R
                pixels[i * 3 + 1] = sourceData[i * 4 + 1]; // G
                pixels[i * 3 + 2] = sourceData[i * 4 + 2]; // B
            }
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
        
        const HEADER_SIZE = 13;
        
        if (arrayBuffer.byteLength < HEADER_SIZE) {
             throw new Error("Packet too small");
        }

        const header = this.parseHeader(arrayBuffer);
        
        const expectedLength = HEADER_SIZE + header.length;
        if (arrayBuffer.byteLength < expectedLength) {
             console.warn("Buffer smaller than expected header length");
        }

        const payloadBuffer = arrayBuffer.slice(HEADER_SIZE, HEADER_SIZE + header.length);

        if (header.offset !== 0 || header.length !== header.totalLen) {
             console.warn("Chunked packet received in WS, reassembly not implemented here yet");
        }

        let parsedPayload;
        try {
            switch (header.type) {
                case PacketType.FRAME:
                    parsedPayload = await this.parseFramePayload(payloadBuffer);
                    break;
                case PacketType.INFO:
                    parsedPayload = this.parseInfoPayload(payloadBuffer);
                    break;
                case PacketType.CMD:
                    parsedPayload = new Uint8Array(payloadBuffer);
                    break;
                case PacketType.LED:
                    parsedPayload = await this.parseFramePayload(payloadBuffer);
                    break;
                default:
                    console.log("Debug - header.type:", header.type);
                    parsedPayload = new Uint8Array(payloadBuffer);
            }
        } catch (e) {
            console.error("Payload parse error:", e);
            parsedPayload = new Uint8Array(payloadBuffer);
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
        const totalLength = 13 + payloadLength;
        
        const buffer = new ArrayBuffer(totalLength);
        const view = new DataView(buffer);
        
        view.setUint16(0, SYNC_MARKER, true);
        view.setUint8(2, version);
        view.setUint8(3, type);
        view.setUint16(4, seq, true);
        view.setUint16(6, 0, true);
        view.setUint16(8, payloadLength, true);
        view.setUint16(10, payloadLength, true);
        
        const headerWithoutCrc = new Uint8Array(buffer, 0, 12);
        const crc = crc8(headerWithoutCrc);
        view.setUint8(12, crc);
        
        const packetPayload = new Uint8Array(buffer, 13);
        packetPayload.set(payload);
        
        return buffer;
    }
}



