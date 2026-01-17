"""
Context extraction Activity.

Extract structured context from entries using LangChain structured output.
Aligned with buun_curator_ontology for Cognee compatibility.
"""

from typing import cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from markdown import Markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from pydantic import BaseModel, Field, SecretStr
from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import ExtractEntryContextActivityInput
from buun_curator.models.context import (
    ContentType,
    EntityInfo,
    EntityRole,
    EntityType,
    EntryContext,
    EntryMetadata,
    ExtractedLink,
    Relationship,
    RelationType,
    Sentiment,
    SubjectDomain,
)

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────
# Markdown Link Extraction
# ─────────────────────────────────────────────────────────────────


class _LinkExtractorTreeProcessor(Treeprocessor):
    """TreeProcessor that extracts links from parsed Markdown."""

    def __init__(self, md: Markdown) -> None:
        super().__init__(md)
        self.links: list[dict[str, str]] = []

    def run(self, root):  # type: ignore[no-untyped-def]
        """Traverse the element tree and extract all <a> tags."""
        for element in root.iter():
            if element.tag == "a":
                href = element.get("href", "")
                text = "".join(element.itertext())
                if href:  # Only include links with actual URLs
                    self.links.append({"text": text, "url": href})
        return root


class _LinkExtractorExtension(Extension):
    """Markdown extension for extracting links."""

    def __init__(self) -> None:
        super().__init__()
        self.extractor: _LinkExtractorTreeProcessor | None = None

    def extendMarkdown(self, md: Markdown) -> None:
        """Register the link extractor tree processor."""
        self.extractor = _LinkExtractorTreeProcessor(md)
        md.treeprocessors.register(self.extractor, "link_extractor", 0)


def extract_markdown_links(content: str) -> list[ExtractedLink]:
    """
    Extract all links from Markdown content.

    Uses the markdown library's parser to properly handle escaped characters
    and complex link syntax.

    Parameters
    ----------
    content : str
        Markdown content to extract links from.

    Returns
    -------
    list[ExtractedLink]
        List of extracted links with text and URL.
    """
    ext = _LinkExtractorExtension()
    md = Markdown(extensions=[ext])
    md.convert(content)

    if ext.extractor is None:
        return []

    return [ExtractedLink(text=link["text"], url=link["url"]) for link in ext.extractor.links]


# ─────────────────────────────────────────────────────────────────
# Pydantic Models for LLM Structured Output
# ─────────────────────────────────────────────────────────────────


class EntityOutput(BaseModel):
    """Extracted entity."""

    name: str = Field(description="Entity name")
    type: str = Field(
        description="Entity type: Person, Organization, Company, "
        "GovernmentOrganization, EducationalOrganization, MediaOrganization, "
        "Community, Place, Country, City, CreativeWork, Article, Book, WebSite, "
        "Software, Product, Service, Event, BusinessEvent, SocialEvent, "
        "Concept, Technology, Topic, Law, FinancialInstrument, Disease, Language"
    )
    role: str | None = Field(
        default=None,
        description="Role in entry: author, subject, mentioned, compared",
    )
    description: str | None = Field(default=None, description="Brief description")


class RelationshipOutput(BaseModel):
    """Relationship between entities."""

    source: str = Field(description="Source entity name")
    relation: str = Field(
        description="Relationship type: createdBy, worksFor, foundedBy, leaderOf, "
        "subsidiaryOf, partnersWith, competesWith, produces, uses, basedOn, "
        "locatedIn, participatesIn, organizedBy, about, mentions, relatedTo, "
        "regulatedBy, affects, inLanguage"
    )
    target: str = Field(description="Target entity name")
    description: str | None = Field(default=None, description="Relationship description")


class MetadataOutput(BaseModel):
    """Entry metadata."""

    author: str | None = Field(default=None, description="Entry author name")
    author_affiliation: str | None = Field(default=None, description="Author's organization")
    sentiment: str = Field(
        default="neutral",
        description="Entry sentiment: positive, negative, neutral, mixed",
    )
    target_audience: str | None = Field(default=None, description="Intended audience")
    is_response_to: str | None = Field(
        default=None,
        description="If this entry responds to something, what is it",
    )


