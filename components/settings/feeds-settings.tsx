"use client";

import * as React from "react";
import { Plus, Pencil, Trash2, Loader2, ExternalLink, Search, HelpCircle } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { invalidateSubscriptions } from "@/hooks/use-subscriptions";
interface Category {
  id: string;
  name: string;
}

interface Feed {
  id: string;
  name: string;
  url: string;
  siteUrl: string | null;
  categoryId: string | null;
  type: string | null;
  fetchContent: boolean;
  fetchLimit: number;
  createdAt: string;
  updatedAt: string;
}

interface DiscoveredFeed {
  url: string;
  title?: string;
  type: "rss" | "atom" | "unknown";
}

interface HttpError {
  status: number;
  statusText: string;
}

interface FeedDiscoveryResult {
  feeds: DiscoveredFeed[];
  siteTitle?: string;
  siteUrl: string;
  httpError?: HttpError;
}

interface FeedFormData {
  url: string;
  name: string;
  siteUrl: string;
  categoryId: string;
  type: string;
  fetchLimit: string;
  fetchContent: boolean;
}

const initialFormData: FeedFormData = {
  url: "",
  name: "",
  siteUrl: "",
  categoryId: "",
  type: "",
  fetchLimit: "",
  fetchContent: true,
};

export function FeedsSettings() {
  const queryClient = useQueryClient();
  const [feeds, setFeeds] = React.useState<Feed[]>([]);
  const [categories, setCategories] = React.useState<Category[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [formData, setFormData] = React.useState<FeedFormData>(initialFormData);
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [editFormData, setEditFormData] = React.useState<FeedFormData>(initialFormData);
  const [saving, setSaving] = React.useState(false);

  // Feed discovery state
  const [discovering, setDiscovering] = React.useState(false);
  const [discoveredFeeds, setDiscoveredFeeds] = React.useState<DiscoveredFeed[]>([]);
  const [discoveryError, setDiscoveryError] = React.useState<string | null>(null);
  const [discoverySiteInfo, setDiscoverySiteInfo] = React.useState<{
    siteTitle?: string;
    siteUrl: string;
  } | null>(null);

  // Fetch feeds and categories
  const fetchData = React.useCallback(async () => {
    try {
      const [feedsRes, categoriesRes] = await Promise.all([
        fetch("/api/feeds"),
        fetch("/api/categories"),
      ]);

      if (feedsRes.ok) {
        const feedsData = await feedsRes.json();
        setFeeds(feedsData);
      }

      if (categoriesRes.ok) {
        const categoriesData = await categoriesRes.json();
        setCategories(categoriesData);
      }
    } catch (error) {
      console.error("Failed to fetch data:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Discover feeds from URL
  const handleDiscover = async () => {
    if (!formData.url.trim()) return;

    setDiscovering(true);
    setDiscoveryError(null);
    setDiscoveredFeeds([]);
    setDiscoverySiteInfo(null);

    try {
      const response = await fetch("/api/feeds/discover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: formData.url.trim() }),
      });

      if (!response.ok) {
        throw new Error("Failed to discover feeds");
      }

      const result: FeedDiscoveryResult = await response.json();

      if (result.httpError) {
        setDiscoveryError(`HTTP ${result.httpError.status} ${result.httpError.statusText}`);
      } else if (result.feeds.length === 0) {
        setDiscoveryError("No feeds found at this URL");
      } else if (result.feeds.length === 1) {
        // Auto-fill if only one feed found
        const feed = result.feeds[0];
        // Use site title if feed title is just a feed type name
        const feedTypeNames = ["atom", "rss", "feed", "rss 2.0", "rss2", "atom 1.0"];
        const useFeedTitle = feed.title && !feedTypeNames.includes(feed.title.toLowerCase());
        setFormData({
          ...formData,
          url: feed.url,
          name: useFeedTitle ? feed.title! : (result.siteTitle || feed.title || ""),
          siteUrl: result.siteUrl,
          type: feed.type !== "unknown" ? feed.type : "",
        });
        setDiscoveredFeeds([]);
      } else {
        // Multiple feeds found, let user choose
        setDiscoveredFeeds(result.feeds);
        setDiscoverySiteInfo({
          siteTitle: result.siteTitle,
          siteUrl: result.siteUrl,
        });
      }
    } catch (error) {
      console.error("Failed to discover feeds:", error);
      setDiscoveryError("Failed to discover feeds. Please check the URL.");
    } finally {
      setDiscovering(false);
    }
  };

  // Select a discovered feed
  const handleSelectDiscoveredFeed = (feed: DiscoveredFeed) => {
    // Use site title if feed title is just a feed type name
    const feedTypeNames = ["atom", "rss", "feed", "rss 2.0", "rss2", "atom 1.0"];
    const useFeedTitle = feed.title && !feedTypeNames.includes(feed.title.toLowerCase());
    setFormData({
      ...formData,
      url: feed.url,
      name: useFeedTitle ? feed.title! : (discoverySiteInfo?.siteTitle || feed.title || ""),
      siteUrl: discoverySiteInfo?.siteUrl || "",
      type: feed.type !== "unknown" ? feed.type : "",
    });
    setDiscoveredFeeds([]);
    setDiscoverySiteInfo(null);
  };

  // Clear discovery results
  const clearDiscovery = () => {
    setDiscoveredFeeds([]);
    setDiscoverySiteInfo(null);
    setDiscoveryError(null);
  };

  // Add feed
  const handleAdd = async () => {
    if (!formData.url.trim() || !formData.name.trim()) return;

    setSaving(true);
    try {
      const fetchLimit = formData.fetchLimit ? parseInt(formData.fetchLimit, 10) : 20;

      const response = await fetch("/api/feeds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: formData.url.trim(),
          name: formData.name.trim(),
          siteUrl: formData.siteUrl.trim() || null,
          categoryId: formData.categoryId && formData.categoryId !== "none" ? formData.categoryId : null,
          type: formData.type || null,
          fetchContent: formData.fetchContent,
          fetchLimit,
        }),
      });

      if (response.ok) {
        setFormData(initialFormData);
        clearDiscovery();
        fetchData();
        invalidateSubscriptions(queryClient);
      }
    } catch (error) {
      console.error("Failed to add feed:", error);
    } finally {
      setSaving(false);
    }
  };

  // Update feed
  const handleUpdate = async (id: string) => {
    if (!editFormData.url.trim() || !editFormData.name.trim()) return;

    setSaving(true);
    try {
      const fetchLimit = editFormData.fetchLimit ? parseInt(editFormData.fetchLimit, 10) : 20;

      const response = await fetch(`/api/feeds/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: editFormData.url.trim(),
          name: editFormData.name.trim(),
          siteUrl: editFormData.siteUrl.trim() || null,
          categoryId: editFormData.categoryId && editFormData.categoryId !== "none" ? editFormData.categoryId : null,
          fetchContent: editFormData.fetchContent,
          fetchLimit,
        }),
      });

      if (response.ok) {
        setEditingId(null);
        setEditFormData(initialFormData);
        fetchData();
        invalidateSubscriptions(queryClient);
      }
    } catch (error) {
      console.error("Failed to update feed:", error);
    } finally {
      setSaving(false);
    }
  };

  // Delete feed
  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this feed?")) return;

    try {
      const response = await fetch(`/api/feeds/${id}`, {
        method: "DELETE",
      });

      if (response.ok) {
        fetchData();
        invalidateSubscriptions(queryClient);
        queryClient.invalidateQueries({ queryKey: ["entries"] });
      }
    } catch (error) {
      console.error("Failed to delete feed:", error);
    }
  };

  // Start editing
  const startEditing = (feed: Feed) => {
    setEditingId(feed.id);
    setEditFormData({
      url: feed.url,
      name: feed.name,
      siteUrl: feed.siteUrl || "",
      categoryId: feed.categoryId?.toString() || "none",
      type: feed.type || "",
      fetchLimit: feed.fetchLimit?.toString() || "",
      fetchContent: feed.fetchContent,
    });
  };

  // Cancel editing
  const cancelEditing = () => {
    setEditingId(null);
    setEditFormData(initialFormData);
  };

  // Get category name by id
  const getCategoryName = (categoryId: string | null) => {
    if (!categoryId) return "Uncategorized";
    const category = categories.find((c) => c.id === categoryId);
    return category?.name || "Unknown";
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h3 className="text-lg font-medium">Feeds</h3>
        <p className="text-sm text-muted-foreground">
          Manage your RSS/Atom feed subscriptions.
        </p>
      </div>

      {/* Add new feed form */}
      <div className="space-y-4 rounded-lg border p-4">
        <h4 className="font-medium">Add New Feed</h4>
        <div className="grid gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">URL *</label>
            <div className="flex gap-2">
              <Input
                placeholder="https://example.com or https://example.com/feed.xml"
                value={formData.url}
                onChange={(e) => {
                  setFormData({ ...formData, url: e.target.value });
                  clearDiscovery();
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleDiscover();
                  }
                }}
              />
              <Button
                variant="outline"
                onClick={handleDiscover}
                disabled={discovering || !formData.url.trim()}
              >
                {discovering ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Search className="size-4" />
                )}
                <span className="ml-2">Discover</span>
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Enter a website URL or feed URL. Click Discover to find feeds automatically.
            </p>
          </div>

          {/* Discovery error */}
          {discoveryError && (
            <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {discoveryError}
            </div>
          )}

          {/* Discovered feeds selection */}
          {discoveredFeeds.length > 0 && (
            <div className="space-y-2">
              <label className="text-sm font-medium">
                Found {discoveredFeeds.length} feed(s) - Select one:
              </label>
              <div className="space-y-2 rounded-md border p-2">
                {discoveredFeeds.map((feed, index) => (
                  <button
                    key={index}
                    onClick={() => handleSelectDiscoveredFeed(feed)}
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-accent"
                  >
                    <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs uppercase">
                      {feed.type}
                    </span>
                    <span className="min-w-0 flex-1 truncate">
                      {feed.title || feed.url}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-2">
            <label className="text-sm font-medium">Name *</label>
            <Input
              placeholder="Feed name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Site URL</label>
            <Input
              placeholder="https://example.com"
              value={formData.siteUrl}
              onChange={(e) => setFormData({ ...formData, siteUrl: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Category</label>
            <Select
              value={formData.categoryId}
              onValueChange={(value) => setFormData({ ...formData, categoryId: value })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Uncategorized</SelectItem>
                {[...categories].sort((a, b) => a.name.localeCompare(b.name)).map((category) => (
                  <SelectItem key={category.id} value={category.id.toString()}>
                    {category.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Fetch Limit</label>
            <Input
              type="number"
              placeholder="20 (default)"
              min="1"
              max="100"
              value={formData.fetchLimit ?? ""}
              onChange={(e) => setFormData({ ...formData, fetchLimit: e.target.value })}
            />
            <p className="text-xs text-muted-foreground">
              Maximum number of entries to fetch (1-100, default: 20)
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox
              id="fetchContent"
              checked={formData.fetchContent}
              onCheckedChange={(checked) =>
                setFormData({ ...formData, fetchContent: checked === true })
              }
            />
            <label
              htmlFor="fetchContent"
              className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
            >
              Fetch full content
            </label>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="size-4 text-muted-foreground" />
              </TooltipTrigger>
              <TooltipContent side="right" className="max-w-xs">
                <p>
                  Please ensure the target site does not prohibit crawling.
                  Sites requiring authentication or cookie
                  consent cannot be fetched.
                </p>
              </TooltipContent>
            </Tooltip>
          </div>
          <Button
            onClick={handleAdd}
            disabled={saving || !formData.url.trim() || !formData.name.trim()}
            className="w-fit"
          >
            {saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
            <span className="ml-2">Add Feed</span>
          </Button>
        </div>
      </div>

      {/* Feed list */}
      <div className="space-y-2">
        <h4 className="font-medium">Existing Feeds</h4>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : feeds.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No feeds yet. Add your first feed above.
          </p>
        ) : (
          <div className="space-y-2">
            {feeds.map((feed) => (
              <div
                key={feed.id}
                className="rounded-lg border p-4"
              >
                {editingId === feed.id ? (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Feed URL *</label>
                      <Input
                        value={editFormData.url}
                        onChange={(e) => setEditFormData({ ...editFormData, url: e.target.value })}
                        autoFocus
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Name *</label>
                      <Input
                        value={editFormData.name}
                        onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Site URL</label>
                      <Input
                        value={editFormData.siteUrl}
                        onChange={(e) => setEditFormData({ ...editFormData, siteUrl: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Category</label>
                      <Select
                        value={editFormData.categoryId}
                        onValueChange={(value) => setEditFormData({ ...editFormData, categoryId: value })}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select a category" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">Uncategorized</SelectItem>
                          {[...categories].sort((a, b) => a.name.localeCompare(b.name)).map((category) => (
                            <SelectItem key={category.id} value={category.id.toString()}>
                              {category.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Fetch Limit</label>
                      <Input
                        type="number"
                        placeholder="20 (default)"
                        min="1"
                        max="100"
                        value={editFormData.fetchLimit ?? ""}
                        onChange={(e) => setEditFormData({ ...editFormData, fetchLimit: e.target.value })}
                      />
                      <p className="text-xs text-muted-foreground">
                        Maximum number of entries to fetch (1-100, default: 20)
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id={`editFetchContent-${feed.id}`}
                        checked={editFormData.fetchContent}
                        onCheckedChange={(checked) =>
                          setEditFormData({ ...editFormData, fetchContent: checked === true })
                        }
                      />
                      <label
                        htmlFor={`editFetchContent-${feed.id}`}
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                      >
                        Fetch full content
                      </label>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <HelpCircle className="size-4 text-muted-foreground" />
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-xs">
                          <p>
                            Please ensure the target site does not prohibit crawling.
                            Sites requiring authentication or cookie consent cannot be fetched.
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleUpdate(feed.id)}
                        disabled={saving || !editFormData.url.trim() || !editFormData.name.trim()}
                      >
                        Save
                      </Button>
                      <Button size="sm" variant="outline" onClick={cancelEditing}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{feed.name}</span>
                        {feed.type && (
                          <span className="rounded bg-muted px-1.5 py-0.5 text-xs uppercase text-muted-foreground">
                            {feed.type}
                          </span>
                        )}
                        <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                          {getCategoryName(feed.categoryId)}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
                        <span className="truncate">{feed.url}</span>
                        {feed.siteUrl && (
                          <a
                            href={feed.siteUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="shrink-0 hover:text-foreground"
                          >
                            <ExternalLink className="size-3" />
                          </a>
                        )}
                      </div>
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-8"
                        onClick={() => startEditing(feed)}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-8 text-destructive hover:text-destructive"
                        onClick={() => handleDelete(feed.id)}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
