const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AppResponse {
  active_app: string | null;
}

export interface AvailableAppsResponse {
  available_apps: string[];
}

export interface ActivateAppResponse {
  status: string;
  active_app: string;
}

export async function getActiveApp(): Promise<string | null> {
  const response = await fetch(`${API_URL}/apps/active`);
  if (!response.ok) {
    throw new Error("Error getting active application");
  }
  const data: AppResponse = await response.json();
  return data.active_app;
}

export async function getAvailableApps(): Promise<string[]> {
  const response = await fetch(`${API_URL}/apps/available`);
  if (!response.ok) {
    throw new Error("Error getting application list");
  }
  const data: AvailableAppsResponse = await response.json();
  return data.available_apps;
}

export async function activateApp(appName: string): Promise<string> {
  const response = await fetch(`${API_URL}/apps/activate/${appName}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error("Error activating application");
  }
  const data: ActivateAppResponse = await response.json();
  return data.active_app;
}
