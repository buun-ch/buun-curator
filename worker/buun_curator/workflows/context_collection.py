"""
Context Collection Workflow.

High-level workflow for collecting and analyzing entry contexts.
Orchestrates ExtractEntryContextWorkflow for multiple entries and creates
an execution plan based on the extracted contexts.
"""

import hashlib
import re
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    # Pre-import idna modules to avoid sandbox warnings
    # (used by url-normalize for internationalized domain names)
    import idna.core  # noqa: F401
    import idna.intranges  # noqa: F401
    import idna.package_data  # noqa: F401
    import idna.uts46data  # noqa: F401

    from buun_curator.activities import (
        delete_enrichment,
        fetch_github_readme,
        rerank_github_results,
        save_entry_links,
        save_github_enrichment,
        search_github_candidates,
    )
    from buun_curator.models import (
        ContextCollectionInput,
        ContextCollectionOutput,
        ContextCollectionProgress,
        DeleteEnrichmentActivityInput,
        EnrichmentCandidate,
        EntryLinkInfo,
        EntryProgressState,
        ExtractEntryContextInput,
        FetchGitHubReadmeInput,
        RerankGitHubInput,
        SaveEntryLinksInput,
        SaveGitHubEnrichmentInput,
        SearchGitHubCandidatesInput,
    )
    from buun_curator.models.context import EntryContext, ExtractedLink
    from buun_curator.utils.date import workflow_now_iso
    from buun_curator.utils.url import normalize_url_for_dedup
    from buun_curator.workflows.extract_entry_context import (
        ExtractEntryContextWorkflow,
    )
    from buun_curator.workflows.progress_mixin import ProgressNotificationMixin

# Well-known software that doesn't need GitHub enrichment
SKIP_SOFTWARE = {
    "python",
    "javascript",
    "typescript",
    "java",
    "rust",
    "go",
    "ruby",
    "php",
    "c",
    "c++",
    "c#",
    "swift",
    "kotlin",
    "scala",
    "perl",
    "r",
    "sql",
    "html",
    "css",
    "shell",
    "bash",
    "powershell",
    "vs code",
    "visual studio code",
    "vscode",
    "pycharm",
    "intellij",
    "eclipse",
    "xcode",
    "vim",
    "neovim",
    "emacs",
    "sublime text",
    "git",
    "github",
    "gitlab",
    "docker",
    "kubernetes",
    "linux",
    "windows",
    "macos",
    "android",
    "ios",
    "chrome",
    "firefox",
    "safari",
    "edge",
    "node.js",
    "nodejs",
    "npm",
    "yarn",
    "pip",
    "conda",
    "wasm",
    "webassembly",
}


def _extract_github_urls(links: list[ExtractedLink]) -> dict[str, str]:
    """
    Extract GitHub URLs from extracted links.

    Returns a mapping of repo name -> full URL.
    """
    github_urls: dict[str, str] = {}
    for link in links:
        match = re.match(r"https?://github\.com/([^/]+)/([^/]+)", link.url)
        if match:
            repo_name = match.group(2).lower()
            # Remove .git suffix if present
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
            github_urls[repo_name] = link.url
    return github_urls


def _find_creator(
    entity_name: str,
    relationships: list,
) -> str | None:
    """
    Find the creator of an entity from relationships.

    Looks for createdBy relationships where entity is the source.
    """
    for rel in relationships:
        if rel.source == entity_name and str(rel.relation) == "createdBy":
            return rel.target
    return None


def _create_enrichment_candidates(context: EntryContext) -> list[EnrichmentCandidate]:
    """
    Create enrichment candidates from a context.

    Identifies Software entities that should be enriched with GitHub info.

    Parameters
    ----------
    context : EntryContext
        The entry context to analyze.

    Returns
    -------
    list[EnrichmentCandidate]
        List of entities that should be enriched.
    """
    candidates: list[EnrichmentCandidate] = []

    # Only process software-related domains
    if str(context.domain) not in ("software", "technology"):
        return candidates

    # Extract GitHub URLs from extracted links
    github_urls = _extract_github_urls(context.extracted_links)

    for entity in context.entities:
        # Only consider Software entities
        if str(entity.type) != "Software":
            continue

        # Skip well-known software
        if entity.name.lower() in SKIP_SOFTWARE:
            continue

        # Prioritize subject and compared roles
        role = str(entity.role) if entity.role else None
        if role not in ("subject", "compared", None):
            # Skip entities that are only mentioned
            continue

        # Find creator from relationships
        owner_hint = _find_creator(entity.name, context.relationships)

        # Check if there's a GitHub URL for this entity
        github_url_hint = None
        entity_name_lower = entity.name.lower()
        for repo_name, url in github_urls.items():
            if entity_name_lower in repo_name or repo_name in entity_name_lower:
                github_url_hint = url
                break

        candidates.append(
            EnrichmentCandidate(
                name=entity.name,
                entity_type=str(entity.type),
                role=role,
                owner_hint=owner_hint,
                github_url_hint=github_url_hint,
            )
        )

    return candidates


