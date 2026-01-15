"use client";

import { useState } from "react";
import type { EventSchema, QuerySchema } from "@/lib/api/events";
import { emitEvent, executeQuery } from "@/lib/api/events";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Spinner } from "@/components/ui/spinner";

function SchemaForm({ schema, onSubmit, buttonText, isQuery = false }: { 
  schema: any; 
  onSubmit: (data: any) => Promise<any>;
  buttonText: string;
  isQuery?: boolean;
}) {
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const properties = schema?.properties || {};
  const required = schema?.required || [];

  const handleChange = (key: string, value: string) => {
    setFormData(prev => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      // convert data types based on schema
      const typedData: Record<string, any> = {};
      for (const key in formData) {
        const propSchema = properties[key];
        const value = formData[key];
        
        if (propSchema?.type === "number" || propSchema?.type === "integer") {
          typedData[key] = Number(value);
        } else if (propSchema?.type === "boolean") {
          typedData[key] = value === "true" || value === true;
        } else {
          typedData[key] = value;
        }
      }
      
      const result = await onSubmit(typedData);
      if (isQuery && result) {
        toast.success("Request executed");
      } else if (!isQuery) {
        toast.success("Sent successfully");
      }
      setFormData({});
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Sending error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {Object.entries(properties).map(([key, prop]: [string, any]) => {
        const isRequired = required.includes(key);
        const type = prop.type;
        
        return (
          <div key={key} className="space-y-2">
            <Label htmlFor={key}>
              {prop.title || key}
              {isRequired && <span className="text-destructive ml-1">*</span>}
            </Label>
            {prop.description && (
              <p className="text-xs text-muted-foreground">{prop.description}</p>
            )}
            {type === "boolean" ? (
              <select
                id={key}
                value={formData[key]?.toString() || "false"}
                onChange={(e) => handleChange(key, e.target.value)}
                required={isRequired}
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs"
              >
                <option value="false">false</option>
                <option value="true">true</option>
              </select>
            ) : (
              <Input
                id={key}
                type={type === "number" || type === "integer" ? "number" : "text"}
                value={formData[key] || ""}
                onChange={(e) => handleChange(key, e.target.value)}
                required={isRequired}
                placeholder={prop.default?.toString()}
              />
            )}
          </div>
        );
      })}
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? <Spinner /> : buttonText}
      </Button>
    </form>
  );
}

function EventCard({ 
  name, 
  description, 
  schema, 
  onSubmit, 
  buttonText,
  isQuery = false
}: { 
  name: string;
  description?: string;
  schema: any; 
  onSubmit: (data: any) => Promise<any>;
  buttonText: string;
  isQuery?: boolean;
}) {
  const [result, setResult] = useState<any>(null);
  
  const handleSubmitWithResult = async (data: any) => {
    const res = await onSubmit(data);
    if (isQuery && res) {
      setResult(res);
    }
  };
  
  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div>
        <h3 className="font-medium text-sm">{name}</h3>
        {description && (
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        )}
      </div>
      <SchemaForm
        schema={schema}
        onSubmit={handleSubmitWithResult}
        buttonText={buttonText}
        isQuery={isQuery}
      />
      {isQuery && result && (
        <div className="mt-4 pt-4 border-t">
          <p className="text-xs font-medium text-muted-foreground mb-2">Result:</p>
          <pre className="bg-muted p-3 rounded text-xs overflow-auto max-h-48 font-mono">
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export interface GenericEventPageProps {
  activeApp: string;
  events: EventSchema[];
  queries: QuerySchema[];
}

export function GenericEventPage({ activeApp, events, queries }: GenericEventPageProps) {
  const handleEventSubmit = async (eventName: string, payload: any) => {
    await emitEvent(eventName, payload);
  };

  const handleQuerySubmit = async (queryName: string, payload: any) => {
    return await executeQuery(activeApp, queryName);
  };

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto w-full">
      <h1 className="text-3xl font-bold mb-2">Events and Queries</h1>
      <p className="text-muted-foreground mb-8">Application: {activeApp}</p>

      <Tabs defaultValue="events" className="w-full">
        <TabsList>
          <TabsTrigger value="events">Events ({events.length})</TabsTrigger>
          <TabsTrigger value="queries">Queries ({queries.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="events" className="mt-8">
          {events.length === 0 ? (
            <p className="text-muted-foreground">No available events</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {events.map((event) => (
                <EventCard
                  key={event.name}
                  name={event.name}
                  schema={event.schema}
                  onSubmit={(data) => handleEventSubmit(event.name, data)}
                  buttonText="Send"
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="queries" className="mt-8">
          {queries.length === 0 ? (
            <p className="text-muted-foreground">No available queries</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {queries.map((query) => (
                <EventCard
                  key={query.name}
                  name={query.name}
                  description={query.description}
                  schema={query.schema}
                  onSubmit={(data) => handleQuerySubmit(query.name, data)}
                  buttonText="Execute"
                  isQuery={true}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
