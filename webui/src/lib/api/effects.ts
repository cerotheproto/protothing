const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface EffectParamInfo {
  name: string;
  type: string;
  default: any;
  required: boolean;
}

export interface EffectMetadata {
  name: string;
  params: EffectParamInfo[];
}

export interface EffectInfo {
  id: string;
  name: string;
}

export interface AvailableEffectsResponse {
  effects: string[];
  count: number;
}

export interface ActiveEffectsResponse {
  effects: EffectInfo[];
  count: number;
}

export interface AddEffectResponse {
  status: string;
  effect_id: string;
  effect_type: string;
  message: string;
}

export interface EffectsMetadataResponse {
  effects: EffectMetadata[];
}

export async function getAvailableEffects(): Promise<string[]> {
  const response = await fetch(`${API_URL}/effects/available`);
  if (!response.ok) {
    throw new Error("Error getting effect list");
  }
  const data: AvailableEffectsResponse = await response.json();
  return data.effects;
}

export async function getActiveEffects(): Promise<EffectInfo[]> {
  const response = await fetch(`${API_URL}/effects/active`);
  if (!response.ok) {
    throw new Error("Error getting active effects");
  }
  const data: ActiveEffectsResponse = await response.json();
  return data.effects;
}

export async function addEffect(
  effectName: string,
  params: Record<string, unknown> = {}
): Promise<AddEffectResponse> {
  const response = await fetch(`${API_URL}/effects/add`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      effect_name: effectName,
      params,
    }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Error adding effect");
  }
  return response.json();
}

export async function removeEffect(effectId: string): Promise<void> {
  const response = await fetch(`${API_URL}/effects/${effectId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Error removing effect");
  }
}

export async function clearEffects(): Promise<void> {
  const response = await fetch(`${API_URL}/effects/clear`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Error clearing effects");
  }
}

export async function getEffectsMetadata(): Promise<EffectMetadata[]> {
  const response = await fetch(`${API_URL}/effects/metadata`);
  if (!response.ok) {
    throw new Error("Error getting effect metadata");
  }
  const data: EffectsMetadataResponse = await response.json();
  return data.effects;
}
