

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class DocumentChunk(BaseModel):
    """
    Our 'Index Card' data model.
    Represents one single piece cut out from a manual, runbook, or code file.
    """

    # 1. A unique barcode ID for this chunk (e.g. "redis_runbook.md#section_1")
    # 'str' stands for 'string', which means plain text in Python.
    chunk_id: str = Field(
        description="A unique ID barcode for this piece of text"
    )

    # 2. The actual text, table, or code snippet that the AI will read.
    content: str = Field(
        description="The actual text content inside this chunk"
    )

    # 3. The name of the file this chunk was cut from (e.g. "runbook_redis_cluster.md")
    source: str = Field(
        description="The filename or document where this came from"
    )

    # 4. The type of document: 'markdown', 'pdf', 'code', or 'log'
    doc_type: str = Field(
        description="The category of file this chunk belongs to"
    )

    # 5. The section or chapter title this was under (e.g. "## 3. Mitigation and Recovery Steps")
    # 'Optional[str]' means this can be text, OR it can be None (empty) if there was no title.
    section_title: Optional[str] = Field(
        default=None,
        description="Heading or section name, if one exists"
    )

    # 6. Page number (useful when we read PDF documents)
    # 'Optional[int]' means an optional whole number (integer).
    page_number: Optional[int] = Field(
        default=None,
        description="The PDF page number where this chunk was found"
    )

    # 7. Token count: How many "AI tokens" (sub-words) this chunk uses up.
    # We default this to 0 until our tokenizer counts it.
    token_count: int = Field(
        default=0,
        description="Exact number of tokens this chunk consumes in an LLM prompt"
    )

    # 8. Extra metadata: A Python dictionary (key-value pairs) for any extra info.
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Any extra details like line numbers or authors"
    )

    # In Python, a "def" inside a class is called a method (a custom function).
    # This function creates a neat citation receipt that the user can read.
    def citation_label(self) -> str:
        """
        Builds a clean citation tag for this chunk.
        Example output:
        '[runbook_redis_cluster.md, Section: Mitigation and Recovery Steps]'
        """
        # Grab just the clean filename without the folder path
        clean_filename = self.source.replace("\\", "/").split("/")[-1]
        parts = [clean_filename]

        # If there is a section title, add it to the label
        if self.section_title:
            parts.append(f"Section: {self.section_title}")

        # If there is a page number, add it to the label
        if self.page_number is not None:
            parts.append(f"p. {self.page_number}")

        # Join the parts together inside square brackets [ ... ]
        return f"[{', '.join(parts)}]"

