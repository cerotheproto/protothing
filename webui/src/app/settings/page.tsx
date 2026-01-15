'use client';

import { BrightnessControl } from '@/components/BrightnessControl';

export default function SettingsPage() {
  return (
    <div className="space-y-6 p-4">
      <div>
        <h1 className="text-2xl font-bold mb-4">Settings</h1>
      </div>
      
        <h2 className="text-lg font-semibold mb-4">Display</h2>
        <BrightnessControl />
      </div>
  );
}