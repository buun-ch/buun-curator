/** View mode for the context panel. */
export type ViewMode = "context" | "debug";

/** Structured context extracted from entry content by LLM. */
export interface ExtractedContext {
  domain: string;
  content_type: string;
  language: string;
  confidence: number;
  entities: Array<{
    name: string;
    type: string;
    role: string | null;
    description: string | null;
  }>;
  relationships: Array<{
    source: string;
    relation: string;
    target: string;
    description: string | null;
  }>;
  key_points: string[];
  metadata: {
    author: string | null;
    author_affiliation: string | null;
    sentiment: string;
    target_audience: string | null;
    is_response_to: string | null;
    references: string[];
  };
}

/** GitHub repository info from enrichment (single repo per enrichment). */
export interface GitHubRepo {
  entityName: string;
  owner: string;
  repo: string;
  fullName: string;
  description: string | null;
  url: string;
  stars: number;
  forks: number;
  language: string | null;
  topics: string[];
  license: string | null;
  homepage: string | null;
  readmeFilename: string | null;
  readmeContent: string | null;
}

/** GitHub enrichment data - single repo per enrichment record. */
export type GitHubEnrichment = GitHubRepo;

/** Web page info from enrichment (single page per enrichment). */
export interface WebPage {
  title: string;
  content: string;
  fetchedAt: string;
}

/** Web page enrichment data - single page per enrichment record. */
export type WebPageEnrichment = WebPage;

/** Entry link candidate from extraction. */
export interface EntryLink {
  id: string;
  url: string;
  title: string;
  createdAt: string;
}

/** Grouped entry links by URL for display. */
export interface GroupedEntryLink {
  url: string;
  titles: string[];
}

/** Entry context data from API. */
export interface EntryContext {
  context: ExtractedContext | null;
  contextSavedAt: string | null;
  keepContext: boolean;
  enrichments: Array<{
    id: string;
    type: string;
    data: GitHubEnrichment | WebPageEnrichment | Record<string, unknown> | null;
    source: string | null;
    metadata: Record<string, unknown> | null;
    createdAt: string;
    expiresAt: string | null;
  }>;
  links: EntryLink[];
}
