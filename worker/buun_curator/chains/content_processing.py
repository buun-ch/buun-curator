"""
Content Processing Chain.

LangChain LCEL chain for entry content processing (filtering + summarization).
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from buun_curator.models.entry import (
    BatchContentProcessingOutput,
    ContentProcessingLLMOutput,
)

SYSTEM_PROMPT = """You are an expert at analyzing and summarizing entries.
Your task is to:
1. Identify where the main article content starts and ends
2. Create a concise summary of the main content

You will receive Markdown content with line numbers (e.g., "1: ", "2: ", etc.).
Find the line numbers where the MAIN ARTICLE starts and ends.

Lines BEFORE the main article (to exclude) typically include:
- Site navigation and menus
- Header elements and logos
- Breadcrumb navigation
- Social sharing buttons at the top
- Publication date/author info that's separate from the article
- Language/translation selectors

Lines AFTER the main article (to exclude) typically include:
- Author biography sections
- "Related articles" or "Recommended reading" sections
- Comment sections
- Newsletter signup forms
- Social sharing buttons at the bottom
- Footer navigation
- Advertisement placeholders
- Previous/next article links
- PR and sponsorship disclaimers
- News headlines or updates not part of the article
- Consecutive link or image lines are likely non-article content

OUTPUT INSTRUCTIONS:
- main_content_start_line: The LINE NUMBER where the main article STARTS (1-indexed)
- main_content_end_line: The LINE NUMBER where the main article ENDS (1-indexed)
- Both must be valid line numbers that exist in the content
- main_content_end_line must be >= main_content_start_line
- Be CONSERVATIVE: if unsure, include more lines rather than fewer
- The main article content MUST be preserved - never exclude the article body
- Write the summary in **{language}** (not the original language)"""

USER_PROMPT = """Analyze this entry and provide:
1. The line number where the main article content STARTS
2. The line number where the main article content ENDS
3. A 3-4 sentence summary of the main article content in **{language}** (not the original language)

Title: {title}

Content (with line numbers):
{content}"""


def create_content_processing_chain(llm: ChatOpenAI) -> Runnable:
    """
    Create a content processing chain using LCEL with Structured Output.

    Parameters
    ----------
    llm : ChatOpenAI
        The language model to use.

    Returns
    -------
    Runnable
        A chain that takes {"language": str, "title": str, "content": str}
        and returns ContentProcessingLLMOutput.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("user", USER_PROMPT),
        ]
    )
    structured_llm = llm.with_structured_output(ContentProcessingLLMOutput)
    return prompt | structured_llm


# Batch processing prompts
BATCH_SYSTEM_PROMPT = """You are an expert at analyzing and summarizing entries.
You will receive MULTIPLE entries to process in a single request.

For EACH entry, you must:
1. Identify where the main article content starts and ends
2. Create a concise summary of the main content

Each entry has Markdown content with line numbers (e.g., "1: ", "2: ", etc.).
Find the line numbers where the MAIN ARTICLE starts and ends.

Lines BEFORE the main article (to exclude) typically include:
- Site navigation and menus
- Header elements and logos
- Breadcrumb navigation
- Social sharing buttons at the top
- Publication date/author info that's separate from the article
- Language/translation selectors

Lines AFTER the main article (to exclude) typically include:
- Author biography sections
- "Related articles" or "Recommended reading" sections
- Comment sections
- Newsletter signup forms
- Social sharing buttons at the bottom
- Footer navigation
- Advertisement placeholders
- Previous/next article links
- PR and sponsorship disclaimers
- News headlines or updates not part of the article
- Consecutive link or image lines are likely non-article content

CRITICAL INSTRUCTIONS:
- Each entry has its OWN independent line numbering starting from 1
- The TOTAL_LINES shown in each entry header is the total for THAT entry only
- main_content_start_line and main_content_end_line must be valid line numbers within TOTAL_LINES
- main_content_end_line must be >= main_content_start_line
- Process ALL entries provided - do not skip any
- Return results in the SAME ORDER as the input entries
- Use the exact ENTRY_ID provided for each entry
- Be CONSERVATIVE: if unsure, include more lines rather than fewer
- The main content MUST be preserved - never exclude the article body
- Write all summaries in **{language}** (not the original language)"""

BATCH_USER_PROMPT = """Process the following {entry_count} entries.
Return a result for EACH entry with its ENTRY_ID.

For each entry, provide:
1. main_content_start_line: The line number where the main article STARTS
2. main_content_end_line: The line number where the main article ENDS
3. summary: A 3-4 sentence summary in **{language}** (not the original language)

REMINDER: Each entry has independent line numbering. Check TOTAL_LINES for each entry.

{entries}

IMPORTANT: Return results for ALL {entry_count} entries listed above."""


def create_batch_content_processing_chain(llm: ChatOpenAI) -> Runnable:
    """
    Create a batch content processing chain using LCEL with Structured Output.

    Parameters
    ----------
    llm : ChatOpenAI
        The language model to use.

    Returns
    -------
    Runnable
        A chain that takes {"language": str, "entry_count": int, "entries": str}
        and returns BatchContentProcessingOutput.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", BATCH_SYSTEM_PROMPT),
            ("user", BATCH_USER_PROMPT),
        ]
    )
    structured_llm = llm.with_structured_output(BatchContentProcessingOutput)
    return prompt | structured_llm
