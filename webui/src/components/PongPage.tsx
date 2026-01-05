"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { emitEvent } from "@/lib/api/events";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { ChevronUp, ChevronDown, RotateCcw } from "lucide-react";

const MOVE_INTERVAL_MS = 120;

export function PongPage({ activeApp }: { activeApp: string }) {
  const [selectedPlayer, setSelectedPlayer] = useState<1 | 2>(1);
  const [isResetting, setIsResetting] = useState(false);
  const selectedPlayerRef = useRef(selectedPlayer);
  const moveIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const sendMoveEvent = useCallback(async (direction: number) => {
    try {
      await emitEvent("MovePlayer", {
        player_id: selectedPlayerRef.current,
        direction,
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
    }
  }, []);

  const clearMovementInterval = () => {
    if (moveIntervalRef.current) {
      clearInterval(moveIntervalRef.current);
      moveIntervalRef.current = null;
    }
  };

  const startMovement = (direction: number) => {
    clearMovementInterval();
    sendMoveEvent(direction);
    moveIntervalRef.current = setInterval(() => sendMoveEvent(direction), MOVE_INTERVAL_MS);
  };

  const stopMovement = () => {
    clearMovementInterval();
    sendMoveEvent(0);
  };

  useEffect(() => {
    selectedPlayerRef.current = selectedPlayer;
    stopMovement();
  }, [selectedPlayer]);

  useEffect(() => () => stopMovement(), []);

  const handleReset = async () => {
    setIsResetting(true);
    try {
      await emitEvent("ResetGame", {});
      toast.success("Game reset");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] p-4 space-y-8">
      <div className="space-y-4 w-full max-w-md">
        <Label className="text-center block text-lg">Select Player</Label>
        <div className="grid grid-cols-2 gap-4">
          <Button
            variant={selectedPlayer === 1 ? "default" : "outline"}
            onClick={() => setSelectedPlayer(1)}
            className="h-16 text-xl"
            disabled={isResetting}
          >
            Player 1
          </Button>
          <Button
            variant={selectedPlayer === 2 ? "default" : "outline"}
            onClick={() => setSelectedPlayer(2)}
            className="h-16 text-xl"
            disabled={isResetting}
          >
            Player 2
          </Button>
        </div>
      </div>

      <div className="flex flex-col items-center space-y-6 w-full max-w-md">
        <Button
          size="lg"
          className="w-full h-32 text-2xl"
          onMouseDown={() => startMovement(-1)}
          onMouseUp={stopMovement}
          onMouseLeave={stopMovement}
          onTouchStart={() => startMovement(-1)}
          onTouchEnd={stopMovement}
        >
          <ChevronUp className="h-12 w-12" />
          UP
        </Button>

        <Button
          size="lg"
          className="w-full h-32 text-2xl"
          onMouseDown={() => startMovement(1)}
          onMouseUp={stopMovement}
          onMouseLeave={stopMovement}
          onTouchStart={() => startMovement(1)}
          onTouchEnd={stopMovement}
        >
          <ChevronDown className="h-12 w-12" />
          DOWN
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
    </div>
  );
}
