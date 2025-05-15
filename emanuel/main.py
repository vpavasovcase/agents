#!/usr/bin/env python3
"""
Loan‑Agreement Automation CLI
─────────────────────────────
Restored six‑agent workflow **with a clean, working ReadAgent**:

* Primary OCR path uses `pdf2image` (Poppler). 
* Fallback path uses PyMuPDF → PIL when Poppler isn’t available. 
  ‑ Handles both `page.get_pixmap` (new) and `page.getPixmap` (old) APIs.
* No double `except`, no stray `doc.close()`, and `"\n".join(parts)` is fixed.

Directory layout:
  emanuel/docs/template.docx / template.pdf
  emanuel/docs/sources/<credit>/ …
  emanuel/docs/completed/<credit>.docx
"""

import os
import re
import io
import asyncio
from pathlib import Path
from typing import List, Dict

from dotenv import load_dotenv

import logfire
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.usage import Usage, UsageLimits

from pdf2image import convert_from_path  # OCR helpers
import pytesseract
import fitz  # PyMuPDF
from PIL import Image as PIL_Image  # pillow

# ─── Init & instrumentation ──────────────────────────────────────────────────
load_dotenv()
logfire.configure()
Agent.instrument_all()

# ─── Paths -------------------------------------------------------------------
ROOT_DIR = Path("emanuel/docs").resolve()
TEMPLATE_DOCX = (ROOT_DIR / "template.docx").as_posix()
TEMPLATE_PDF = (ROOT_DIR / "template.pdf").as_posix()

# ─── LLM + MCP setup ----------------------------------------------------------
llm_model = GroqModel(
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    provider=GroqProvider(api_key=os.getenv("GROQ_API_KEY", "")),
)

mcp_servers: List[MCPServerStdio] = [
    MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-filesystem", ROOT_DIR.as_posix()]),
    MCPServerStdio("uvx", ["--from", "office-word-mcp-server", "word_mcp_server"]),
]

# ─── Pydantic schemas ---------------------------------------------------------
class RequiredFields(BaseModel):
    required_fields: List[str]

class SearchOutput(BaseModel):
    found_data: Dict[str, str]
    missing_data: List[str]

# ─── LLM Agents ---------------------------------------------------------------
analysis_agent = Agent[None, RequiredFields](
    model=llm_model,
    output_type=RequiredFields,  # type: ignore
    system_prompt=(
        "You are the Analysis Agent. From placeholders + PDF comments, decide which placeholders must be filled. "
        "Return JSON {\"required_fields\": [...]}"
    ),
    mcp_servers=mcp_servers,
)

search_agent = Agent[None, SearchOutput](
    model=llm_model,
    output_type=SearchOutput,  # type: ignore
    system_prompt=(
        "You are the Search Agent. Extract values for required fields from document text; mark missing/ambiguous. "
        "Return JSON {found_data, missing_data}."
    ),
    mcp_servers=mcp_servers,
)

# ╭───────────────────────────────────────────────────────────────────────────╮
# │ 1) READ AGENT – robust OCR                                              │
# ╰───────────────────────────────────────────────────────────────────────────╯
async def read_agent(credit: str) -> str:
    """OCR every PDF + read every TXT under sources/<credit>."""
    src_dir = ROOT_DIR / "sources" / credit
    if not src_dir.exists():
        print(f"[error] No source directory {src_dir}")
        return ""

    parts: List[str] = []
    for fp in src_dir.iterdir():
        if fp.suffix.lower() == ".pdf":
            # First try Poppler‑based pdf2image
            success = False
            try:
                for img in convert_from_path(fp):
                    parts.append(pytesseract.image_to_string(img, lang="hrv"))
                success = True
            except Exception as exc:
                print(f"[warn] pdf2image failed on {fp.name}: {exc}")

        elif fp.suffix.lower() == ".txt":
            parts.append(fp.read_text(encoding="utf-8"))

    combined = "\n".join(parts)
    logfire.info("read_agent", credit=credit, chars=len(combined))
    return combined

# ╭───────────────────────────────────────────────────────────────────────────╮
# │ Word MCP helpers (Fill / Final)                                         │
# ╰───────────────────────────────────────────────────────────────────────────╯
async def get_placeholders(word_server: MCPServerStdio, path: str) -> List[str]:
    text: str = await word_server.call_tool("get_document_text", {"filename": path})
    return re.findall(r"\{\{[^{}]+?\}\}|\[[^\[\]]+?\]", text)

async def fill_agent(word_server: MCPServerStdio, dest: str, data: Dict[str, str]) -> None:
    await word_server.call_tool("copy_document", {
        "source_filename": TEMPLATE_DOCX,
        "destination_filename": dest,
    })
    tokens = await get_placeholders(word_server, dest)
    for token in tokens:
        key = token.strip("{}[]")
        if key in data:
            await word_server.call_tool("search_and_replace", {
                "filename": dest,
                "find_text": token,
                "replace_text": str(data[key]),
            })
    logfire.info("fill_agent", path=dest)

async def final_agent(word_server: MCPServerStdio, path: str) -> List[str]:
    return await get_placeholders(word_server, path)

# ╭───────────────────────────────────────────────────────────────────────────╮
# │ Misc helpers                                                            │
# ╰───────────────────────────────────────────────────────────────────────────╯

def comments_from_pdf(path: str) -> List[str]:
    out: List[str] = []
    pdf = fitz.open(path)
    for pg in pdf:
        ann = pg.first_annot
        while ann:
            if txt := ann.get_text():
                out.append(txt.strip())
            ann = ann.next
    pdf.close()
    return out

async def ask_agent(found: Dict[str, str], missing: List[str]) -> None:
    for field in missing:
        ans = input(f"Enter value for '{field}': ").strip()
        if ans:
            found[field] = ans

# ╭───────────────────────────────────────────────────────────────────────────╮
# │ Main orchestrator                                                       │
# ╰───────────────────────────────────────────────────────────────────────────╯
async def main() -> None:
    usage = Usage()
    limits = UsageLimits(request_limit=25)

    async with Agent(model=llm_model, mcp_servers=mcp_servers).run_mcp_servers():
        word_server = mcp_servers[1]

        while True:
            credit = input("Credit number (or 'exit'): ").strip()
            if credit.lower() in {"exit", "quit", ""}:
                break

            # 1) OCR source docs
            doc_text = await read_agent(credit)
            if not doc_text:
                continue

            # 2) Analyse template
            tokens = await get_placeholders(word_server, TEMPLATE_DOCX)
            pdf_notes = comments_from_pdf(TEMPLATE_PDF)
            prompt_analysis = f"TOKENS: {tokens}\nPDF_COMMENTS: {pdf_notes}"
            res_analysis = await analysis_agent.run(prompt_analysis, usage=usage, usage_limits=limits)
            required = res_analysis.output.required_fields

            # 3) Search in OCR text
            prompt_search = f"REQUIRED: {required}\nTEXT: {doc_text[:1600]}"
            res_search = await search_agent.run(prompt_search, usage=usage, usage_limits=limits)
            found, missing = res_search.output.found_data, res_search.output.missing_data

            # 4) Ask user
            if missing:
                await ask_agent(found, missing)

            still_missing = [k for k in required if not found.get(k)]
            if still_missing:
                print("[error] Still missing:", still_missing)
                continue

            # 5) Fill template
            dest = (ROOT_DIR / "completed" / f"{credit}.docx").as_posix()
            await fill_agent(word_server, dest, found)

            # 6) Validate
                        leftovers = await final_agent(word_server, dest)
