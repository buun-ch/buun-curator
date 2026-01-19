"use client";

import * as React from "react";
import { ChevronRight, Plus, Check, X, Loader2, Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useRedditFavorites } from "@/hooks/use-reddit-favorites";
import { useSettingsStore } from "@/stores/settings-store";

import { RedditIcon } from "./icons";

interface RedditSectionProps {
  collapsed?: boolean;
  selectedId?: string;
  onSelect?: (id: string) => void;
}

/** Inline input for adding subreddit. */
function SubredditAddInput({
  onAdd,
  onCancel,
  isAdding,
}: {
  onAdd: (name: string) => void;
  onCancel: () => void;
  isAdding?: boolean;
}) {
  const [value, setValue] = React.useState("");
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = () => {
    if (value.trim()) {
      onAdd(value.trim());
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    } else if (e.key === "Escape") {
      onCancel();
    }
  };

  return (
    <div
      className="flex items-center gap-1 px-2 py-1"
      style={{ paddingLeft: "44px" }}
    >
      <Input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="subreddit name"
        className="h-7 flex-1 text-sm"
        disabled={isAdding}
      />
      <Button
        variant="ghost"
        size="icon"
        className="size-6 shrink-0"
        onClick={handleSubmit}
        disabled={!value.trim() || isAdding}
      >
        {isAdding ? (
          <Loader2 className="size-3 animate-spin" />
        ) : (
          <Check className="size-3" />
        )}
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="size-6 shrink-0"
        onClick={onCancel}
        disabled={isAdding}
      >
        <X className="size-3" />
      </Button>
    </div>
  );
}

/** Favorite subreddit item with hover delete button. */
function FavoriteSubredditItem({
  name,
  isSelected,
  collapsed,
  onSelect,
  onDelete,
  isDeleting,
}: {
  name: string;
  isSelected: boolean;
  collapsed?: boolean;
  onSelect: () => void;
  onDelete: () => void;
  isDeleting?: boolean;
}) {
  return (
    <div
      className={cn(
        "group flex w-full items-center rounded-md text-sm select-none hover:bg-accent",
        isSelected && "bg-accent",
        collapsed && "justify-center",
      )}
      style={{ paddingLeft: collapsed ? undefined : "44px" }}
    >
      <button
        onClick={onSelect}
        className="flex min-w-0 flex-1 items-center gap-2 py-1.5 pr-1"
      >
        {!collapsed && (
          <span className="flex-1 truncate text-left">r/{name}</span>
        )}
      </button>
      {!collapsed && (
        <Button
          variant="ghost"
          size="icon"
          className="mr-1 size-6 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          disabled={isDeleting}
        >
          {isDeleting ? (
            <Loader2 className="size-3 animate-spin" />
          ) : (
            <Trash2 className="size-3" />
          )}
        </Button>
      )}
    </div>
  );
}

/**
 * Reddit section wrapper component.
 *
 * Collapsible section containing Reddit search and favorite subreddits.
 */
export function RedditSection({
  collapsed,
  selectedId,
  onSelect,
}: RedditSectionProps) {
  // Use store for collapse state (persisted to localStorage)
  const isOpen = useSettingsStore((state) => state.redditSectionOpen);
  const setIsOpen = useSettingsStore((state) => state.setRedditSectionOpen);
  const [isAddingNew, setIsAddingNew] = React.useState(false);
  const [deletingId, setDeletingId] = React.useState<string | null>(null);
  const { favorites, addFavorite, isAdding, removeFavorite } =
    useRedditFavorites();

  // "Reddit" is selected when showing Reddit search
  const isRedditSelected = selectedId === "reddit-search";

  const handleAdd = async (name: string) => {
    try {
      await addFavorite(name);
      setIsAddingNew(false);
    } catch {
      // Error is handled by the hook, keep input open
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await removeFavorite(id);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div
        className={cn(
          "flex w-full items-center rounded-md text-sm font-medium select-none",
          isRedditSelected && "bg-accent",
          collapsed && "justify-center",
        )}
      >
        <CollapsibleTrigger asChild>
          <button
            className="flex items-center rounded-md p-1.5 hover:bg-accent"
            onClick={(e) => e.stopPropagation()}
          >
            <ChevronRight
              className={cn(
                "size-4 shrink-0 transition-transform",
                isOpen && "rotate-90",
                collapsed && "hidden",
              )}
            />
          </button>
        </CollapsibleTrigger>
        <button
          className={cn(
            "flex flex-1 items-center gap-2 rounded-md py-1.5 hover:bg-accent",
            collapsed && "justify-center px-0",
          )}
          onClick={() => onSelect?.("reddit-search")}
        >
          <RedditIcon className="size-4 text-muted-foreground" />
          {!collapsed && (
            <span className="flex-1 truncate text-left">Reddit</span>
          )}
        </button>
        {!collapsed && (
          <Button
            variant="ghost"
            size="icon"
            className="mr-1 size-6 shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              setIsAddingNew(true);
              setIsOpen(true);
            }}
          >
            <Plus className="size-3" />
          </Button>
        )}
      </div>
      <CollapsibleContent>
        {favorites.map((fav) => (
          <FavoriteSubredditItem
            key={fav.id}
            name={fav.name}
            isSelected={selectedId === `reddit-fav-${fav.id}`}
            collapsed={collapsed}
            onSelect={() => onSelect?.(`reddit-fav-${fav.id}`)}
            onDelete={() => handleDelete(fav.id)}
            isDeleting={deletingId === fav.id}
          />
        ))}
        {isAddingNew && !collapsed && (
          <SubredditAddInput
            onAdd={handleAdd}
            onCancel={() => setIsAddingNew(false)}
            isAdding={isAdding}
          />
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}
