# Terminology

Common terms used throughout Buun Curator documentation and codebase.

## Core Concepts

- **Entry** - A unit of content from a Feed (e.g., a blog post, news item). Use "Entry", NOT "Article".
- **Feed** - An RSS/Atom feed subscription that provides Entries.
- **Category** - A grouping of Feeds for organization.
- **Subscription** - Generic term for items in the sidebar (Feeds, Categories, or special items like "All").

## Worker Operations

- **Crawl** - Parsing RSS/Atom feeds to discover new entries and save them to the database.
- **Fetch** - Retrieving full entry content from URLs using Crawl4AI. Converts HTML to clean Markdown.
- **Distill** - The process of refining raw entry content into a more useful form. Consists of two steps:
    - **Filtering** - Removing noise like ads, navigation, and boilerplate
    - **Summarizing** - Generating a concise summary using LLM

## Context & Enrichment

- **Context Extraction** - LLM-based analysis of entry content to extract structured metadata: classification, entities, relationships, and key points.
- **Enrichment** - Additional data attached to entries from external sources (e.g., GitHub repository info, fetched web pages).

## Research

- **Deep Research** - Multi-agent research workflow using LangGraph. Analyzes queries, searches multiple sources, and synthesizes comprehensive answers.
- **Document** - Abstract container for retrieved content in the research workflow. Represents any searchable content regardless of source (Entry from Meilisearch, web page from Tavily, academic paper, etc.). Used as `RetrievedDoc` in code.
