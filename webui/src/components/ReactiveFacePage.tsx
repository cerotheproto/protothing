"use client";

import { useState, useEffect } from "react";
import { emitEvent, executeQuery } from "@/lib/api/events";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Spinner } from "@/components/ui/spinner";
import { ButtonGroup, ButtonGroupItem } from "@/components/ui/button-group";

interface FaceState {
  preset: string;
  presets: string[];
  states: Record<string, { ref: string; state: string }>;
  audio_reactive: boolean;
  blinking: boolean;
  available_parts: Record<string, Array<{ ref: string; states: string[] }>>;
}

export function ReactiveFacePage({ activeApp }: { activeApp: string }) {
  const [faceState, setFaceState] = useState<FaceState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const normalizeFaceState = (data: FaceState) => ({
    ...data,
    presets: [...data.presets],
    states: { ...data.states },
    available_parts: { ...data.available_parts },
  }); // Создаем новый объект, чтобы реакт отследил обновление

  const loadFaceState = async () => {
    try {
      const result = await executeQuery(activeApp, "GetFaceState");
      setFaceState(normalizeFaceState(result));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error loading state");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadFaceState();
  }, [activeApp]);

  const handleChangeFaceState = async (partType: string, newState: string) => {
    setFaceState((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        states: {
          ...prev.states,
          [partType]: {
            ...prev.states[partType],
            state: newState,
          },
        },
      };
    });
    setIsSubmitting(true);
    try {
      await emitEvent("ChangeFaceState", { part_type: partType, new_state: newState });
      toast.success("State changed");
      await new Promise((resolve) => setTimeout(resolve, 100));
      await loadFaceState();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
      await loadFaceState();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOverrideFacePart = async (partType: string, ref: string, state: string = "default") => {
    setFaceState((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        states: {
          ...prev.states,
          [partType]: {
            ref,
            state,
          },
        },
      };
    });
    setIsSubmitting(true);
    try {
      await emitEvent("OverrideFacePart", { part_type: partType, ref, state });
      toast.success("Face part changed");
      await new Promise((resolve) => setTimeout(resolve, 100));
      await loadFaceState();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
      await loadFaceState();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggle = async (eventName: string, enabled: boolean) => {
    setFaceState((prev) => {
      if (!prev) return null;
      const newState = { ...prev };
      if (eventName === "SetBlinking") newState.blinking = enabled;
      if (eventName === "SetAudioReactive") newState.audio_reactive = enabled;
      return newState;
    });
    setIsSubmitting(true);
    try {
      await emitEvent(eventName, { enabled });
      toast.success(enabled ? "Enabled" : "Disabled");
      await new Promise((resolve) => setTimeout(resolve, 100));
      await loadFaceState();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
      await loadFaceState();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReload = async () => {
    setIsSubmitting(true);
    try {
      await emitEvent("ReloadMetadata", {});
      toast.success("Metadata reloaded");
      await loadFaceState();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChangePreset = async (presetName: string) => {
    setFaceState((prev) => {
      if (!prev) return null;
      return { ...prev, preset: presetName };
    });
    setIsSubmitting(true);
    try {
      await emitEvent("ChangePreset", { preset_name: presetName });
      toast.success("Preset changed");
      await new Promise((resolve) => setTimeout(resolve, 200));
      await loadFaceState();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
      await loadFaceState();
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Spinner />
      </div>
    );
  }

  if (!faceState) {
    return (
      <div className="p-8">
        <p className="text-muted-foreground">Failed to load state</p>
      </div>
    );
  }

  const partTypes = Object.keys(faceState.available_parts || {});

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">Reactive Face</h1>
          <p className="text-muted-foreground">Preset: {faceState.preset || "not set"}</p>
        </div>

      </div>

      <Tabs defaultValue="parts" className="w-full">
        <TabsList>
          <TabsTrigger value="parts">Face Parts</TabsTrigger>
          <TabsTrigger value="states">States</TabsTrigger>
          <TabsTrigger value="presets">Presets</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="parts" className="mt-8">
          <div className="space-y-6">
            {partTypes.map((partType) => {
              const parts = faceState.available_parts[partType] || [];
              const currentPart = faceState.states[partType];
              
              return (
                <div key={partType} className="border rounded-lg p-4">
                  <Label className="text-base font-medium capitalize mb-3 block">
                    {partType}
                  </Label>
                  {currentPart && (
                    <p className="text-xs text-muted-foreground mb-3">
                      Current: {currentPart.ref} ({currentPart.state})
                    </p>
                  )}
                  <ButtonGroup>
                    {parts.map((part) => (
                      <ButtonGroupItem
                        key={`${partType}-${part.ref}-${currentPart?.ref}`}
                        active={currentPart?.ref === part.ref}
                        onClick={() => handleOverrideFacePart(partType, part.ref)}
                        disabled={isSubmitting}
                      >
                        {part.ref}
                      </ButtonGroupItem>
                    ))}
                  </ButtonGroup>
                </div>
              );
            })}
          </div>
        </TabsContent>

        <TabsContent value="states" className="mt-8">
          <div className="space-y-6">
            {partTypes.map((partType) => {
              const currentPart = faceState.states[partType];
              if (!currentPart) return null;

              const parts = faceState.available_parts[partType] || [];
              const part = parts.find((p) => p.ref === currentPart.ref);
              const states = part?.states || [];

              if (states.length === 0) return null;

              return (
                <div key={partType} className="border rounded-lg p-4">
                  <Label className="text-base font-medium capitalize mb-3 block">
                    {partType} - {currentPart.ref}
                  </Label>
                  <ButtonGroup>
                    {states.map((state) => (
                      <ButtonGroupItem
                        key={`${partType}-${currentPart.ref}-${state}-${currentPart.state}`}
                        active={currentPart.state === state}
                        onClick={() => handleChangeFaceState(partType, state)}
                        disabled={isSubmitting}
                      >
                        {state}
                      </ButtonGroupItem>
                    ))}
                  </ButtonGroup>
                </div>
              );
            })}
          </div>
        </TabsContent>

        <TabsContent value="presets" className="mt-8">
          <div className="space-y-6">
            {faceState.presets.length > 0 ? (
              <div className="border rounded-lg p-4">
                <Label className="text-base font-medium block mb-3">Available Presets</Label>
                <ButtonGroup>
                  {faceState.presets.map((preset) => (
                    <ButtonGroupItem
                      key={`preset-${preset}-${faceState.preset}`}
                      active={faceState.preset === preset}
                      onClick={() => handleChangePreset(preset)}
                      disabled={isSubmitting}
                    >
                      {preset}
                    </ButtonGroupItem>
                  ))}
                </ButtonGroup>
              </div>
            ) : (
              <p className="text-muted-foreground">Presets not found</p>
            )}
          </div>
        </TabsContent>

        <TabsContent value="settings" className="mt-8">
          <div className="space-y-4 max-w-md">
            <div className="flex items-center justify-between border rounded-lg p-4">
              <Label className="text-base font-medium">Blinking</Label>
              <Button
                variant={faceState.blinking ? "default" : "outline"}
                onClick={() => handleToggle("SetBlinking", !faceState.blinking)}
                disabled={isSubmitting}
              >
                {faceState.blinking ? "On" : "Off"}
              </Button>
            </div>
            
            <div className="flex items-center justify-between border rounded-lg p-4">
              <Label className="text-base font-medium">Audio Reactive</Label>
              <Button
                variant={faceState.audio_reactive ? "default" : "outline"}
                onClick={() => handleToggle("SetAudioReactive", !faceState.audio_reactive)}
                disabled={isSubmitting}
              >
                {faceState.audio_reactive ? "On" : "Off"}
              </Button>
            </div>

            <div className="flex items-center justify-between border rounded-lg p-4">
              <Label className="text-base font-medium">Metadata</Label>
              <Button
                variant="outline"
                onClick={handleReload}
                disabled={isSubmitting}
              >
                Reload
              </Button>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