class EntryContextOutput(BaseModel):
    """Structured context extracted from an entry."""

    # Classification
    domain: str = Field(
        description="Subject domain: software, technology, business, research, "
        "people, industry, product, politics, economy, society, health, environment, "
        "other (if none of the above fit)"
    )
    content_type: str = Field(
        description="Entry format/intent: announcement, news, tutorial, opinion, "
        "comparison, proposal, criticism, solution, report, interview, review, "
        "other (if none of the above fit)"
    )
    language: str = Field(
        description="Entry language code (ISO 639-1): en, ja, zh, ko, de, fr, es, etc."
    )
    confidence: float = Field(description="Classification confidence 0.0-1.0")

    # Entities and relationships
    entities: list[EntityOutput] = Field(description="Extracted entities")
    relationships: list[RelationshipOutput] = Field(
        default_factory=list,
        description="Relationships between entities",
    )

    # Content analysis
    key_points: list[str] = Field(description="Main takeaways (3-5 items)")

    # Metadata
    metadata: MetadataOutput = Field(description="Entry metadata")


# ─────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────


EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert at extracting structured context from entries.
Analyze the entry comprehensively and extract:

1. **Classification**
   - **domain**: What subject matter is this entry about?
     - software: OSS, tools, libraries, frameworks, programming languages
     - technology: Hardware, systems, infrastructure, AI/ML
     - business: Companies, startups, organizations, markets, funding
     - research: Academic papers, research findings, science
     - people: Individuals, interviews, profiles, careers
     - industry: Industry trends, movements, events, conferences
     - product: Products, gadgets, consumer services
     - politics: Politics, policy, regulations
     - economy: Economy, finance, markets
     - society: Society, culture, lifestyle
     - health: Health, medical
     - environment: Environment, climate
     - other: Doesn't fit any of the above categories

   - **content_type**: What is the entry's format or intent?
     - announcement: New releases, feature announcements, launches
     - news: News reporting, current events coverage
     - tutorial: How-to guides, educational content, walkthroughs
     - opinion: Personal opinions, analysis, commentary
     - comparison: Comparisons, evaluations, benchmarks
     - proposal: RFCs, design proposals, suggestions
     - criticism: Critiques, problem statements
     - solution: Solutions, workarounds, fixes
     - report: Experiment results, benchmark reports, studies
     - interview: Interviews
     - review: Reviews, evaluations
     - other: Doesn't fit any of the above categories

   - **language**: Detect the entry's language (ISO 639-1 code: en, ja, zh, etc.)

2. **Entities** - Extract all significant entities with their types:
   - Person: Individual people
   - Organization: Generic organizations
   - Company: Businesses, startups
   - GovernmentOrganization: Government agencies
   - EducationalOrganization: Universities, schools, research institutes
   - MediaOrganization: News outlets, publishers
   - Community: Open source projects, communities, groups
   - Place, Country, City: Locations
   - Software: Applications, libraries, frameworks, tools
   - Product: Physical products, gadgets
   - Service: Services, platforms
   - Event, BusinessEvent, SocialEvent: Events, conferences
   - Technology: Technologies, methodologies
   - Topic: Topics, themes
   - Law: Laws, regulations, policies
   - FinancialInstrument: Stocks, currencies, crypto

   Include each entity's role: author, subject, mentioned, compared

   **IMPORTANT**: For company/organization names, use the canonical English name
   without suffixes like 社, 株式会社, Inc., Corp., Ltd. (e.g., "Google" not "Google社")

