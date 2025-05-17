#!/usr/bin/env python3
"""loan_cli.py — Pydantic‑AI style with OCR, caching, num2words and smarter token handling

Refactor highlights (May 2025)
─────────────────────────────
* **TOKEN_RE** now matches square‑bracket placeholders **and** “=ALL_CAPS” tokens.
* OCR: 300 DPI grayscale images, lang="hrv+eng"; parallelised & cached under `.cache/`.
* **Regex fast‑path** harvests obvious values before LLM search.
* **num2words** auto‑spells amounts whenever template token contains “slovima”.
* Conditional paragraph cleanup: any leftover token triggers deletion.
* Single‑file, fully typed, Pydantic‑AI idiomatic.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import io
import os
import re
from dataclasses import dataclass, field

from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Pattern

from dotenv import load_dotenv
import logfire
from num2words import num2words
from PIL import Image as PIL_Image
import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import Usage, UsageLimits

# ── init env & logging ────────────────────────────────────────────────────
load_dotenv()
logfire.configure()
logfire.instrument_pydantic()
Agent.instrument_all()

# ── paths ─────────────────────────────────────────────────────────────────
ROOT_DIR = Path("emanuel/docs").resolve()
TEMPLATE_DOCX = ROOT_DIR / "template.docx"
TEMPLATE_PDF = ROOT_DIR / "template.pdf"
CACHE_DIR = ROOT_DIR.parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

# ── placeholder regex ─────────────────────────────────────────────────────
TOKEN_RE: Pattern[str] = re.compile(r"\[[^\]]+?\]|=[A-Z_]+")

# ── OCR helpers ───────────────────────────────────────────────────────────

def ocr_pdf(path: Path) -> str:
    """Return text from any PDF (scanned or searchable)."""
    parts: List[str] = []
    try:
        for img in convert_from_path(path, dpi=300, grayscale=True):
            parts.append(pytesseract.image_to_string(img, lang="hrv+eng"))
        return "\n".join(parts)
    except Exception as exc:
        print(f"[warn] pdf2image failed for {path.name}: {exc}")
    pdf = fitz.open(path.as_posix())
    for page in pdf:
        img_bytes = page.get_pixmap().tobytes()
        img = PIL_Image.open(io.BytesIO(img_bytes))
        parts.append(pytesseract.image_to_string(img, lang="hrv+eng"))
    pdf.close()
    return "\n".join(parts)


def cached_ocr(path: Path) -> str:
    """Cache OCR output by SHA‑256 of the file bytes."""
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    cache_file = CACHE_DIR / f"{h}.txt"
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    txt = ocr_pdf(path)
    cache_file.write_text(txt, encoding="utf-8")
    return txt

# ── pydantic schemas ──────────────────────────────────────────────────────

class RequiredFields(BaseModel):
    required_fields: List[str] = Field(..., description="Template placeholders to fill")


class SearchOutput(BaseModel):
    found_data: Dict[str, str]
    missing_data: List[str]

# ── LLM models ────────────────────────────────────────────────────────────

groq_model = GroqModel(
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    provider=GroqProvider(api_key=os.getenv("GROQ_API_KEY", "")),
)
vision_model = OpenAIModel(
    "gpt-4o-mini",
    provider=OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY", ""))
)

# ── MCP servers ───────────────────────────────────────────────────────────
FILESYSTEM_SERVER = MCPServerStdio(
    "npx", ["-y", "@modelcontextprotocol/server-filesystem", ROOT_DIR.as_posix()]
)
WORD_SERVER = MCPServerStdio(
    "uvx", ["--from", "office-word-mcp-server", "word_mcp_server"]
)
MCP_SERVERS = [FILESYSTEM_SERVER, WORD_SERVER]

# ── agents ────────────────────────────────────────────────────────────────
analysis_agent = Agent[None, RequiredFields](
    model=vision_model,
    output_type=RequiredFields,
    system_prompt=(
        "You are the Analysis Agent. Examine the Word template and the annotated PDF; "
        "return JSON {\"required_fields\": [...]} listing each placeholder token to fill."
    ),
)

search_agent = Agent[None, SearchOutput](
    model=groq_model,
    output_type=SearchOutput,
    system_prompt=(
        "You are the Search Agent. Provided REQUIRED and TEXT, return {found_data, missing_data}."
    ),
)

# ── orchestration ─────────────────────────────────────────────────────────
@dataclass
class LoanAutomation:
    usage: Usage = field(default_factory=Usage)
    limits: UsageLimits = field(default_factory=lambda: UsageLimits(request_limit=25))

    async def read_sources(self, credit: str) -> str:
        src_dir = ROOT_DIR / "sources" / credit
        if not src_dir.exists():
            print(f"[error] No source directory {src_dir}")
            return ""
        pdfs = [fp for fp in src_dir.iterdir() if fp.suffix.lower() == ".pdf"]
        txts = [fp for fp in src_dir.iterdir() if fp.suffix.lower() == ".txt"]
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pdf_texts = await asyncio.gather(*(loop.run_in_executor(pool, cached_ocr, fp) for fp in pdfs))
        txt_parts = [fp.read_text(encoding="utf-8") for fp in txts]
        combined = "\n".join(pdf_texts + txt_parts)
        logfire.info("read_sources", chars=len(combined))
        return combined

    async def analyse_template(self) -> List[str]:
        messages = [
            "Identify placeholders needing data:",
            BinaryContent(TEMPLATE_DOCX.read_bytes(),
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            BinaryContent(TEMPLATE_PDF.read_bytes(), "application/pdf"),
        ]
        result = await analysis_agent.run(messages, usage=self.usage, usage_limits=self.limits)
        return result.output.required_fields

    # quick deterministic regex pass
    PATTERNS = {
        "BROJ_KREDITA": re.compile(r"Broj kredita:\s*(\d+)", re.I),
        "IZNOS_KREDITA": re.compile(r"Iznos kredita[^:\n]*?:\s*([0-9.,]+)", re.I),
        "VALUTA": re.compile(r"Valuta kredita:?\s*([A-Z]{3})", re.I),
        "EKS": re.compile(r"Efektivna\\s+kamatna\\s+stopa:?\\s*([0-9.,]+)\\s*%", re.I),
    }

    def regex_extract(self, text: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for key, pattern in self.PATTERNS.items():
            if m := pattern.search(text):
                out[key] = m.group(1).strip()
        return out

    async def search_fields(self, required: List[str], text: str) -> SearchOutput:
        prelim = self.regex_extract(text)
        missing_req = [r for r in required if r not in prelim]
        prompt = f"KNOWN: {prelim}\nREQUIRED: {missing_req}\nTEXT:\n{text}"
        result = await search_agent.run(prompt, usage=self.usage, usage_limits=self.limits)
        # merge deterministic & LLM finds
        found = {**prelim, **result.output.found_data}
        missing = [k for k in required if k not in found]
        return SearchOutput(found_data=found, missing_data=missing)

    # spelling helper
    def maybe_spell(self, token: str, value: str) -> str:
        if "slovima" in token.lower():
            # normalise separators for Decimal
            num_str = value.replace(".", "").replace(",", ".")
            try:
                return num2words(Decimal(num_str), lang="hr")
            except Exception:
                pass
        return value

    async def fill_template(self, dest: Path, data: Dict[str, str]) -> None:
        word = WORD_SERVER
        await word.call_tool("copy_document", {
            "source_filename": TEMPLATE_DOCX.as_posix(),
            "destination_filename": dest.as_posix(),
        })
        content = await word.call_tool("get_document_text", {"filename": dest.as_posix()})
        for token in TOKEN_RE.findall(content):
            key = token.lstrip("=[").rstrip("]")
            if key in data:
                repl = self.maybe_spell(token, data[key])
                await word.call_tool("search_and_replace", {
                    "filename": dest.as_posix(),
                    "find_text": token,
                    "replace_text": str(repl),
                })
        # remove any paragraph still containing tokens
        content_after = await word.call_tool("get_document_text", {"filename": dest.as_posix()})
        for leftover in TOKEN_RE.findall(content_after):
            await word.call_tool("delete_paragraph_containing", {
                "filename": dest.as_posix(),
                "text": leftover,
            })
        logfire.info("fill_template", dest=dest.as_posix())

    async def validate(self, path: Path) -> List[str]:
        word = WORD_SERVER
        content = await word.call_tool("get_document_text", {"filename": path.as_posix()})
        return TOKEN_RE.findall(content)

    async def run_credit(self, credit: str) -> None:
        text = await self.read_sources(credit)
        if not text:
            return
        required = await self.analyse_template()
        search_res = await self.search_fields(required, text)
        found, missing = search_res.found_data, search_res.missing_data
        for field in missing:
            ans = input(f"Enter value for '{field}': ").strip()
            if ans:
                found[field] = ans
        still_missing = [k for k in required if k not in found]
        if still_missing:
            print("[error] Still missing:", still_missing)
            return
        dest = ROOT_DIR / "completed" / f"{credit}.docx"
        await self.fill_template(dest, found)
        leftovers = await self.validate(dest)
        if leftovers:
            print("❌  Unresolved placeholders after cleanup:", leftovers)
        else:
            print("✅  Completed:", dest.as_posix())

    # CLI loop
    async def cli(self) -> None:
        async with Agent(model=groq_model, mcp_servers=MCP_SERVERS).run_mcp_servers():
            while True:
                credit = input("Credit number (or 'exit'): ").strip()
                if credit.lower() in {"exit", "quit", ""}:
                    break
                await self.run_credit(credit)

# ── entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(LoanAutomation().cli())
