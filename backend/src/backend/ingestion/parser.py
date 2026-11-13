# ==============================================================================
# Step 6: The Structure-Aware Parser (The Smart Scissors)
# File: backend/src/backend/ingestion/parser.py
#
# FOR BEGINNERS:
# - 'pathlib.Path': Python's built-in tool for finding and opening files cleanly.
# - 're': Python's 'Regular Expressions' tool, used to search for text patterns
#   like Markdown headers (e.g., lines starting with '#' or '##').
# ==============================================================================

import re
from pathlib import Path
from typing import List, Optional

# Import our 'Index Card' blueprint and our Token Counter
from backend.ingestion.models import DocumentChunk
from backend.ingestion.tokenizer import count_tokens


class StructureAwareParser:
    """
    The Smart Scissors:
    Reads messy engineering runbooks and PDFs, slicing them along natural
    boundaries (headings, tables, and paragraphs) so instructions never get
    cut in half.
    """

    def __init__(self, target_chunk_tokens: int = 400, max_chunk_tokens: int = 800):
        # We aim for roughly 400 tokens per chunk.
        # If a single section is larger than 800 tokens, we break it into paragraphs.
        self.target_chunk_tokens = target_chunk_tokens
        self.max_chunk_tokens = max_chunk_tokens

    def parse_file(self, file_path: str) -> List[DocumentChunk]:
        """
        Main entry point: Checks file extension (.md, .log, .pdf)
        and calls the appropriate smart slicer.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check the file extension (e.g. '.md')
        file_extension = path.suffix.lower()

        if file_extension in [".md", ".markdown"]:
            return self.parse_markdown(path)
        elif file_extension == ".pdf":
            return self.parse_pdf(path)
        else:
            # Fallback for plain text or log files (.log, .txt)
            return self.parse_text_log(path)

    def parse_markdown(self, path: Path) -> List[DocumentChunk]:
        """
        Slices Markdown documents along their headers (#, ##, ###).
        Keeps troubleshooting tables and commands intact within each section.
        """
        text = path.read_text(encoding="utf-8")
        filename = path.name

        # This regex pattern finds lines starting with 1 to 4 '#' characters
        # e.g.: '# Runbook' or '## 2. Diagnostics Commands'
        header_pattern = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
        matches = list(header_pattern.finditer(text))

        # If there are no headers in the file, split by double newlines (paragraphs)
        if not matches:
            return self._split_paragraphs(text, source=filename, doc_type="markdown")

        chunks: List[DocumentChunk] = []

        # Loop through each section between headers
        for i, match in enumerate(matches):
            header_title = match.group(2).strip()

            # Find where this section starts and ends
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section_content = text[start_pos:end_pos].strip()

            tokens = count_tokens(section_content)

            # If the section fits comfortably on one card, keep it whole!
            if tokens <= self.max_chunk_tokens:
                # Clean up title for the unique card barcode ID
                clean_title = re.sub(r"[^a-zA-Z0-9_]", "_", header_title)[:25]
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{filename}#s{i}_{clean_title}",
                        content=section_content,
                        source=filename,
                        doc_type="markdown",
                        section_title=header_title,
                        token_count=tokens
                    )
                )
            else:
                # If a section is huge, split it by paragraphs while keeping the header label
                sub_chunks = self._split_paragraphs(
                    section_content,
                    source=filename,
                    doc_type="markdown",
                    section_title=header_title,
                    prefix_id=f"{filename}#s{i}"
                )
                chunks.extend(sub_chunks)

        return chunks

    def parse_text_log(self, path: Path) -> List[DocumentChunk]:
        """
        Slices incident logs into manageable paragraph blocks.
        """
        text = path.read_text(encoding="utf-8")
        filename = path.name
        return self._split_paragraphs(text, source=filename, doc_type="log")

    def parse_pdf(self, path: Path) -> List[DocumentChunk]:
        """
        Extracts pages from a PDF, preserving the exact page number for citations.
        """
        import pypdf
        reader = pypdf.PdfReader(str(path))
        filename = path.name
        chunks: List[DocumentChunk] = []

        for page_idx, page in enumerate(reader.pages):
            page_text = (page.extract_text() or "").strip()
            if not page_text:
                continue

            page_number = page_idx + 1
            tokens = count_tokens(page_text)

            chunks.append(
                DocumentChunk(
                    chunk_id=f"{filename}_page_{page_number}",
                    content=page_text,
                    source=filename,
                    doc_type="pdf",
                    page_number=page_number,
                    token_count=tokens
                )
            )

        return chunks

    def _split_paragraphs(
        self,
        text: str,
        source: str,
        doc_type: str,
        section_title: Optional[str] = None,
        page_number: Optional[int] = None,
        prefix_id: Optional[str] = None
    ) -> List[DocumentChunk]:
        """
        Helper function: Splits long text blocks by double newlines (\n\n).
        """
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: List[DocumentChunk] = []
        base_id = prefix_id or source

        for idx, p in enumerate(paragraphs, 1):
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{base_id}_p{idx}",
                    content=p,
                    source=source,
                    doc_type=doc_type,
                    section_title=section_title,
                    page_number=page_number,
                    token_count=count_tokens(p)
                )
            )

        return chunks