3. **Relationships** between entities:
   Format: source --[relation]--> target (source performs action on target)

   Active relations (source acts on target):
   - produces: "Meta produces Pyrefly" → source=Meta, target=Pyrefly
   - uses: "Pyrefly uses Rust" → source=Pyrefly, target=Rust
   - competesWith: "Pyrefly competesWith Mypy" → source=Pyrefly, target=Mypy
   - partnersWith: "Google partnersWith Apple" → source=Google, target=Apple
   - affects: "Law affects Industry" → source=Law, target=Industry
   - leaderOf: "CEO leaderOf Company" → source=CEO, target=Company

   Passive relations (source is acted upon by target):
   - createdBy: "Pyrefly createdBy Meta" → source=Pyrefly, target=Meta
   - foundedBy: "Company foundedBy Person" → source=Company, target=Person
   - worksFor: "Person worksFor Company" → source=Person, target=Company
   - subsidiaryOf: "SubCo subsidiaryOf ParentCo" → source=SubCo, target=ParentCo
   - basedOn: "Pyrefly basedOn Rust" → source=Pyrefly, target=Rust
   - locatedIn: "Company locatedIn City" → source=Company, target=City
   - participatesIn: "Person participatesIn Event" → source=Person, target=Event
   - organizedBy: "Event organizedBy Company" → source=Event, target=Company
   - regulatedBy: "Company regulatedBy Law" → source=Company, target=Law
   - relatedTo: General relation

   **IMPORTANT**: Every entity mentioned in relationships (both source and target)
   MUST also appear in the entities list above.

4. **Key Points**: Main takeaways (3-5 bullet points)

5. **Metadata**: Author, sentiment (positive/negative/neutral/mixed), target audience

Respond in the same language as the entry content.""",
        ),
        (
            "user",
            """Entry Title: {title}
