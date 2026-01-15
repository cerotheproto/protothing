'use client';

import { BrightnessControl } from '@/components/BrightnessControl';

export default function SettingsPage() {
  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto w-full">
      <h1 className="text-3xl font-bold mb-8">Settings</h1>
      
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold mb-4">Display</h2>
          <BrightnessControl />
        </div>
      </div>
    </div>
  );
}