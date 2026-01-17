"use client";

import { Star, GitFork, ExternalLink, FileText } from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";

import { Badge } from "@/components/ui/badge";

/** Sanitize schema using defaults (img/svg hidden via components). */
const sanitizeSchema = defaultSchema;
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import type { GitHubRepo } from "./types";
import { GitHubIcon } from "./github-repo-card";

interface RepoDetailDialogProps {
  repo: GitHubRepo | null;
  onOpenChange: (open: boolean) => void;
}

/**
 * Dialog component for displaying detailed GitHub repository information.
 *
 * Shows description, stats, topics, license, README, and links.
 */
export function RepoDetailDialog({ repo, onOpenChange }: RepoDetailDialogProps) {
  const hasReadme = repo?.readmeContent && repo.readmeContent.length > 0;

  return (
    <Dialog open={!!repo} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-5xl">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <GitHubIcon className="h-5 w-5" />
            {repo?.fullName}
          </DialogTitle>
        </DialogHeader>
        {repo && (
          <div className="flex min-h-0 flex-1 flex-col space-y-4">
            {/* Description */}
            {repo.description && (
              <p className="flex-shrink-0 text-sm text-muted-foreground">
                {repo.description}
              </p>
            )}

            {/* Stats */}
            <div className="flex flex-shrink-0 flex-wrap gap-4 text-sm">
              <div className="flex items-center gap-1.5">
                <Star className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">
                  {repo.stars.toLocaleString()}
                </span>
                <span className="text-muted-foreground">stars</span>
              </div>
              <div className="flex items-center gap-1.5">
                <GitFork className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">
                  {repo.forks.toLocaleString()}
                </span>
                <span className="text-muted-foreground">forks</span>
              </div>
              {repo.language && (
                <div className="flex items-center gap-1.5">
                  <span className="text-muted-foreground">Language:</span>
                  <span className="font-medium">{repo.language}</span>
                </div>
              )}
            </div>

            {/* Topics */}
            {repo.topics && repo.topics.length > 0 && (
              <div className="flex-shrink-0 space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">
                  Topics
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {repo.topics.map((topic) => (
                    <Badge key={topic} variant="secondary" className="text-xs">
                      {topic}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* License */}
            {repo.license && (
              <div className="flex-shrink-0 text-sm">
                <span className="text-muted-foreground">License: </span>
                <span>{repo.license}</span>
              </div>
            )}

            {/* README */}
            {hasReadme && (
              <div className="flex flex-col space-y-2">
                <div className="flex items-center gap-1.5">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground">
                    {repo.readmeFilename || "README.md"}
                  </span>
                </div>
                <div className="max-h-[400px] overflow-y-auto rounded-md border bg-muted/30 p-4">
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown
                      rehypePlugins={[
                        rehypeRaw,
                        [rehypeSanitize, sanitizeSchema],
                      ]}
                      components={{
                        // Hide img and svg tags (often inaccessible outside GitHub)
                        img: () => null,
                        svg: () => null,
                      }}
                    >
                      {repo.readmeContent}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            )}

            {/* Links */}
            <div className="flex flex-shrink-0 flex-wrap gap-3 border-t pt-4">
              <a
                href={repo.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-sm text-primary hover:underline"
              >
                <GitHubIcon className="h-4 w-4" />
                View on GitHub
                <ExternalLink className="h-3 w-3" />
              </a>
              {repo.homepage && (
                <a
                  href={repo.homepage}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-sm text-primary hover:underline"
                >
                  Website
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