Entry URL: {url}
Entry Content:
{content}""",
        ),
    ]
)


# ─────────────────────────────────────────────────────────────────
# Conversion helpers
# ─────────────────────────────────────────────────────────────────


def _safe_enum_lower[T](enum_class: type[T], value: str | None, default: T) -> T:
    """Safely convert lowercase string to enum with fallback."""
    if value is None:
        return default
    try:
        return enum_class(value.lower())  # type: ignore[call-arg]
    except (ValueError, AttributeError):
        return default


def _safe_entity_type(value: str | None) -> EntityType:
    """Safely convert entity type string to EntityType enum."""
    if value is None:
        return EntityType.CONCEPT

    # Try exact match first (PascalCase)
    try:
        return EntityType(value)
    except ValueError:
        pass

    # Try case-insensitive match
    value_lower = value.lower()
    for entity_type in EntityType:
        if entity_type.value.lower() == value_lower:
            return entity_type

    # Fallback mappings for common variations
    mappings = {
        "person": EntityType.PERSON,
        "organization": EntityType.ORGANIZATION,
        "company": EntityType.COMPANY,
        "software": EntityType.SOFTWARE,
        "product": EntityType.PRODUCT,
        "service": EntityType.SERVICE,
        "technology": EntityType.TECHNOLOGY,
        "concept": EntityType.CONCEPT,
        "event": EntityType.EVENT,
        "place": EntityType.PLACE,
        "country": EntityType.COUNTRY,
        "city": EntityType.CITY,
    }
    return mappings.get(value_lower, EntityType.CONCEPT)


def _safe_relation_type(value: str | None) -> RelationType:
    """Safely convert relation type string to RelationType enum."""
    if value is None:
        return RelationType.RELATED_TO

    # Try exact match first (camelCase)
    try:
        return RelationType(value)
    except ValueError:
        pass

    # Try case-insensitive match
    value_lower = value.lower()
    for relation_type in RelationType:
        if relation_type.value.lower() == value_lower:
            return relation_type

    # Fallback mappings for common variations
    mappings = {
        "created_by": RelationType.CREATED_BY,
        "createdby": RelationType.CREATED_BY,
        "works_for": RelationType.WORKS_FOR,
        "worksfor": RelationType.WORKS_FOR,
        "founded_by": RelationType.FOUNDED_BY,
        "foundedby": RelationType.FOUNDED_BY,
        "competes_with": RelationType.COMPETES_WITH,
        "competeswith": RelationType.COMPETES_WITH,
        "partners_with": RelationType.PARTNERS_WITH,
        "partnerswith": RelationType.PARTNERS_WITH,
        "based_on": RelationType.BASED_ON,
        "basedon": RelationType.BASED_ON,
        "located_in": RelationType.LOCATED_IN,
        "locatedin": RelationType.LOCATED_IN,
        "related_to": RelationType.RELATED_TO,
        "relatedto": RelationType.RELATED_TO,
        "uses": RelationType.USES,
        "produces": RelationType.PRODUCES,
        "affects": RelationType.AFFECTS,
    }
    return mappings.get(value_lower, RelationType.RELATED_TO)


def _convert_output(output: EntryContextOutput) -> EntryContext:
    """Convert LLM output to domain model with Enum values."""
    return EntryContext(
        domain=_safe_enum_lower(SubjectDomain, output.domain, SubjectDomain.OTHER),
        content_type=_safe_enum_lower(ContentType, output.content_type, ContentType.OTHER),
        language=output.language or "en",
        confidence=output.confidence,
        entities=[
            EntityInfo(
                name=e.name,
                type=_safe_entity_type(e.type),
                role=_safe_enum_lower(EntityRole, e.role, None) if e.role else None,
                description=e.description,
            )
            for e in output.entities
        ],
        relationships=[
            Relationship(
                source=r.source,
                relation=_safe_relation_type(r.relation),
                target=r.target,
                description=r.description,
            )
            for r in output.relationships
        ],
        key_points=output.key_points,
        metadata=EntryMetadata(
            author=output.metadata.author,
            author_affiliation=output.metadata.author_affiliation,
            sentiment=_safe_enum_lower(Sentiment, output.metadata.sentiment, Sentiment.NEUTRAL),
            target_audience=output.metadata.target_audience,
            is_response_to=output.metadata.is_response_to,
        ),
    )


# ─────────────────────────────────────────────────────────────────
# Activity
# ─────────────────────────────────────────────────────────────────


@activity.defn
async def extract_entry_context(
    input: ExtractEntryContextActivityInput,
) -> EntryContext:
    """
    Extract structured context from an entry.

    Uses LangChain structured output to extract classification, entities,
    relationships, key points, and metadata from the entry content.
    Aligned with buun_curator_ontology for Cognee compatibility.

    Parameters
    ----------
    input : ExtractEntryContextActivityInput
        The entry to analyze (entry_id, title, url, content).

    Returns
    -------
    EntryContext
        Structured context extracted from the entry.
    """
    config = get_config()

    if not config.openai_api_key:
        logger.error("OPENAI_API_KEY not configured")
        raise ValueError("OPENAI_API_KEY not configured")

    logger.info("Extracting context", entry_id=input.entry_id, title=input.title[:50])

    # Create LLM with structured output
    # Uses extraction_llm_model which requires Structured Output support
    # See: https://docs.langchain.com/oss/python/integrations/chat/anthropic#structured-output
    llm = ChatOpenAI(
        model=config.extraction_llm_model,
        base_url=config.openai_base_url or None,  # None = OpenAI direct
        api_key=SecretStr(config.openai_api_key),
    )
    structured_llm = llm.with_structured_output(EntryContextOutput)

    # Create chain
    chain = EXTRACTION_PROMPT | structured_llm

    # Extract links from full content before truncation
    extracted_links = extract_markdown_links(input.content)
    logger.info("Extracted links from content", count=len(extracted_links))

    # Truncate content for token limits
    content = input.content[:4000] if len(input.content) > 4000 else input.content

    # Execute
    result = await chain.ainvoke(
        {
            "title": input.title,
            "url": input.url,
            "content": content,
        }
    )
    output = cast(EntryContextOutput, result)

    # Debug output
    logger.debug(
        "Raw LLM output",
        entry_id=input.entry_id,
        domain=output.domain,
        content_type=output.content_type,
        language=output.language,
        confidence=output.confidence,
        entities_count=len(output.entities),
        relationships_count=len(output.relationships),
        key_points_count=len(output.key_points),
        author=output.metadata.author,
        sentiment=output.metadata.sentiment,
    )

    # Convert to domain model and add extracted links
    context = _convert_output(output)
    context.extracted_links = extracted_links

    logger.info(
        "Context extracted",
        entry_id=input.entry_id,
        domain=str(context.domain.value),
        content_type=str(context.content_type.value),
        language=context.language,
        entities=len(context.entities),
        relationships=len(context.relationships),
        links=len(context.extracted_links),
    )

    return context
