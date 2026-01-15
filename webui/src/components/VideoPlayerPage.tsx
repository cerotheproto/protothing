"use client";

import { useState, useEffect } from "react";
import { emitEvent, executeQuery } from "@/lib/api/events";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Spinner } from "@/components/ui/spinner";
import { Play, Pause, RotateCcw } from "lucide-react";

interface VideoState {
  available_videos: string[];
  current_video: string | null;
  is_playing: boolean;
}

export function VideoPlayerPage({ activeApp }: { activeApp: string }) {
  const [videoState, setVideoState] = useState<VideoState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadVideoState = async () => {
    try {
      const result = await executeQuery(activeApp, "GetVideoState");
      setVideoState(result);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error loading state");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadVideoState();
  }, [activeApp]);

  const handlePlayVideo = async (videoName: string) => {
    setIsSubmitting(true);
    try {
      await emitEvent("PlayVideo", { video_name: videoName });
      toast.success("Video started");
      await new Promise((resolve) => setTimeout(resolve, 100));
      await loadVideoState();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
      await loadVideoState();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePause = async () => {
    setIsSubmitting(true);
    try {
      await emitEvent("PauseVideo", {});
      toast.success("Video paused");
      await new Promise((resolve) => setTimeout(resolve, 100));
      await loadVideoState();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
      await loadVideoState();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResume = async () => {
    setIsSubmitting(true);
    try {
      await emitEvent("ResumeVideo", {});
      toast.success("Video resumed");
      await new Promise((resolve) => setTimeout(resolve, 100));
      await loadVideoState();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
      await loadVideoState();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRestart = async () => {
    setIsSubmitting(true);
    try {
      await emitEvent("RestartVideo", {});
      toast.success("Video restarted");
      await new Promise((resolve) => setTimeout(resolve, 100));
      await loadVideoState();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Error");
      await loadVideoState();
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-3.5rem)] md:min-h-screen">
        <Spinner />
      </div>
    );
  }

  if (!videoState) {
    return <div className="p-4 md:p-6 text-center text-muted-foreground">No data available</div>;
  }

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto w-full">
      <h1 className="text-3xl font-bold mb-8">Video Player</h1>
      <div className="space-y-6">
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Current Video</Label>
            <div className="text-sm text-muted-foreground">
              {videoState.current_video || "No video selected"}
            </div>
          </div>

          {videoState.current_video && (
            <div className="flex gap-2">
              {videoState.is_playing ? (
                <Button onClick={handlePause} disabled={isSubmitting} size="sm">
                  <Pause className="mr-2 h-4 w-4" />
                  Pause
                </Button>
              ) : (
                <Button onClick={handleResume} disabled={isSubmitting} size="sm">
                  <Play className="mr-2 h-4 w-4" />
                  Resume
                </Button>
              )}
              <Button onClick={handleRestart} disabled={isSubmitting} variant="outline" size="sm">
                <RotateCcw className="mr-2 h-4 w-4" />
                Restart
              </Button>
            </div>
          )}
        </div>

        <div className="space-y-2">
          <Label>Available Videos</Label>
          {videoState.available_videos.length === 0 ? (
            <div className="text-sm text-muted-foreground">No videos found in assets/videos</div>
          ) : (
            <div className="grid gap-2">
              {videoState.available_videos.map((video) => (
                <Button
                  key={video}
                  variant={videoState.current_video === video ? "default" : "outline"}
                  onClick={() => handlePlayVideo(video)}
                  disabled={isSubmitting}
                  className="justify-start"
                >
                  <Play className="mr-2 h-4 w-4" />
                  {video}
                </Button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
