"use client";

import { useCallback, useEffect, useState } from "react";
import { emitEvent } from "@/lib/api/events";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { RotateCcw, ArrowUp } from "lucide-react";

export function FlappyBirdPage({ activeApp }: { activeApp: string }) {
  const [isResetting, setIsResetting] = useState(false);
  const [isGameOver, setIsGameOver] = useState(false);

  const handleFlap = useCallback(async () => {
    try {
      await emitEvent("Flap", {});
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
    }
  }, []);

  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (isGameOver) return;
      
      if (e.key === " " || e.key === "ArrowUp" || e.key.toLowerCase() === "w") {
        e.preventDefault();
        handleFlap();
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [handleFlap, isGameOver]);

  const handleReset = async () => {
    setIsResetting(true);
    setIsGameOver(false);
    try {
      await emitEvent("ResetFlappyBirdGame", {});
      toast.success("Game reset");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] p-4 space-y-8">
      <div className="text-center space-y-4">
      </div>

      <Button
        size="lg"
        className="h-32 w-32 rounded-full"
        onMouseDown={handleFlap}
        onTouchStart={(e) => {
          e.preventDefault();
          handleFlap();
        }}
        disabled={isResetting || isGameOver}
      >
        <ArrowUp className="h-16 w-16" />
      </Button>

      <Button
        variant="outline"
        onClick={handleReset}
        disabled={isResetting}
        className="mt-8"
      >
        <RotateCcw className="mr-2 h-4 w-4" />
        Reset Game
      </Button>

      {isGameOver && (
        <div className="text-center space-y-2 p-4 bg-red-100 rounded-lg border border-red-300">
          <p className="text-red-700 font-bold">Game Over!</p>
          <p className="text-sm text-red-600">Click Reset Game to try again</p>
        </div>
      )}
    </div>
  );
}
