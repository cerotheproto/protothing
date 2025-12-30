const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface EventSchema {
  name: string;
  schema: any;
}

export interface QuerySchema {
  name: string;
  description?: string;
  schema: any;
}

export interface AppTypesResponse {
  events: EventSchema[];
  queries: QuerySchema[];
}

export async function getEventTypesForApp(appName: string): Promise<AppTypesResponse> {
  const response = await fetch(`${API_URL}/events/types/${appName}`);
  if (!response.ok) {
    throw new Error("Error getting event types");
  }
  return await response.json();
}

export async function emitEvent(eventName: string, payload: any): Promise<void> {
  const response = await fetch(`${API_URL}/events/emit/${eventName}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Error sending event");
  }
}

export async function executeQuery(appName: string, queryName: string, payload?: any): Promise<any> {
  const response = await fetch(`${API_URL}/apps/${appName}/queries/${queryName}`, {
    method: "GET",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Error executing query");
  }
  return await response.json();
}
