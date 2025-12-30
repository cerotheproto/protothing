"use client";
import { useState, useEffect } from "react";
import { Spinner } from "@/components/ui/spinner";
import {
  Item,
  ItemGroup,
  ItemContent,
  ItemTitle,
  ItemActions,
  ItemHeader,
} from "@/components/ui/item";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  getAvailableEffects,
  getActiveEffects,
  addEffect,
  removeEffect,
  clearEffects,
  getEffectsMetadata,
  EffectMetadata,
  EffectInfo,
} from "@/lib/api/effects";
import { toast } from "sonner";

export default function EffectsPage() {
  const [availableEffects, setAvailableEffects] = useState<string[]>([]);
  const [activeEffects, setActiveEffects] = useState<EffectInfo[]>([]);
  const [effectsMetadata, setEffectsMetadata] = useState<EffectMetadata[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [selectedEffect, setSelectedEffect] = useState<string | null>(null);
  const [effectParams, setEffectParams] = useState<Record<string, any>>({});

  useEffect(() => {
    loadEffects();
  }, []);

  const loadEffects = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [available, active, metadata] = await Promise.all([
        getAvailableEffects(),
        getActiveEffects(),
        getEffectsMetadata(),
      ]);
      setAvailableEffects(available);
      setActiveEffects(active);
      setEffectsMetadata(metadata);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error loading effects"
      );
    } finally {
      setIsLoading(false);
    }
  };

  const getEffectMetadata = (effectName: string): EffectMetadata | undefined => {
    return effectsMetadata.find((meta) => meta.name === effectName);
  };

  const handleAddEffect = async (effectName: string, params?: Record<string, any>) => {
    try {
      setIsAdding(true);
      await addEffect(effectName, params || {});
      toast.success(`Effect ${effectName} added`);
      await loadEffects();
      setSelectedEffect(null);
      setEffectParams({});
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Error adding effect";
      toast.error(message);
    } finally {
      setIsAdding(false);
    }
  };

  const handleClearEffects = async () => {
    try {
      setIsAdding(true);
      await clearEffects();
      toast.success("All effects cleared");
      setActiveEffects([]);
      await loadEffects();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Error clearing effects";
      toast.error(message);
    } finally {
      setIsAdding(false);
    }
  };

  const handleRemoveEffect = async (effectId: string) => {
    try {
      setIsAdding(true);
      await removeEffect(effectId);
      // Remove effect local state immediately
      setActiveEffects(prev => prev.filter(e => e.id !== effectId));
      toast.success("Effect removed");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Error removing effect";
      toast.error(message);
    } finally {
      setIsAdding(false);
    }
  };

  const handleParamChange = (paramName: string, value: any) => {
    setEffectParams((prev) => ({
      ...prev,
      [paramName]: value,
    }));
  };

  const parseColorToTuple = (color: string): [number, number, number] => {
    const hex = color.replace("#", "");
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    return [r, g, b];
  };

  const tupleToColor = (tuple: [number, number, number] | number[]): string => {
    if (!tuple || tuple.length < 3) return "#ffffff";
    const [r, g, b] = tuple;
    return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
  };

  const openEffectDialog = (effectName: string) => {
    const metadata = getEffectMetadata(effectName);
    if (!metadata || metadata.params.length === 0) {
      handleAddEffect(effectName);
      return;
    }
    
    const defaultParams: Record<string, any> = {};
    metadata.params.forEach((param) => {
      if (param.default !== null && param.default !== undefined) {
        defaultParams[param.name] = param.default;
      }
    });
    
    setEffectParams(defaultParams);
    setSelectedEffect(effectName);
  };

  const renderParamInput = (param: any, effectName: string) => {
    const value = effectParams[param.name] ?? param.default;

    switch (param.type) {
      case "boolean":
        return (
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={value || false}
              onChange={(e) => handleParamChange(param.name, e.target.checked)}
              className="w-4 h-4"
            />
            <Label>{param.name}</Label>
          </div>
        );

      case "color":
        return (
          <div className="space-y-2">
            <Label>{param.name}</Label>
            <div className="flex items-center space-x-2">
              <input
                type="color"
                value={Array.isArray(value) ? tupleToColor(value) : "#ffffff"}
                onChange={(e) =>
                  handleParamChange(param.name, parseColorToTuple(e.target.value))
                }
                className="w-12 h-10 border rounded cursor-pointer"
              />
              <span className="text-sm text-gray-500">
                {Array.isArray(value) ? `RGB(${value.join(", ")})` : ""}
              </span>
            </div>
          </div>
        );

      case "number":
      case "integer":
        return (
          <div className="space-y-2">
            <Label>{param.name}</Label>
            <Input
              type="number"
              step={param.type === "number" ? "0.1" : "1"}
              value={typeof value === "number" && !isNaN(value) ? value : (param.default ?? 0)}
              onChange={(e) => {
                const numValue = e.target.value === "" 
                  ? "" 
                  : (param.type === "number"
                    ? parseFloat(e.target.value)
                    : parseInt(e.target.value));
                handleParamChange(
                  param.name,
                  numValue === "" ? param.default ?? 0 : numValue
                );
              }}
            />
          </div>
        );

      default:
        return (
          <div className="space-y-2">
            <Label>{param.name}</Label>
            <Input
              type="text"
              value={value ?? ""}
              onChange={(e) => handleParamChange(param.name, e.target.value)}
            />
          </div>
        );
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto min-w-md">
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Effects</h1>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error}
          </div>
        )}

        {/* Active effects */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Active</h2>
            {activeEffects.length > 0 && (
              <Button
                onClick={handleClearEffects}
                disabled={isAdding}
                variant="destructive"
                size="sm"
              >
                Clear All
              </Button>
            )}
          </div>

          {activeEffects.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No active effects
            </div>
          ) : (
            <ItemGroup>
              {activeEffects.map((effect) => (
                <Item key={effect.id}>
                  <ItemHeader>
                    <ItemTitle>{effect.name}</ItemTitle>
                  </ItemHeader>
                  <ItemActions>
                    <Button
                      onClick={() => handleRemoveEffect(effect.id)}
                      disabled={isAdding}
                      variant="destructive"
                      size="sm"
                    >
                      Remove
                    </Button>
                  </ItemActions>
                </Item>
              ))}
            </ItemGroup>
          )}
        </div>

        {/* Available effects */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Available Effects</h2>

          {availableEffects.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              No available effects
            </div>
          ) : (
            <ItemGroup>
              {availableEffects.map((effect) => {
                const metadata = getEffectMetadata(effect);
                const hasParams = metadata && metadata.params.length > 0;

                return (
                  <Item key={effect}>
                    <ItemContent>
                      <ItemTitle>{effect}</ItemTitle>
                    </ItemContent>
                    <ItemActions>
                      {hasParams ? (
                        <Dialog
                          open={selectedEffect === effect}
                          onOpenChange={(open) => {
                            if (!open) {
                              setSelectedEffect(null);
                              setEffectParams({});
                            }
                          }}
                        >
                          <DialogTrigger asChild>
                            <Button
                              onClick={() => openEffectDialog(effect)}
                              disabled={isAdding || activeEffects.some(e => e.name === effect)}
                              size="sm"
                            >
                              {activeEffects.some(e => e.name === effect)
                                ? "Active"
                                : "Add"}
                            </Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>Effect parameters: {effect}</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                              {metadata?.params.map((param) => (
                                <div key={param.name}>
                                  {renderParamInput(param, effect)}
                                </div>
                              ))}
                            </div>
                            <div className="flex justify-end space-x-2">
                              <Button
                                variant="outline"
                                onClick={() => {
                                  setSelectedEffect(null);
                                  setEffectParams({});
                                }}
                              >
                                Cancel
                              </Button>
                              <Button
                                onClick={() => handleAddEffect(effect, effectParams)}
                                disabled={isAdding}
                              >
                                Apply
                              </Button>
                            </div>
                          </DialogContent>
                        </Dialog>
                      ) : (
                        <Button
                          onClick={() => handleAddEffect(effect)}
                          disabled={isAdding || activeEffects.some(e => e.name === effect)}
                          size="sm"
                        >
                          {activeEffects.some(e => e.name === effect) ? "Active" : "Add"}
                        </Button>
                      )}
                    </ItemActions>
                  </Item>
                );
              })}
            </ItemGroup>
          )}
        </div>
      </div>
    </div>
  );
}
