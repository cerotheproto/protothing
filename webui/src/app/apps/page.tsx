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
import {
  getActiveApp,
  getAvailableApps,
  activateApp,
} from "@/lib/api/apps";

export default function AppsPage() {
  const [activeApp, setActiveApp] = useState<string | null>(null);
  const [availableApps, setAvailableApps] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isActivating, setIsActivating] = useState(false);

  useEffect(() => {
    loadApps();
  }, []);

  const loadApps = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [active, available] = await Promise.all([
        getActiveApp(),
        getAvailableApps(),
      ]);
      setActiveApp(active);
      setAvailableApps(available);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error loading applications"
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleActivateApp = async (appName: string) => {
    try {
      setIsActivating(true);
      await activateApp(appName);
      setActiveApp(appName);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error activating application"
      );
    } finally {
      setIsActivating(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-3.5rem)] md:min-h-screen">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Applications</h1>
        {activeApp && (
          <p className="text-sm text-muted-foreground">
            Active: <span className="font-semibold text-foreground">{activeApp}</span>
          </p>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-destructive/10 text-destructive text-sm rounded-md">
          {error}
        </div>
      )}

      <ItemGroup className="border rounded-lg overflow-hidden">
        {availableApps.length === 0 ? (
          <Item>
            <ItemContent>
              <p className="text-muted-foreground">No available applications</p>
            </ItemContent>
          </Item>
        ) : (
          availableApps.map((app) => (
            <Item
              key={app}
              variant={activeApp === app ? "muted" : "default"}
              className="border-b last:border-b-0"
            >
              <ItemHeader className="w-full">
                <ItemContent>
                  <ItemTitle>
                    {app}
                    {activeApp === app && (
                      <span className="inline-block w-2 h-2 bg-green-500 rounded-full ml-2" />
                    )}
                  </ItemTitle>
                </ItemContent>
                <ItemActions>
                  <Button
                    onClick={() => handleActivateApp(app)}
                    disabled={activeApp === app || isActivating}
                    variant={activeApp === app ? "outline" : "default"}
                    size="sm"
                  >
                    {activeApp === app ? "Active" : "Activate"}
                  </Button>
                </ItemActions>
              </ItemHeader>
            </Item>
          ))
        )}
      </ItemGroup>
    </div>
  );
}
