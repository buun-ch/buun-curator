"use client";

import * as React from "react";
import { Sparkles, Loader2, Play, ChevronRight, Network } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";

import type {
  EntryContext,
  GroupedEntryLink,
  GitHubRepo,
  GitHubEnrichment,
  WebPage,
  WebPageEnrichment,
} from "./types";
import { EntryLinkCard } from "./entry-link-card";
import { GitHubRepoCard } from "./github-repo-card";
import { WebPageCard } from "./web-page-card";

interface ContextViewProps {
  entryId?: string;
  data: EntryContext | null;
  loading: boolean;
  extracting: boolean;
  error: string | null;
  selectedRepos: Set<string>;
  selectedWebPages: Set<string>;
  pendingLinks: Set<string>;
  fetchingLinks: Set<string>;
  failedLinks: Map<string, string>;
  deletingWebPages: Set<string>;
  onToggleRepoSelection: (fullName: string) => void;
  onToggleWebPageSelection: (url: string) => void;
  onEnrichLink: (url: string) => void;
  onDeleteWebPage: (url: string) => void;
  onShowRepoDetail: (repo: GitHubRepo) => void;
  onShowRelationships: () => void;
  onStartExtraction: () => void;
}

/**
 * Context view component displaying extracted entry context.
 *
 * Shows domain tags, key points, GitHub repos, and web pages.
 */
