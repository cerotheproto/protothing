const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function setMirrorMode(mode: 'none' | 'left' | 'right' ): Promise<void> {
    const response = await fetch(`${API_URL}/display/mirror`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ mode }),
    });
    if (!response.ok) {
        throw new Error("Error setting mirror mode");
    }
}