"use client";

import * as React from "react";
import { Plus, Pencil, Trash2, Loader2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Label {
  id: string;
  name: string;
  color: string;
}

/** Labels settings component for managing entry labels. */
export function LabelsSettings() {
  const queryClient = useQueryClient();
  const [labels, setLabels] = React.useState<Label[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [newLabelName, setNewLabelName] = React.useState("");
  const [newLabelColor, setNewLabelColor] = React.useState("#6b7280");
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [editingName, setEditingName] = React.useState("");
  const [editingColor, setEditingColor] = React.useState("");
  const [saving, setSaving] = React.useState(false);

  // Fetch labels
  const fetchLabels = React.useCallback(async () => {
    try {
      const response = await fetch("/api/labels");
      if (response.ok) {
        const data = await response.json();
        setLabels(data);
      }
    } catch (error) {
      console.error("Failed to fetch labels:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchLabels();
  }, [fetchLabels]);

  // Add label
  const handleAdd = async () => {
    if (!newLabelName.trim()) return;

    setSaving(true);
    try {
      const response = await fetch("/api/labels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newLabelName.trim(),
          color: newLabelColor,
        }),
      });

      if (response.ok) {
        setNewLabelName("");
        setNewLabelColor("#6b7280");
        fetchLabels();
        queryClient.invalidateQueries({ queryKey: ["labels"] });
      }
    } catch (error) {
      console.error("Failed to add label:", error);
    } finally {
      setSaving(false);
    }
  };

  // Update label
  const handleUpdate = async (id: string) => {
    if (!editingName.trim()) return;

    setSaving(true);
    try {
      const response = await fetch(`/api/labels?id=${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editingName.trim(),
          color: editingColor,
        }),
      });

      if (response.ok) {
        setEditingId(null);
        setEditingName("");
        setEditingColor("");
        fetchLabels();
        queryClient.invalidateQueries({ queryKey: ["labels"] });
      }
    } catch (error) {
      console.error("Failed to update label:", error);
    } finally {
      setSaving(false);
    }
  };

  // Delete label
  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this label? It will be removed from all entries.")) return;

    try {
      const response = await fetch(`/api/labels?id=${id}`, {
        method: "DELETE",
      });

      if (response.ok) {
        fetchLabels();
        queryClient.invalidateQueries({ queryKey: ["labels"] });
      }
    } catch (error) {
      console.error("Failed to delete label:", error);
    }
  };

  // Start editing
  const startEditing = (label: Label) => {
    setEditingId(label.id);
    setEditingName(label.name);
    setEditingColor(label.color);
  };

  // Cancel editing
  const cancelEditing = () => {
    setEditingId(null);
    setEditingName("");
    setEditingColor("");
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h3 className="text-lg font-medium">Labels</h3>
        <p className="text-sm text-muted-foreground">
          Create and manage labels to organize your entries.
        </p>
      </div>

      {/* Add new label */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Add New Label</label>
        <div className="flex gap-2">
          <input
            type="color"
            value={newLabelColor}
            onChange={(e) => setNewLabelColor(e.target.value)}
            className="h-9 w-12 cursor-pointer rounded border bg-transparent p-1"
            title="Choose color"
          />
          <Input
            placeholder="Label name"
            value={newLabelName}
            onChange={(e) => setNewLabelName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAdd();
            }}
            className="flex-1"
          />
          <Button onClick={handleAdd} disabled={saving || !newLabelName.trim()}>
            {saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
            <span className="ml-2">Add</span>
          </Button>
        </div>
      </div>

      {/* Label list */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Existing Labels</label>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : labels.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No labels yet. Add your first label above.
          </p>
        ) : (
          <div className="space-y-2">
            {[...labels].sort((a, b) => a.name.localeCompare(b.name)).map((label) => (
              <div
                key={label.id}
                className="flex items-center gap-2 rounded-lg border p-3"
              >
                {editingId === label.id ? (
                  <>
                    <input
                      type="color"
                      value={editingColor}
                      onChange={(e) => setEditingColor(e.target.value)}
                      className="h-9 w-12 cursor-pointer rounded border bg-transparent p-1"
                      title="Choose color"
                    />
                    <Input
                      value={editingName}
                      onChange={(e) => setEditingName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleUpdate(label.id);
                        if (e.key === "Escape") cancelEditing();
                      }}
                      className="flex-1"
                      autoFocus
                    />
                    <Button
                      size="sm"
                      onClick={() => handleUpdate(label.id)}
                      disabled={saving || !editingName.trim()}
                    >
                      Save
                    </Button>
                    <Button size="sm" variant="outline" onClick={cancelEditing}>
                      Cancel
                    </Button>
                  </>
                ) : (
                  <>
                    <span
                      className="size-4 shrink-0 rounded-full border"
                      style={{ backgroundColor: label.color }}
                      title={label.color}
                    />
                    <span className="flex-1 font-medium">{label.name}</span>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-8"
                      onClick={() => startEditing(label)}
                    >
                      <Pencil className="size-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-8 text-destructive hover:text-destructive"
                      onClick={() => handleDelete(label.id)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