def _analyze_contexts(contexts: list[EntryContext]) -> list[str]:
    """
    Analyze extracted contexts and generate an execution plan.

    Parameters
    ----------
    contexts : list[EntryContext]
        List of extracted entry contexts.

    Returns
    -------
    list[str]
        List of planned actions based on context analysis.
    """
    plan: list[str] = []

    if not contexts:
        plan.append("No contexts extracted - nothing to process")
        return plan

    # Analyze domains
    domains = {}
    for ctx in contexts:
        domain = str(ctx.domain)
        domains[domain] = domains.get(domain, 0) + 1

    plan.append(f"Extracted {len(contexts)} entry contexts")
    plan.append(f"Domain distribution: {domains}")

    # Analyze entities
    all_entities = []
    entity_types = {}
    for ctx in contexts:
        for entity in ctx.entities:
            all_entities.append(entity)
            entity_type = str(entity.type)
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

    plan.append(f"Total entities extracted: {len(all_entities)}")
    plan.append(f"Entity type distribution: {entity_types}")

    # Analyze relationships
    all_relationships = []
    relation_types = {}
    for ctx in contexts:
        for rel in ctx.relationships:
            all_relationships.append(rel)
            rel_type = str(rel.relation)
            relation_types[rel_type] = relation_types.get(rel_type, 0) + 1

    plan.append(f"Total relationships extracted: {len(all_relationships)}")
    if relation_types:
        plan.append(f"Relationship type distribution: {relation_types}")

    # Identify common entities across entries
    entity_names = {}
    for ctx in contexts:
        for entity in ctx.entities:
            entity_names[entity.name] = entity_names.get(entity.name, 0) + 1

    common_entities = [(name, count) for name, count in entity_names.items() if count > 1]
    if common_entities:
        common_entities.sort(key=lambda x: x[1], reverse=True)
        plan.append(
            f"Common entities across entries: "
            f"{[f'{name} ({count})' for name, count in common_entities[:10]]}"
        )

    # Suggested next steps
    plan.append("--- Suggested Next Steps ---")

    if len(contexts) > 1 and common_entities:
        plan.append("SUGGEST: Build knowledge graph connections for common entities")

    if all_relationships:
        plan.append("SUGGEST: Index relationships for graph-based retrieval")

    # Check for entities that might need enrichment
    entities_without_description = sum(1 for e in all_entities if not e.description)
    if entities_without_description > 0:
        plan.append(f"SUGGEST: Enrich {entities_without_description} entities without descriptions")

    return plan


def _collect_enrichment_candidates(
    contexts: list[EntryContext],
) -> list[EnrichmentCandidate]:
    """
    Collect all enrichment candidates from contexts.

    Parameters
    ----------
    contexts : list[EntryContext]
        List of extracted entry contexts.

    Returns
    -------
    list[EnrichmentCandidate]
        Deduplicated list of enrichment candidates.
    """
    candidates: list[EnrichmentCandidate] = []
    seen_names: set[str] = set()

    for ctx in contexts:
        for candidate in _create_enrichment_candidates(ctx):
            # Deduplicate by name (case-insensitive)
            name_lower = candidate.name.lower()
            if name_lower not in seen_names:
                seen_names.add(name_lower)
                candidates.append(candidate)

    return candidates


