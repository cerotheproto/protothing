const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function getBrightness(): Promise<number> {
  const response = await fetch(`${API_BASE}/brightness/`);
  if (!response.ok) {
    throw new Error('Failed to get brightness');
  }
  const data = await response.json();
  return data.brightness;
}

export async function setBrightness(level: number): Promise<void> {
  const response = await fetch(`${API_BASE}/brightness/${level}`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to set brightness');
  }
}
