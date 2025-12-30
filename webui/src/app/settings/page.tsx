'use client';

import { BrightnessControl } from '@/components/BrightnessControl';

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-4">Настройки</h1>
      </div>
      
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Дисплей</h2>
        <BrightnessControl />
      </div>
    </div>
  );
}