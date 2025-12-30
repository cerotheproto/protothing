const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface FileInfo {
  path: string;
  name: string;
  type: "file" | "directory" | "image" | "yaml";
  size?: number;
}

export interface DirectoryListing {
  path: string;
  items: FileInfo[];
}

export async function listFiles(path: string = ""): Promise<DirectoryListing> {
  const response = await fetch(`${API_URL}/files/list?path=${encodeURIComponent(path)}`);
  if (!response.ok) {
    throw new Error("Error getting file list");
  }
  return response.json();
}

export async function uploadFile(path: string, file: File): Promise<{ success: boolean; path: string; name: string }> {
  const formData = new FormData();
  formData.append("file", file);
  
  const response = await fetch(`${API_URL}/files/upload?path=${encodeURIComponent(path)}`, {
    method: "POST",
    body: formData,
  });
  
  if (!response.ok) {
    throw new Error("Error uploading file");
  }
  return response.json();
}

export async function deleteFile(path: string): Promise<{ success: boolean }> {
  const response = await fetch(`${API_URL}/files/delete?path=${encodeURIComponent(path)}`, {
    method: "DELETE",
  });
  
  if (!response.ok) {
    throw new Error("Error deleting file");
  }
  return response.json();
}

export async function createDirectory(path: string, name: string): Promise<{ success: boolean; path: string }> {
  const response = await fetch(`${API_URL}/files/create-directory?path=${encodeURIComponent(path)}&name=${encodeURIComponent(name)}`, {
    method: "POST",
  });
  
  if (!response.ok) {
    throw new Error("Error creating directory");
  }
  return response.json();
}

export async function getMetadata(path: string): Promise<any> {
  const response = await fetch(`${API_URL}/files/metadata?path=${encodeURIComponent(path)}`);
  if (!response.ok) {
    throw new Error("Error getting metadata");
  }
  return response.json();
}

export async function updateMetadata(path: string, data: any): Promise<{ success: boolean }> {
  const response = await fetch(`${API_URL}/files/metadata?path=${encodeURIComponent(path)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    throw new Error("Error updating metadata");
  }
  return response.json();
}

export function getFileUrl(path: string): string {
  return `${API_URL}/files/download?path=${encodeURIComponent(path)}`;
}
