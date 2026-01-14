"use client";

import { useState, useEffect } from "react";
import { ProtocolParser, type FramePayload } from "@/lib/proto";
import { ButtonGroup } from "@/components/ui/button-group";
import { Button } from "@/components/ui/button";
import { setMirrorMode } from "@/lib/api/mirror";
const API_URL = process.env.NEXT_PUBLIC_API_URL;

const getWebSocketUrl = () => {
    if (!API_URL) return null;
    
    try {
        const urlObj = new URL(API_URL);
        const protocol = urlObj.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${urlObj.host}${urlObj.pathname}/ws`;
    } catch {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}${API_URL}/ws`;
    }
};

let ws: WebSocket | null = null;
let canvasL: HTMLCanvasElement | null = null;
let canvasR: HTMLCanvasElement | null = null;
const width = 128;
const height = 32;
const MIN_SCALE = 6;
const MAX_SCALE = 10;

function renderFrame(frame: FramePayload) {
    // splits frame into left and right
    const pixels = frame.pixels
    const leftPixels = new Uint8Array(width / 2 * height * 3);
    const rightPixels = new Uint8Array(width / 2 * height * 3);
    const FULL_W = width;
    const FULL_H = height;
    const PANEL_W = width / 2;

    for (let y = 0; y < FULL_H; y++) {
        for (let x = 0; x < PANEL_W; x++) {
            const srcIdxLeft = (y * FULL_W + x) * 3;
            const srcIdxRight = (y * FULL_W + x + PANEL_W) * 3;
            const dstIdx = (y * PANEL_W + x) * 3;

            leftPixels[dstIdx] = pixels[srcIdxLeft];
            leftPixels[dstIdx + 1] = pixels[srcIdxLeft + 1];
            leftPixels[dstIdx + 2] = pixels[srcIdxLeft + 2];

            rightPixels[dstIdx] = pixels[srcIdxRight];
            rightPixels[dstIdx + 1] = pixels[srcIdxRight + 1];
            rightPixels[dstIdx + 2] = pixels[srcIdxRight + 2];
        }
    }

    drawToCanvas(canvasL, leftPixels);
    drawToCanvas(canvasR, rightPixels);
}

function drawToCanvas(canvas: HTMLCanvasElement | null, pixels: Uint8Array) {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const imageData = ctx.createImageData(width / 2, height);
    const pixelCount = pixels.length / 3;
    for (let i = 0; i < pixelCount; i++) {
        imageData.data[i * 4] = pixels[i * 3];       // R
        imageData.data[i * 4 + 1] = pixels[i * 3 + 1]; // G
        imageData.data[i * 4 + 2] = pixels[i * 3 + 2]; // B
        imageData.data[i * 4 + 3] = 255;               // A
    }
    ctx.putImageData(imageData, 0, 0);
}
export default function PreviewPage() {
    const [scale, setScale] = useState(MAX_SCALE);

    useEffect(() => {
        const wsUrl = getWebSocketUrl();
        if (wsUrl) {
            ws = new WebSocket(wsUrl);
            ws.binaryType = "arraybuffer";
            
            ws.addEventListener("message", async (event) => {
                try {
                    const message = await ProtocolParser.parsePacket(event.data);
                    if (message.payload && typeof message.payload === "object" && "frameId" in message.payload) {
                        const frame = message.payload as FramePayload;
                        renderFrame(frame);
                    }
                }
                catch (e) {
                    console.error("Error parsing message:", e);
                }
            });
        }

        return () => {
            if (ws) ws.close();
        };
    }, []);

    useEffect(() => {
        const calculateScale = () => {
            const viewportWidth = window.innerWidth;
            const panelWidth = width / 2;
            const requiredWidth = panelWidth * MAX_SCALE + 40;

            if (viewportWidth < requiredWidth) {
                const newScale = Math.max(MIN_SCALE, (viewportWidth - 40) / panelWidth);
                setScale(newScale);
            } else {
                setScale(MAX_SCALE);
            }
        };

        calculateScale();
        window.addEventListener("resize", calculateScale);
        return () => window.removeEventListener("resize", calculateScale);
    }, []);

    return (
        <div className="flex flex-col gap-8 p-6 max-w-7xl mx-auto">
            <div className="flex flex-col md:flex-row gap-10">
                <canvas
                    ref={(el) => { canvasL = el; }}
                    width={width / 2}
                    height={height}
                    style={{ imageRendering: "pixelated", width: (width / 2) * scale, height: height * scale, border: "1px solid white" }}
                ></canvas>
                <canvas
                    ref={(el) => { canvasR = el; }}
                    width={width / 2}
                    height={height}
                    style={{ imageRendering: "pixelated", width: (width / 2) * scale, height: height * scale, border: "1px solid white" }}
                ></canvas>
            </div>
            <div className="flex flex-col gap-2 justify-center items-center">
                <p>Mirror mode:</p>
                <div className="flex">
                    <ButtonGroup>
                        <Button onClick={() => setMirrorMode('none')}>Off</Button>
                        <Button onClick={() => setMirrorMode('left')}>Left</Button>
                        <Button onClick={() => setMirrorMode('right')}>Right</Button>
                    </ButtonGroup>
                </div>
            </div>
        </div>
    );
}