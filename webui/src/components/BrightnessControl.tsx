'use client';

import { useEffect, useState } from 'react';
import { getBrightness, setBrightness } from '@/lib/api/brightness';

export function BrightnessControl() {
  const [brightness, setBrightnessValue] = useState(255);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadBrightness();
  }, []);

  const loadBrightness = async () => {
    try {
      setIsLoading(true);
      const value = await getBrightness();
      setBrightnessValue(value);
    } catch (error) {
      console.error('Failed to load brightness:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value);
    setBrightnessValue(value);
  };

  const handleChangeEnd = async () => {
    try {
      await setBrightness(brightness);
    } catch (error) {
      console.error('Failed to set brightness:', error);
      await loadBrightness();
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium">Яркость</label>
        <span className="text-sm text-gray-500">{brightness}</span>
      </div>
      <input
        type="range"
        min="0"
        max="255"
        value={brightness}
        onChange={handleChange}
        onMouseUp={handleChangeEnd}
        onTouchEnd={handleChangeEnd}
        disabled={isLoading}
        className="w-full cursor-pointer"
      />
    </div>
  );
}
