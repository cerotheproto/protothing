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
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  listFiles,
  uploadFile,
  deleteFile,
  createDirectory,
  getMetadata,
  updateMetadata,
  getFileUrl,
  FileInfo,
} from "@/lib/api/files";
import { toast } from "sonner";

export default function AssetsPage() {
  const [currentPath, setCurrentPath] = useState<string>("");
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<FileInfo | null>(null);
  const [metadata, setMetadata] = useState<any>(null);
  const [editedMetadata, setEditedMetadata] = useState<string>("");
  const [isMetadataDialogOpen, setIsMetadataDialogOpen] = useState(false);
  const [isCreateDirDialogOpen, setIsCreateDirDialogOpen] = useState(false);
  const [newDirName, setNewDirName] = useState("");
  const [isDragActive, setIsDragActive] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [fileToDelete, setFileToDelete] = useState<FileInfo | null>(null);

  useEffect(() => {
    loadFiles();
  }, [currentPath]);

  const loadFiles = async () => {
    try {
      setIsLoading(true);
      const data = await listFiles(currentPath);
      setFiles(data.items);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error loading files");
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileClick = (file: FileInfo) => {
    if (file.type === "directory") {
      setCurrentPath(file.path);
    } else if (file.type === "yaml") {
      loadMetadata(file);
    }
  };

  const handleGoBack = () => {
    const parts = currentPath.split("/");
    parts.pop();
    setCurrentPath(parts.join("/"));
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      await uploadFile(currentPath, file);
      toast.success("File uploaded");
      loadFiles();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error uploading file");
    }
  };

  const handleDeleteClick = (file: FileInfo) => {
    setFileToDelete(file);
    setDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!fileToDelete) return;

    try {
      await deleteFile(fileToDelete.path);
      toast.success("Deleted");
      setDeleteDialogOpen(false);
      setFileToDelete(null);
      loadFiles();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error deleting");
    }
  };

  const handleCreateDirectory = async () => {
    if (!newDirName.trim()) return;

    try {
      await createDirectory(currentPath, newDirName);
      toast.success("Directory created");
      setIsCreateDirDialogOpen(false);
      setNewDirName("");
      loadFiles();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error creating directory");
    }
  };

  const loadMetadata = async (file: FileInfo) => {
    try {
      const data = await getMetadata(file.path);
      setMetadata(data);
      setEditedMetadata(JSON.stringify(data, null, 2));
      setSelectedFile(file);
      setIsMetadataDialogOpen(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error loading metadata");
    }
  };

  const handleSaveMetadata = async () => {
    if (!selectedFile) return;

    try {
      const data = JSON.parse(editedMetadata);
      await updateMetadata(selectedFile.path, data);
      toast.success("Metadata saved");
      setIsMetadataDialogOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error saving metadata");
    }
  };

  const handleDrag = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        try {
          await uploadFile(currentPath, file);
          toast.success(`${file.name} uploaded`);
        } catch (err) {
          toast.error(
            err instanceof Error
              ? err.message
              : `Error uploading ${file.name}`
          );
        }
      }
      loadFiles();
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[calc(100vh-3.5rem)] md:min-h-screen items-center justify-center">
        <Spinner className="size-8" />
      </div>
    );
  }

  return (
    <div 
      className="p-4 md:p-6 max-w-7xl mx-auto w-full"
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
    >
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-4">Assets</h1>
        
        <div className="flex items-center gap-2 mb-4">
          {currentPath && (
            <Button onClick={handleGoBack} variant="outline">
              ← Back
            </Button>
          )}
          <div className="text-sm text-muted-foreground">
            /{currentPath || "assets"}
          </div>
        </div>

        <div className="flex gap-2">
          <Button onClick={() => setIsCreateDirDialogOpen(true)}>
            Create Directory
          </Button>
          <label>
            <Button variant="outline" asChild>
              <span>Upload File</span>
            </Button>
            <input
              type="file"
              className="hidden"
              onChange={handleFileUpload}
            />
          </label>
        </div>
      </div>

      {isDragActive && (
        <div className="mb-6 border-2 border-dashed border-primary rounded-lg p-8 text-center bg-primary/5">
          <p className="text-lg font-medium">Drop files here to upload</p>
        </div>
      )}

      <ItemGroup>
        {files.map((file) => (
          <Item key={file.path}>
            <ItemHeader>
              <ItemContent>
                <div className="flex items-center gap-4">
                  {file.type === "image" && (
                    <img
                      src={getFileUrl(file.path)}
                      alt={file.name}
                      className="w-16 h-16 object-contain bg-muted rounded"
                    />
                  )}
                  <div>
                    <ItemTitle
                      className="cursor-pointer hover:underline"
                      onClick={() => handleFileClick(file)}
                    >
                      {file.type === "directory" ? "📁" : "📄"} {file.name}
                    </ItemTitle>
                    {file.size && (
                      <div className="text-xs text-muted-foreground">
                        {(file.size / 1024).toFixed(2)} KB
                      </div>
                    )}
                  </div>
                </div>
              </ItemContent>
              <ItemActions>
                {file.type === "yaml" && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => loadMetadata(file)}
                  >
                    Edit
                  </Button>
                )}
                {file.type !== "directory" && (
                  <a href={getFileUrl(file.path)} download>
                    <Button variant="outline" size="sm">
                      Download
                    </Button>
                  </a>
                )}
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleDeleteClick(file)}
                >
                  Delete
                </Button>
              </ItemActions>
            </ItemHeader>
          </Item>
        ))}
      </ItemGroup>

      {/* Create directory dialog */}
      <Dialog open={isCreateDirDialogOpen} onOpenChange={setIsCreateDirDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Directory</DialogTitle>
          </DialogHeader>
          <Input
            value={newDirName}
            onChange={(e) => setNewDirName(e.target.value)}
            placeholder="Directory name"
          />
          <DialogFooter>
            <Button onClick={handleCreateDirectory}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete file dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete file?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete "<strong>{fileToDelete?.name}</strong>"? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Metadata editing dialog */}
      <Dialog open={isMetadataDialogOpen} onOpenChange={setIsMetadataDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Metadata: {selectedFile?.name}
            </DialogTitle>
          </DialogHeader>
          <textarea
            value={editedMetadata}
            onChange={(e) => setEditedMetadata(e.target.value)}
            className="w-full h-96 p-2 font-mono text-sm border rounded"
          />
          <DialogFooter>
            <Button onClick={handleSaveMetadata}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
