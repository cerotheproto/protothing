"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { emitEvent } from "@/lib/api/events";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { ChevronUp, ChevronDown, ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";

const MOVE_INTERVAL_MS = 100;

export function SnakePage({ activeApp }: { activeApp: string }) {
  const [isResetting, setIsResetting] = useState(false);
  const [isGameOver, setIsGameOver] = useState(false);
  const moveIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const sendMoveEvent = useCallback(async (direction: number) => {
    try {
      await emitEvent("MoveSnake", {
        direction,
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
    }
  }, []);

  const handleDirectionKey = useCallback(
    async (direction: number) => {
      await sendMoveEvent(direction);
    },
    [sendMoveEvent]
  );

  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (isGameOver) return;
      
      switch (e.key.toLowerCase()) {
        case "arrowup":
        case "w":
          e.preventDefault();
          handleDirectionKey(0);
          break;
        case "arrowdown":
        case "s":
          e.preventDefault();
          handleDirectionKey(1);
          break;
        case "arrowleft":
        case "a":
          e.preventDefault();
          handleDirectionKey(2);
          break;
        case "arrowright":
        case "d":
          e.preventDefault();
          handleDirectionKey(3);
          break;
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [handleDirectionKey, isGameOver]);

  useEffect(() => {
    return () => {
      if (moveIntervalRef.current) {
        clearInterval(moveIntervalRef.current);
      }
    };
  }, []);

  const handleReset = async () => {
    setIsResetting(true);
    setIsGameOver(false);
    try {
      await emitEvent("ResetSnakeGame", {});
      toast.success("Game reset");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] p-4 space-y-8">
      <div className="grid grid-cols-3 gap-4 w-full max-w-md">
        <div></div>
        <Button
          size="lg"
          className="h-20 w-20"
          onMouseDown={() => handleDirectionKey(0)}
          onTouchStart={() => handleDirectionKey(0)}
          disabled={isResetting || isGameOver}
        >
          <ChevronUp className="h-10 w-10" />
        </Button>
        <div></div>

        <Button
          size="lg"
          className="h-20 w-20"
          onMouseDown={() => handleDirectionKey(2)}
          onTouchStart={() => handleDirectionKey(2)}
          disabled={isResetting || isGameOver}
        >
          <ChevronLeft className="h-10 w-10" />
        </Button>
        <Button
          size="lg"
          className="h-20 w-20"
          onMouseDown={() => handleDirectionKey(1)}
          onTouchStart={() => handleDirectionKey(1)}
          disabled={isResetting || isGameOver}
        >
          <ChevronDown className="h-10 w-10" />
        </Button>
        <Button
          size="lg"
          className="h-20 w-20"
          onMouseDown={() => handleDirectionKey(3)}
          onTouchStart={() => handleDirectionKey(3)}
          disabled={isResetting || isGameOver}
        >
          <ChevronRight className="h-10 w-10" />
        </Button>
      </div>

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
