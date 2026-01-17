"""
Context extraction data models.

Models for entry context extraction using LLM structured output.
Uses Pydantic for proper Temporal serialization of Enum values.
Aligned with buun_curator_ontology for Cognee compatibility.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────────────────────────────────────────────
# Enums - Aligned with buun_curator_ontology
# ─────────────────────────────────────────────────────────────────


class SubjectDomain(str, Enum):
    """Entry subject domain."""

    SOFTWARE = "software"  # OSS, tools, libraries, frameworks, programming
    TECHNOLOGY = "technology"  # Hardware, systems, infrastructure, AI/ML
    BUSINESS = "business"  # Companies, startups, organizations, markets
    RESEARCH = "research"  # Academic papers, research, science
    PEOPLE = "people"  # Individuals, interviews, profiles, careers
    INDUSTRY = "industry"  # Industry trends, movements, events
    PRODUCT = "product"  # Products, gadgets, consumer services
    POLITICS = "politics"  # Politics, policy, regulations
    ECONOMY = "economy"  # Economy, finance, markets
    SOCIETY = "society"  # Society, culture, lifestyle
    HEALTH = "health"  # Health, medical
    ENVIRONMENT = "environment"  # Environment, climate
    OTHER = "other"  # Doesn't fit predefined categories


class ContentType(str, Enum):
    """Entry content type/format."""

    ANNOUNCEMENT = "announcement"  # New features, releases, launches
    NEWS = "news"  # News reporting, current events
    TUTORIAL = "tutorial"  # How-to guides, educational content
    OPINION = "opinion"  # Personal opinions, analysis, commentary
    COMPARISON = "comparison"  # Comparisons, evaluations, benchmarks
    PROPOSAL = "proposal"  # RFCs, design proposals
    CRITICISM = "criticism"  # Critiques, problem statements
    SOLUTION = "solution"  # Solutions, workarounds, fixes
    REPORT = "report"  # Benchmarks, experiment results, reports
    INTERVIEW = "interview"  # Interviews
    REVIEW = "review"  # Reviews, evaluations
    OTHER = "other"  # Doesn't fit predefined categories


class EntityType(str, Enum):
    """Entity types aligned with buun_curator_ontology."""

    # Agents
    PERSON = "Person"
    ORGANIZATION = "Organization"
    COMPANY = "Company"
    GOVERNMENT_ORGANIZATION = "GovernmentOrganization"
    EDUCATIONAL_ORGANIZATION = "EducationalOrganization"
    MEDIA_ORGANIZATION = "MediaOrganization"
    COMMUNITY = "Community"

    # Places
    PLACE = "Place"
    COUNTRY = "Country"
    CITY = "City"

    # Creative Works
    CREATIVE_WORK = "CreativeWork"
    ARTICLE = "Article"
    BOOK = "Book"
    WEBSITE = "WebSite"
    SOFTWARE = "Software"

    # Products & Services
    PRODUCT = "Product"
    SERVICE = "Service"

    # Events
    EVENT = "Event"
    BUSINESS_EVENT = "BusinessEvent"
    SOCIAL_EVENT = "SocialEvent"

    # Concepts
    CONCEPT = "Concept"
    TECHNOLOGY = "Technology"
    TOPIC = "Topic"
    LAW = "Law"
    FINANCIAL_INSTRUMENT = "FinancialInstrument"
    DISEASE = "Disease"

    # Language
    LANGUAGE = "Language"


class EntityRole(str, Enum):
    """Role of entity in the entry."""

    AUTHOR = "author"  # Author
    SUBJECT = "subject"  # Main subject
    MENTIONED = "mentioned"  # Mentioned in passing
    COMPARED = "compared"  # Used for comparison


class RelationType(str, Enum):
    """Relationship types aligned with buun_curator_ontology."""

    # Agent Relations
    CREATED_BY = "createdBy"
    WORKS_FOR = "worksFor"
    FOUNDED_BY = "foundedBy"
    LEADER_OF = "leaderOf"

    # Organization Relations
    SUBSIDIARY_OF = "subsidiaryOf"
    PARTNERS_WITH = "partnersWith"
    COMPETES_WITH = "competesWith"

    # Product/Service Relations
    PRODUCES = "produces"
    USES = "uses"
    BASED_ON = "basedOn"

    # Location Relations
    LOCATED_IN = "locatedIn"

    # Event Relations
    PARTICIPATES_IN = "participatesIn"
    ORGANIZED_BY = "organizedBy"

    # Content Relations
    ABOUT = "about"
    MENTIONS = "mentions"
    RELATED_TO = "relatedTo"

    # Regulatory Relations
    REGULATED_BY = "regulatedBy"
    AFFECTS = "affects"

    # Language Relations
    IN_LANGUAGE = "inLanguage"


class Sentiment(str, Enum):
    """Sentiment."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


# ─────────────────────────────────────────────────────────────────
# Pydantic Models with Enum serialization support
# ─────────────────────────────────────────────────────────────────


class EntityInfo(BaseModel):
    """Entity extracted from entry."""

    model_config = ConfigDict(use_enum_values=True)

    name: str
    type: EntityType
    role: EntityRole | None = None
    description: str | None = None


class Relationship(BaseModel):
    """Relationship between two entities."""

    model_config = ConfigDict(use_enum_values=True)

    source: str  # Source entity name
    relation: RelationType  # Relationship type (ontology property)
    target: str  # Target entity name
    description: str | None = None


class EntryMetadata(BaseModel):
    """Entry metadata extracted from content."""

    model_config = ConfigDict(use_enum_values=True)

    author: str | None = None
    author_affiliation: str | None = None
    sentiment: Sentiment = Sentiment.NEUTRAL
    target_audience: str | None = None
    is_response_to: str | None = None


class ExtractedLink(BaseModel):
    """Link extracted from Markdown content."""

    text: str
    url: str


class EntryContext(BaseModel):
    """
    Structured context extracted from an entry.

    Aligned with buun_curator_ontology for Cognee compatibility.
    Uses Pydantic with use_enum_values=True for Temporal serialization.
    """

    model_config = ConfigDict(use_enum_values=True)

    # Classification
    domain: SubjectDomain  # What the entry is about
    content_type: ContentType  # Format/intent of the entry
    language: str  # Entry language (ISO 639-1)
    confidence: float  # Classification confidence (0.0-1.0)

    # Entities and relationships
    entities: list[EntityInfo] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)

    # Content analysis
    key_points: list[str] = Field(default_factory=list)  # Main takeaways (3-5)

    # Links extracted from Markdown content
    extracted_links: list[ExtractedLink] = Field(default_factory=list)

    # Metadata
    metadata: EntryMetadata = Field(default_factory=EntryMetadata)