def _collect_entry_links(
    contexts: list[EntryContext],
) -> list[EntryLinkInfo]:
    """
    Collect unique links from contexts.

    Normalizes URLs for deduplication. When multiple links have the same
    normalized URL, the shorter title is kept.

    Parameters
    ----------
    contexts : list[EntryContext]
        List of extracted entry contexts with extracted_links.

    Returns
    -------
    list[EntryLinkInfo]
        Deduplicated list of entry links with normalized URLs.
    """
    # Map: normalized_url -> (original_url, title)
    # We keep original URL for display, normalized for dedup
    url_map: dict[str, tuple[str, str]] = {}

    def add_url(url: str, title: str | None) -> None:
        """Add URL to map, keeping shorter title if duplicate."""
        normalized = normalize_url_for_dedup(url)
        link_title = title or ""

        if normalized in url_map:
            existing_url, existing_title = url_map[normalized]
            # Keep shorter title if both exist
            if link_title and existing_title:
                if len(link_title) < len(existing_title):
                    url_map[normalized] = (existing_url, link_title)
            elif link_title and not existing_title:
                url_map[normalized] = (existing_url, link_title)
        else:
            url_map[normalized] = (url, link_title)

    # Collect from extracted_links in contexts
    for ctx in contexts:
        for link in ctx.extracted_links:
            add_url(link.url, link.text if link.text else None)

    # Convert to EntryLinkInfo list
    return [
        EntryLinkInfo(url=normalized_url, title=title)
        for normalized_url, (_, title) in url_map.items()
    ]


