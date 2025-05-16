#!/usr/bin/env python3
"""loan_cli.py — Pydantic‑AI‑style refactor

Single‑file CLI that automates filling a loan‑agreement template from
source documents (PDF/TXT).  Highlights of the refactor:

* Agents & schemas live at top‑level; each exchange is fully typed.
* Template analysis uses BinaryContent (DOCX + PDF) so no Word‑MCP roundtrip.
* `LoanAutomation` orchestrates the workflow; the CLI loop is a thin wrapper.
* Logfire + Agent.instrument_all() give distributed tracing out of the box.
"""

from __future__ import annotations

import asyncio
import io
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
import logfire
from PIL import Image as PIL_Image  # pillow
import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.usage import Usage, UsageLimits

# ── initialise logging & env ───────────────────────────────────────────────
load_dotenv()
logfire.configure()
logfire.instrument_pydantic()
Agent.instrument_all()

# ── paths & constants ──────────────────────────────────────────────────────
ROOT_DIR = Path("emanuel/docs").resolve()
TEMPLATE_DOCX = ROOT_DIR / "template.docx"
TEMPLATE_PDF = ROOT_DIR / "template.pdf"

# ── low‑level helper functions ─────────────────────────────────────────────

def ocr_pdf(path: Path) -> str:
    """Return text from any PDF (handles scanned docs via pdf2image + Tesseract)."""
    parts: List[str] = []
    try:
        # fast path: pdf2image/Poppler
        for img in convert_from_path(path):
            parts.append(pytesseract.image_to_string(img, lang="hrv"))
        return "\n".join(parts)
    except Exception as exc:
        print(f"[warn] pdf2image failed for {path.name}: {exc}")
    # fallback: PyMuPDF rasterisation
    pdf = fitz.open(path.as_posix())
    for page in pdf:
        img = PIL_Image.open(io.BytesIO(page.get_pixmap().tobytes()))
        parts.append(pytesseract.image_to_string(img, lang="hrv"))
    pdf.close()
    return "\n".join(parts)


def comments_from_pdf(path: Path) -> List[str]:
    out: List[str] = []
    pdf = fitz.open(path.as_posix())
    for pg in pdf:
        ann = pg.first_annot
        while ann:
            if txt := ann.get_text():
                out.append(txt.strip())
            ann = ann.next
    pdf.close()
    return out

# ── pydantic schemas ───────────────────────────────────────────────────────

class RequiredFields(BaseModel):
    required_fields: List[str] = Field(..., description="Tokens inside {{...}} or [...] to fill")


class SearchOutput(BaseModel):
    found_data: Dict[str, str]
    missing_data: List[str]


# ── LLM models ─────────────────────────────────────────────────────────────

llm_model = GroqModel(
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    provider=GroqProvider(api_key=os.getenv("GROQ_API_KEY", "")),
)
vision_model = OpenAIModel(
    "gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY", ""),
)

# ── MCP servers (filesystem + Word) ────────────────────────────────────────
FILESYSTEM_SERVER = MCPServerStdio(
    "npx", ["-y", "@modelcontextprotocol/server-filesystem", ROOT_DIR.as_posix()]
)
WORD_SERVER = MCPServerStdio(
    "uvx", ["--from", "office-word-mcp-server", "word_mcp_server"]
)
MCP_SERVERS = [FILESYSTEM_SERVER, WORD_SERVER]

# ── agents ─────────────────────────────────────────────────────────────────
analysis_agent = Agent[None, RequiredFields](
    model=vision_model,
    output_type=RequiredFields,
    system_prompt=(
        "You are the Analysis Agent. Examine the Word template and the annotated PDF; "
        "return JSON {\"required_fields\": [...]} listing every placeholder token "
        "that must be filled before the agreement is signed."
    ),
)

search_agent = Agent[None, SearchOutput](
    model=llm_model,
    output_type=SearchOutput,
    system_prompt=(
        "You are the Search Agent. Given REQUIRED and TEXT, extract values for each "
        "field; return {found_data, missing_data}."
    ),
)


