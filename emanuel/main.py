#!/usr/bin/env python3
"""
Loan-Agreement Automation CLI – v0.6 (Document-Input edition)
"""

import os, re, io, asyncio
from pathlib import Path
from typing import List, Dict

from dotenv import load_dotenv
import logfire

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIModel                # NEW
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.usage import Usage, UsageLimits
from pydantic_ai.mcp import MCPServerStdio

from pdf2image import convert_from_path
import pytesseract, fitz
from PIL import Image as PIL_Image

# ─── setup ────────────────────────────────────────────────────────────────
load_dotenv()
logfire.configure()
logfire.instrument_pydantic()
Agent.instrument_all()

ROOT_DIR = Path("emanuel/docs").resolve()
TEMPLATE_DOCX = ROOT_DIR / "template.docx"
TEMPLATE_PDF  = ROOT_DIR / "template.pdf"

# ─── LLM models ───────────────────────────────────────────────────────────
llm_model = GroqModel(
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    provider=GroqProvider(api_key=os.getenv("GROQ_API_KEY", "")),
)

# ─── MCP servers (unchanged) ──────────────────────────────────────────────
mcp_servers = [
    MCPServerStdio("npx", ["-y", "@modelcontextprotocol/server-filesystem", ROOT_DIR.as_posix()]),
    MCPServerStdio("uvx", ["--from", "office-word-mcp-server", "word_mcp_server"]),
]

# ─── Pydantic schemas ────────────────────────────────────────────────────
class RequiredFields(BaseModel):
    required_fields: List[str]

class SearchOutput(BaseModel):
    found_data: Dict[str, str]
    missing_data: List[str]

# ─── Agents ───────────────────────────────────────────────────────────────
analysis_agent = Agent[None, RequiredFields](
    model=llm_model,                                             # NEW
    output_type=RequiredFields,
    system_prompt=(
        "You are the Analysis Agent. Examine the Word template and the "
        "annotated PDF; return JSON {\"required_fields\": [...]} listing the "
        "placeholders that must be filled before the agreement is signed."
    ),
)

search_agent = Agent[None, SearchOutput](
    model=llm_model,
    output_type=SearchOutput,
    system_prompt=(
        "You are the Search Agent. Extract values for required fields from "
        "document OCR text; mark missing or ambiguous ones."
    ),
    mcp_servers=mcp_servers,
)

# ... (ReadAgent, FillAgent, FinalAgent code remains IDENTICAL) ...
# Only the call inside `main()` changes:

async def main() -> None:
    usage = Usage()
    limits = UsageLimits(request_limit=25)

    async with Agent(model=llm_model, mcp_servers=mcp_servers).run_mcp_servers():
        word_server = mcp_servers[1]

        while True:
            credit = input("Credit number (or 'exit'): ").strip()
            if credit.lower() in {"exit", "quit", ""}:
                break

            # 1) OCR source docs (unchanged) --------------------------------
            doc_text = await read_agent(credit)
            if not doc_text:
                continue

            # 2) Analyse template with document input -----------------------
            analysis_messages = [
                "Identify placeholders needing data:",
                BinaryContent(TEMPLATE_DOCX.read_bytes(),
                               "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                BinaryContent(TEMPLATE_PDF.read_bytes(), "application/pdf"),
            ]
            res_analysis = await analysis_agent.run(
                analysis_messages, usage=usage, usage_limits=limits
            )
            required = res_analysis.output.required_fields

            # ... 3)-6) Search, Ask, Fill, Validate are unchanged ...