@workflow.defn
class ContextCollectionWorkflow(ProgressNotificationMixin):
    """
    High-level workflow for collecting and analyzing entry contexts.

    Orchestrates ExtractEntryContextWorkflow for multiple entries,
    analyzes the extracted contexts, and creates an execution plan
    for further processing.
    """

    def __init__(self) -> None:
        """Initialize workflow progress state."""
        self._progress = ContextCollectionProgress()

    @workflow.query
    def get_progress(self) -> ContextCollectionProgress:
        """Return current workflow progress for Temporal Query."""
        return self._progress

    def _update_entry_status(self, entry_id: str, status: str, error: str = "") -> None:
        """Update status for a specific entry."""
        now = workflow_now_iso()
        if entry_id in self._progress.entry_progress:
            self._progress.entry_progress[entry_id].status = status
            self._progress.entry_progress[entry_id].changed_at = now
            if error:
                self._progress.entry_progress[entry_id].error = error
        self._progress.updated_at = now

    async def _extract_all_contexts(
        self,
        entry_ids: list[str],
    ) -> tuple[list[EntryContext], int, int]:
        """
        Extract contexts for all entries using child workflows.

        Parameters
        ----------
        entry_ids : list[str]
            List of entry IDs to process.

        Returns
        -------
        tuple[list[EntryContext], int, int]
            Tuple of (contexts, successful_count, failed_count).
        """
        wf_info = workflow.info()
        contexts: list[EntryContext] = []
        successful = 0
        failed = 0

        for entry_id in entry_ids:
            # Generate unique child workflow ID
            hash_input = f"{wf_info.workflow_id}:{wf_info.run_id}:{entry_id}"
            unique_suffix = hashlib.sha1(hash_input.encode()).hexdigest()[:7]
            child_wf_id = f"extract-context-{unique_suffix}"

            workflow.logger.info("Extracting context for entry", extra={"entry_id": entry_id})
            self._update_entry_status(entry_id, "extracting")
            await self._notify_update()

            try:
                context = await workflow.execute_child_workflow(
                    ExtractEntryContextWorkflow.run,
                    ExtractEntryContextInput(entry_id=entry_id),
                    id=child_wf_id,
                    execution_timeout=timedelta(minutes=5),
                )

                if context is not None:
                    contexts.append(context)
                    successful += 1
                    self._progress.successful_extractions = successful
                    self._update_entry_status(entry_id, "completed")
                    workflow.logger.info(
                        "Context extracted",
                        extra={
                            "entry_id": entry_id,
                            "domain": str(context.domain),
                            "entities": len(context.entities),
                            "relationships": len(context.relationships),
                        },
                    )
                else:
                    failed += 1
                    self._progress.failed_extractions = failed
                    self._update_entry_status(entry_id, "error", "No context returned")
                    workflow.logger.warning("No context returned", extra={"entry_id": entry_id})

            except Exception as e:
                failed += 1
                self._progress.failed_extractions = failed
                self._update_entry_status(entry_id, "error", str(e))
                workflow.logger.error(
                    f"Failed to extract context: {e}", extra={"entry_id": entry_id}
                )

            await self._notify_update()

        return contexts, successful, failed

    async def _execute_github_enrichment(
        self,
        candidates: list[EnrichmentCandidate],
        contexts: list[EntryContext],
        plan: list[str],
    ) -> list[dict]:
        """
        Execute GitHub search and re-ranking for enrichment candidates.

        Parameters
        ----------
        candidates : list[EnrichmentCandidate]
            List of enrichment candidates to search.
        contexts : list[EntryContext]
            Extracted contexts (for key_points).
        plan : list[str]
            Execution plan to append results to.

        Returns
        -------
        list[dict]
            List of enrichment results.
        """
        if not candidates:
            return []

        self._progress.current_step = "enrich"
        self._progress.message = f"Enriching {len(candidates)} candidates..."
        await self._notify_update()

        workflow.logger.info("Executing GitHub search", extra={"candidates": len(candidates)})
        plan.append("--- GitHub Enrichment Execution ---")

        # Collect key_points from all contexts for LLM re-ranking
        all_key_points: list[str] = []
        for ctx in contexts:
            all_key_points.extend(ctx.key_points)

        enrichment_results: list[dict] = []

        for candidate in candidates:
            workflow.logger.info(
                f"Searching GitHub for: {candidate.name} (owner_hint={candidate.owner_hint})"
            )

            try:
                result = await self._search_and_rerank_candidate(candidate, all_key_points, plan)
                enrichment_results.append(result)
            except Exception as e:
                enrichment_results.append(
                    {
                        "name": candidate.name,
                        "found": False,
                        "error": str(e),
                    }
                )
                plan.append(f"  ERROR: {candidate.name} - {e}")
                workflow.logger.error(f"Error searching for {candidate.name}: {e}")

        return enrichment_results

    async def _search_and_rerank_candidate(
        self,
        candidate: EnrichmentCandidate,
        all_key_points: list[str],
        plan: list[str],
    ) -> dict:
        """
        Search GitHub and re-rank results for a single candidate.

        Parameters
        ----------
        candidate : EnrichmentCandidate
            The candidate to search for.
        all_key_points : list[str]
            Key points from all contexts for re-ranking.
        plan : list[str]
            Execution plan to append results to.

        Returns
        -------
        dict
            Enrichment result dict.
        """
        # Search for candidates
        search_result = await workflow.execute_activity(
            search_github_candidates,
            SearchGitHubCandidatesInput(
                query=candidate.name,
                owner_hint=candidate.owner_hint,
                max_candidates=5,
            ),
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not search_result.candidates:
            plan.append(f"  NOT FOUND: {candidate.name}")
            workflow.logger.info(f"No candidates found: {candidate.name}")
            return {
                "name": candidate.name,
                "found": False,
                "error": search_result.error,
            }

        # Re-rank candidates using LLM
        workflow.logger.info(
            f"Re-ranking {len(search_result.candidates)} candidates for {candidate.name}..."
        )

        # Convert candidates to dicts for activity input
        candidates_dicts = [
            {
                "repo": {
                    "owner": c.repo.owner,
                    "repo": c.repo.repo,
                    "full_name": c.repo.full_name,
                    "description": c.repo.description,
                    "url": c.repo.url,
                    "stars": c.repo.stars,
                    "forks": c.repo.forks,
                    "language": c.repo.language,
                    "topics": c.repo.topics,
                    "license": c.repo.license,
                    "homepage": c.repo.homepage,
                },
                "score": c.score,
            }
            for c in search_result.candidates
        ]

        rerank_result = await workflow.execute_activity(
            rerank_github_results,
            RerankGitHubInput(
                query=candidate.name,
                candidates=candidates_dicts,
                entry_key_points=all_key_points[:10],  # Limit to 10
                owner_hint=candidate.owner_hint,
            ),
            start_to_close_timeout=timedelta(seconds=60),
        )

        if not rerank_result.selected:
            plan.append(f"  NOT FOUND: {candidate.name}")
            if rerank_result.reason:
                plan.append(f"    Reason: {rerank_result.reason}")
            workflow.logger.info(f"No match selected for {candidate.name}: {rerank_result.reason}")
            return {
                "name": candidate.name,
                "found": False,
                "error": rerank_result.error or rerank_result.reason,
            }

        # Fetch README for the selected repository
        repo = rerank_result.selected
        readme_filename, readme_content = await self._fetch_readme(repo.owner, repo.repo)

        plan.append(
            f"  FOUND: {candidate.name} -> {repo.full_name} "
            f"(stars={repo.stars}, lang={repo.language})"
        )
        if rerank_result.reason:
            plan.append(f"    Reason: {rerank_result.reason}")
        workflow.logger.info(
            f"Selected: {repo.full_name} (stars={repo.stars}, lang={repo.language})"
        )

        return {
            "name": candidate.name,
            "found": True,
            "repo": {
                "owner": repo.owner,
                "repo": repo.repo,
                "full_name": repo.full_name,
                "description": repo.description,
                "url": repo.url,
                "stars": repo.stars,
                "forks": repo.forks,
                "language": repo.language,
                "topics": repo.topics,
                "license": repo.license,
                "homepage": repo.homepage,
                "readme_filename": readme_filename,
                "readme_content": readme_content,
            },
            "reason": rerank_result.reason,
        }

    async def _fetch_readme(self, owner: str, repo: str) -> tuple[str | None, str | None]:
        """
        Fetch README for a repository.

        Returns
        -------
        tuple[str | None, str | None]
            Tuple of (filename, content) or (None, None) if not found.
        """
        try:
            readme_result = await workflow.execute_activity(
                fetch_github_readme,
                FetchGitHubReadmeInput(owner=owner, repo=repo),
                start_to_close_timeout=timedelta(seconds=30),
            )
            if readme_result.found:
                workflow.logger.info(
                    f"Fetched README: {readme_result.filename} "
                    f"({len(readme_result.content or '')} chars)"
                )
                return readme_result.filename, readme_result.content
        except Exception as e:
            workflow.logger.warning(f"Failed to fetch README for {owner}/{repo}: {e}")
        return None, None

    async def _save_enrichments(
        self,
        entry_ids: list[str],
        enrichment_results: list[dict],
    ) -> None:
        """
        Clear stale enrichments and save new ones.

        Parameters
        ----------
        entry_ids : list[str]
            List of entry IDs to save enrichments for.
        enrichment_results : list[dict]
            List of enrichment results from GitHub search.
        """
        self._progress.current_step = "save"
        self._progress.message = "Saving enrichments..."
        await self._notify_update()

        # Clear web_page enrichments (not re-created by this workflow)
        workflow.logger.info(f"Clearing web_page enrichments for {len(entry_ids)} entries...")
        for entry_id in entry_ids:
            try:
                await workflow.execute_activity(
                    delete_enrichment,
                    DeleteEnrichmentActivityInput(
                        entry_id=entry_id,
                        enrichment_type="web_page",
                        source=None,  # Delete all web_page enrichments
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                )
            except Exception as e:
                workflow.logger.warning(f"Failed to clear web_page enrichments for {entry_id}: {e}")

        # Save GitHub enrichments (also clears stale ones internally)
        if not enrichment_results:
            return

        found_results = [er for er in enrichment_results if er.get("found")]
        workflow.logger.info(
            f"Saving {len(found_results)} enrichments to {len(entry_ids)} entries..."
        )

        for entry_id in entry_ids:
            try:
                save_result = await workflow.execute_activity(
                    save_github_enrichment,
                    SaveGitHubEnrichmentInput(
                        entry_id=entry_id,
                        enrichment_results=enrichment_results,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                )
                if save_result.success:
                    workflow.logger.info(
                        f"Saved {save_result.saved_count} enrichments for entry {entry_id}"
                    )
                else:
                    workflow.logger.warning(
                        f"Failed to save enrichments for {entry_id}: {save_result.error}"
                    )
            except Exception as e:
                workflow.logger.error(f"Error saving enrichments for {entry_id}: {e}")

    async def _save_entry_links(
        self,
        entry_ids: list[str],
        contexts: list[EntryContext],
        plan: list[str],
    ) -> None:
        """
        Collect and save entry links from contexts.

        Parameters
        ----------
        entry_ids : list[str]
            List of entry IDs to save links for.
        contexts : list[EntryContext]
            Extracted contexts with links.
        plan : list[str]
            Execution plan to append results to.
        """
        entry_links = _collect_entry_links(contexts)

        if not entry_links:
            return

        workflow.logger.info(f"Saving {len(entry_links)} links to {len(entry_ids)} entries...")
        plan.append("--- Entry Links ---")
        plan.append(f"Collected {len(entry_links)} unique links")

        for entry_id in entry_ids:
            try:
                save_result = await workflow.execute_activity(
                    save_entry_links,
                    SaveEntryLinksInput(
                        entry_id=entry_id,
                        links=entry_links,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                )
                if save_result.success:
                    workflow.logger.info(
                        f"Saved {save_result.saved_count} links for entry {entry_id}"
                    )
                else:
                    workflow.logger.warning(
                        f"Failed to save links for {entry_id}: {save_result.error}"
                    )
            except Exception as e:
                workflow.logger.error(f"Error saving links for {entry_id}: {e}")

    @workflow.run
    async def run(self, input: ContextCollectionInput) -> ContextCollectionOutput:
        """
        Execute context collection for multiple entries.

        Parameters
        ----------
        input : ContextCollectionInput
            Input containing list of entry_ids to process.

        Returns
        -------
        ContextCollectionOutput
            Results including extraction statistics and execution plan.
        """
        wf_info = workflow.info()

        # Initialize progress state
        now = workflow_now_iso()
        self._progress.workflow_id = wf_info.workflow_id
        self._progress.started_at = now
        self._progress.updated_at = now
        self._progress.status = "running"
        self._progress.current_step = "initializing"
        self._progress.message = "Starting context collection..."
        self._progress.total_entries = len(input.entry_ids)

        workflow.logger.info(
            "ContextCollectionWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "entries": len(input.entry_ids),
            },
        )

        if not input.entry_ids:
            workflow.logger.warning("No entry IDs provided")

            self._progress.status = "completed"
            self._progress.current_step = "done"
            self._progress.message = "No entries to process"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()

            return ContextCollectionOutput(
                status="completed",
                total_entries=0,
                plan=["No entries to process"],
            )

        try:
            return await self._run_context_collection(input)
        except Exception as e:
            # Send error notification via SSE before failing the workflow
            error_msg = str(e)
            self._progress.status = "error"
            self._progress.error = error_msg
            self._progress.message = f"Context collection failed: {error_msg}"
            for entry_id in self._progress.entry_progress:
                self._update_entry_status(entry_id, "error", error=error_msg)
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()
            raise

    async def _run_context_collection(
        self, input: ContextCollectionInput
    ) -> ContextCollectionOutput:
        """
        Run the main context collection logic.

        Separated from run() to enable top-level error handling with SSE notification.
        """
        now = workflow_now_iso()

        # Initialize entry progress tracking
        for entry_id in input.entry_ids:
            self._progress.entry_progress[entry_id] = EntryProgressState(
                entry_id=entry_id,
                title="",  # Title unknown until extraction
                status="pending",
                changed_at=now,
            )
        await self._notify_update()

        # Step 1: Extract contexts for all entries
        self._progress.current_step = "extract"
        self._progress.message = f"Extracting contexts for {len(input.entry_ids)} entries..."
        await self._notify_update()

        contexts, successful, failed = await self._extract_all_contexts(input.entry_ids)

        # Step 2: Analyze contexts and create plan
        workflow.logger.info(
            f"Context extraction complete: {successful} successful, {failed} failed"
        )
        workflow.logger.info("Analyzing contexts and creating execution plan...")

        self._progress.current_step = "analyze"
        self._progress.message = "Analyzing contexts..."
        await self._notify_update()

        plan = _analyze_contexts(contexts)

        # Step 3: Collect enrichment candidates
        candidates = _collect_enrichment_candidates(contexts)
        self._progress.enrichment_candidates_count = len(candidates)
        await self._notify_update()

        # Step 4: Execute GitHub enrichment
        enrichment_results = await self._execute_github_enrichment(candidates, contexts, plan)

        # Step 5: Debug output the plan
        workflow.logger.info("- - - - - EXECUTION PLAN - - - - -")
        for i, step in enumerate(plan, 1):
            workflow.logger.info(f"  [{i}] {step}")
        workflow.logger.info("- - - - - - - - - - - - - - - - - - ")

        # Step 6: Save enrichments
        await self._save_enrichments(input.entry_ids, enrichment_results)

        # Step 7: Save entry links
        await self._save_entry_links(input.entry_ids, contexts, plan)

        # Determine status
        if failed == 0:
            status = "completed"
        elif successful == 0:
            status = "error"
        else:
            status = "partial"

        workflow.logger.info(
            "ContextCollectionWorkflow end",
            extra={"status": status},
        )

        # Update final progress state
        self._progress.status = status
        self._progress.current_step = "done"
        self._progress.message = f"Completed: {successful} extracted, {failed} failed" + (
            f", {len(candidates)} enriched" if candidates else ""
        )
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        return ContextCollectionOutput(
            status=status,
            total_entries=len(input.entry_ids),
            successful_extractions=successful,
            failed_extractions=failed,
            plan=plan,
            enrichment_results=enrichment_results,
        )
