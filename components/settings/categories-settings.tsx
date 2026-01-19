"use client";

import * as React from "react";
import { Plus, Pencil, Trash2, Loader2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { invalidateSubscriptions } from "@/hooks/use-subscriptions";
interface Category {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
}

export function CategoriesSettings() {
  const queryClient = useQueryClient();
  const [categories, setCategories] = React.useState<Category[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [newCategoryName, setNewCategoryName] = React.useState("");
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [editingName, setEditingName] = React.useState("");
  const [saving, setSaving] = React.useState(false);

  // Fetch categories
  const fetchCategories = React.useCallback(async () => {
    try {
      const response = await fetch("/api/categories");
      if (response.ok) {
        const data = await response.json();
        setCategories(data);
      }
    } catch (error) {
      console.error("Failed to fetch categories:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  // Add category
  const handleAdd = async () => {
    if (!newCategoryName.trim()) return;

    setSaving(true);
    try {
      const response = await fetch("/api/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newCategoryName.trim() }),
      });

      if (response.ok) {
        setNewCategoryName("");
        fetchCategories();
        invalidateSubscriptions(queryClient);
      }
    } catch (error) {
      console.error("Failed to add category:", error);
    } finally {
      setSaving(false);
    }
  };

  // Update category
  const handleUpdate = async (id: string) => {
    if (!editingName.trim()) return;

    setSaving(true);
    try {
      const response = await fetch(`/api/categories/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: editingName.trim() }),
      });

      if (response.ok) {
        setEditingId(null);
        setEditingName("");
        fetchCategories();
        invalidateSubscriptions(queryClient);
      }
    } catch (error) {
      console.error("Failed to update category:", error);
    } finally {
      setSaving(false);
    }
  };

  // Delete category
  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this category?")) return;

    try {
      const response = await fetch(`/api/categories/${id}`, {
        method: "DELETE",
      });

      if (response.ok) {
        fetchCategories();
        invalidateSubscriptions(queryClient);
      }
    } catch (error) {
      console.error("Failed to delete category:", error);
    }
  };

  // Start editing
  const startEditing = (category: Category) => {
    setEditingId(category.id);
    setEditingName(category.name);
  };

  // Cancel editing
  const cancelEditing = () => {
    setEditingId(null);
    setEditingName("");
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h3 className="text-lg font-medium">Categories</h3>
        <p className="text-sm text-muted-foreground">
          Organize your feeds into categories.
        </p>
      </div>

      {/* Add new category */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Add New Category</label>
        <div className="flex gap-2">
          <Input
            placeholder="Category name"
            value={newCategoryName}
            onChange={(e) => setNewCategoryName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAdd();
            }}
            className="flex-1"
          />
          <Button
            onClick={handleAdd}
            disabled={saving || !newCategoryName.trim()}
          >
            {saving ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Plus className="size-4" />
            )}
            <span className="ml-2">Add</span>
          </Button>
        </div>
      </div>

      {/* Category list */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Existing Categories</label>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : categories.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No categories yet. Add your first category above.
          </p>
        ) : (
          <div className="space-y-2">
            {[...categories]
              .sort((a, b) => a.name.localeCompare(b.name))
              .map((category) => (
                <div
                  key={category.id}
                  className="flex items-center gap-2 rounded-lg border p-3"
                >
                  {editingId === category.id ? (
                    <>
                      <Input
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleUpdate(category.id);
                          if (e.key === "Escape") cancelEditing();
                        }}
                        className="flex-1"
                        autoFocus
                      />
                      <Button
                        size="sm"
                        onClick={() => handleUpdate(category.id)}
                        disabled={saving || !editingName.trim()}
                      >
                        Save
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={cancelEditing}
                      >
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <>
                      <span className="flex-1 font-medium">
                        {category.name}
                      </span>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-8"
                        onClick={() => startEditing(category)}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-8 text-destructive hover:text-destructive"
                        onClick={() => handleDelete(category.id)}
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