# ── orchestration class ────────────────────────────────────────────────────
@dataclass
class LoanAutomation:
    """High‑level coordinator for the multi‑agent workflow."""

    usage: Usage = Usage()
    limits: UsageLimits = UsageLimits(request_limit=25)

    async def read_sources(self, credit: str) -> str:
        """OCR every PDF + concatenate every TXT under sources/<credit>."""
        src_dir = ROOT_DIR / "sources" / credit
        if not src_dir.exists():
            print(f"[error] No source directory {src_dir}")
            return ""

        parts: List[str] = []
        for fp in src_dir.iterdir():
            if fp.suffix.lower() == ".pdf":
                parts.append(ocr_pdf(fp))
            elif fp.suffix.lower() == ".txt":
                parts.append(fp.read_text(encoding="utf-8"))
        combined = "\n".join(parts)
        logfire.info("read_sources", credit=credit, chars=len(combined))
        return combined

    async def analyse_template(self) -> List[str]:
        """Call analysis_agent using BinaryContent to pull placeholders."""
        messages = [
            "Identify placeholders needing data:",
            BinaryContent(TEMPLATE_DOCX.read_bytes(),
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            BinaryContent(TEMPLATE_PDF.read_bytes(), "application/pdf"),
        ]
        result = await analysis_agent.run(messages, usage=self.usage, usage_limits=self.limits)
        return result.output.required_fields

    async def search_fields(self, required: List[str], text: str) -> SearchOutput:
        prompt = f"REQUIRED: {required}\nTEXT: {text[:1600]}"
        result = await search_agent.run(prompt, usage=self.usage, usage_limits=self.limits)
        return result.output

    async def fill_template(self, dest: Path, data: Dict[str, str]) -> None:
        word = WORD_SERVER
        await word.call_tool("copy_document", {
            "source_filename": TEMPLATE_DOCX.as_posix(),
            "destination_filename": dest.as_posix(),
        })
        # replace tokens
        content = await word.call_tool("get_document_text", {"filename": dest.as_posix()})
        tokens = re.findall(r"\{\{[^{}]+?\}\}|\[[^\[\]]+?\]", content)
        for token in tokens:
            key = token.strip("{}[]")
            if key in data:
                await word.call_tool("search_and_replace", {
                    "filename": dest.as_posix(),
                    "find_text": token,
                    "replace_text": str(data[key]),
                })
        logfire.info("fill_template", dest=dest.as_posix())

    async def validate(self, path: Path) -> List[str]:
        word = WORD_SERVER
        content = await word.call_tool("get_document_text", {"filename": path.as_posix()})
        return re.findall(r"\{\{[^{}]+?\}\}|\[[^\[\]]+?\]", content)

    async def run_credit(self, credit: str) -> None:
        # 1) OCR in background
        text = await self.read_sources(credit)
        if not text:
            return

        # 2) analyse once (static)
        required = await self.analyse_template()

        # 3) search OCR text
        search_output = await self.search_fields(required, text)
        found, missing = search_output.found_data, search_output.missing_data

        # 4) ask user for anything missing
        for field in missing:
            value = input(f"Enter value for '{field}': ").strip()
            if value:
                found[field] = value

        still_missing = [k for k in required if not found.get(k)]
        if still_missing:
            print("[error] Still missing:", still_missing)
            return

        # 5) fill template
        dest = ROOT_DIR / "completed" / f"{credit}.docx"
        await self.fill_template(dest, found)

        # 6) validate
        leftovers = await self.validate(dest)
        if leftovers:
            print("❌  Unresolved placeholders:", leftovers)
        else:
            print("✅  Completed:", dest.as_posix())

    # CLI helpers -----------------------------------------------------------
    async def cli(self) -> None:
        async with Agent(model=llm_model, mcp_servers=MCP_SERVERS).run_mcp_servers():
            while True:
                credit = input("Credit number (or 'exit')
