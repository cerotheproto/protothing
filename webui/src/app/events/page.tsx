"use client";

import { useEffect, useState } from "react";
import { getActiveApp } from "@/lib/api/apps";
import { getEventTypesForApp, type EventSchema, type QuerySchema } from "@/lib/api/events";
import { GenericEventPage } from "@/components/GenericEventPage";
import { ReactiveFacePage } from "@/components/ReactiveFacePage";
import { toast } from "sonner";
import { Spinner } from "@/components/ui/spinner";

export default function EventsPage() {
  const [activeApp, setActiveApp] = useState<string | null>(null);
  const [events, setEvents] = useState<EventSchema[]>([]);
  const [queries, setQueries] = useState<QuerySchema[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const app = await getActiveApp();
        if (!app) {
          toast.error("No active application");
          return;
        }
        
        setActiveApp(app);
        const types = await getEventTypesForApp(app);
        setEvents(types.events);
        setQueries(types.queries);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Loading error");
      } finally {
        setIsLoading(false);
      }
    }
    
    loadData();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Spinner />
      </div>
    );
  }

  if (!activeApp) {
    return (
      <div className="p-8">
        <p className="text-muted-foreground">No active application</p>
      </div>
    );
  }

  if (activeApp === "reactive_face") {
    return <ReactiveFacePage activeApp={activeApp} />;
  }

  return (
    <GenericEventPage
      activeApp={activeApp}
      events={events}
      queries={queries}
    />
  );
}