export function ContextView({
  entryId,
  data,
  loading,
  extracting,
  error,
  selectedRepos,
  selectedWebPages,
  pendingLinks,
  fetchingLinks,
  failedLinks,
  deletingWebPages,
  onToggleRepoSelection,
  onToggleWebPageSelection,
  onEnrichLink,
  onDeleteWebPage,
  onShowRepoDetail,
  onShowRelationships,
  onStartExtraction,
}: ContextViewProps) {
  const [keyPointsOpen, setKeyPointsOpen] = React.useState(false);

  // Reset key points state when entry changes
  React.useEffect(() => {
    setKeyPointsOpen(false);
  }, [entryId]);

  // Collect enriched URLs for filtering (need to compute before groupedLinks)
  const enrichedUrlSet = React.useMemo(() => {
    const urls = new Set<string>();
    for (const enrichment of data?.enrichments || []) {
      if (enrichment.type === "web_page" && enrichment.source) {
        urls.add(enrichment.source);
      }
    }
    return urls;
  }, [data?.enrichments]);

  // Group entry links by URL, filter out already enriched URLs, and sort alphabetically
  const groupedLinks: GroupedEntryLink[] = React.useMemo(() => {
    const links = data?.links || [];
    const urlMap = new Map<string, string[]>();

    for (const link of links) {
      // Skip URLs that are already enriched
      if (enrichedUrlSet.has(link.url)) continue;

      const titles = urlMap.get(link.url) || [];
      if (link.title && !titles.includes(link.title)) {
        titles.push(link.title);
      }
      urlMap.set(link.url, titles);
    }

    return Array.from(urlMap.entries())
      .map(([url, titles]) => ({ url, titles }))
      .sort((a, b) => a.url.localeCompare(b.url));
  }, [data?.links, enrichedUrlSet]);

  if (!entryId) {
    return (
      <div className="text-sm text-muted-foreground">No entry selected</div>
    );
  }

  if (loading || extracting) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {extracting ? "Collecting context..." : "Loading..."}
      </div>
    );
  }

  if (error) {
    return <div className="text-sm text-destructive">Error: {error}</div>;
  }

  if (!data?.context) {
    return (
      <Empty className="py-8">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Sparkles className="h-5 w-5" />
          </EmptyMedia>
          <EmptyTitle>No Context Yet</EmptyTitle>
          <EmptyDescription>
            Context has not been collected for this entry.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button
            variant="outline"
            size="sm"
            onClick={onStartExtraction}
            disabled={extracting}
          >
            <Play className="mr-1 h-3 w-3" />
            Collect Context
          </Button>
        </EmptyContent>
      </Empty>
    );
  }

  // Collect all GitHub repos from enrichments (each enrichment = 1 repo)
  const allRepos: GitHubRepo[] = [];
  for (const enrichment of data.enrichments) {
    if (enrichment.type === "github" && enrichment.data) {
      const repo = enrichment.data as GitHubEnrichment;
      // Ensure it has required fields
      if (repo.fullName && repo.url) {
        allRepos.push(repo);
      }
    }
  }

  // Collect all web pages from enrichments (each enrichment = 1 page)
  // Also collect URLs for filtering from Referenced Links
  const allWebPages: Array<WebPage & { url: string }> = [];
  const enrichedUrls = new Set<string>();
  for (const enrichment of data.enrichments) {
    if (enrichment.type === "web_page" && enrichment.data && enrichment.source) {
      const page = enrichment.data as WebPageEnrichment;
      allWebPages.push({
        ...page,
        url: enrichment.source,
      });
      enrichedUrls.add(enrichment.source);
    }
  }

  return (
    <div className="space-y-3">
      {/* Domain + Content Type Tags */}
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary" className="text-xs">
          {data.context.domain}
        </Badge>
        <Badge variant="outline" className="text-xs">
          {data.context.content_type}
        </Badge>

        <div className="ml-auto flex items-center gap-1">
          {/* Relationships Button */}
          {data.context.relationships.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 gap-1 px-2 text-xs text-muted-foreground hover:text-foreground"
              onClick={onShowRelationships}
              title="View relationships graph"
            >
              <Network className="h-3 w-3" />
              <span className="hidden sm:inline">Relationships</span>
              <span className="text-muted-foreground">
                ({data.context.relationships.length})
              </span>
            </Button>
          )}

          {/* Key Points Toggle */}
          {data.context.key_points.length > 0 && (
            <Collapsible open={keyPointsOpen} onOpenChange={setKeyPointsOpen}>
              <CollapsibleTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 gap-1 px-2 text-xs text-muted-foreground hover:text-foreground"
                >
                  <ChevronRight
                    className={cn(
                      "h-3 w-3 transition-transform",
                      keyPointsOpen && "rotate-90"
                    )}
                  />
                  Key Points
                </Button>
              </CollapsibleTrigger>
            </Collapsible>
          )}
        </div>
      </div>

      {/* Key Points Content (Collapsible) */}
      {data.context.key_points.length > 0 && (
        <Collapsible open={keyPointsOpen} onOpenChange={setKeyPointsOpen}>
          <CollapsibleContent>
            <ul className="space-y-1 rounded-md bg-muted/50 p-2 text-xs">
              {data.context.key_points.map((point, i) => (
                <li key={i} className="flex gap-2 text-muted-foreground">
                  <span className="shrink-0">•</span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* Enrichment Cards (GitHub + Web Pages) */}
      {(allRepos.length > 0 || allWebPages.length > 0) && (
        <div className="flex flex-wrap gap-3">
          {/* GitHub Repository Cards */}
          {allRepos.map((repo) => (
            <GitHubRepoCard
              key={repo.fullName}
              repo={repo}
              isSelected={selectedRepos.has(repo.fullName)}
              onToggleSelect={onToggleRepoSelection}
              onShowDetail={onShowRepoDetail}
            />
          ))}

          {/* Web Page Cards */}
          {allWebPages.map((page) => (
            <WebPageCard
              key={page.url}
              page={page}
              isSelected={selectedWebPages.has(page.url)}
              isDeleting={deletingWebPages.has(page.url)}
              onToggleSelect={onToggleWebPageSelection}
              onDelete={onDeleteWebPage}
            />
          ))}
        </div>
      )}

      {/* Entry Links Section */}
      {groupedLinks.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground">
            Referenced Links ({groupedLinks.length})
          </h4>
          <div className="flex flex-wrap gap-2">
            {groupedLinks.map((link) => (
              <EntryLinkCard
                key={link.url}
                link={link}
                isPending={pendingLinks.has(link.url)}
                isFetching={fetchingLinks.has(link.url)}
                isError={failedLinks.has(link.url)}
                errorMessage={failedLinks.get(link.url)}
                onEnrich={onEnrichLink}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
