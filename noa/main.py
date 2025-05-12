#!/usr/bin/env python3
import os
import asyncio
from dataclasses import dataclass
from datetime import date
from typing import List, Dict
from pathlib import Path

import logfire
import asyncpg
from pydantic import BaseModel, Field

from pydantic_ai import Agent, RunContext, MCPServerStdio

# --- Database schema ---
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
    id SERIAL PRIMARY KEY,
    image_path TEXT,
    vendor TEXT,
    date DATE,
    total NUMERIC,
    items JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

RECEIPTS_FOLDER = Path(os.environ.get("RECEIPTS_FOLDER", "./receipts"))

# --- Database connection class ---
class DatabaseConn:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._conn = None

    async def connect(self):
        self._conn = await asyncpg.connect(self._dsn)
        await self._conn.execute(DB_SCHEMA)

    async def close(self):
        await self._conn.close()

    async def insert_record(self, image_path: str, vendor: str, date_: date, total: float, items: List[Dict]):
        await self._conn.execute(
            "INSERT INTO receipts (image_path, vendor, date, total, items) VALUES ($1, $2, $3, $4, $5)",
            image_path, vendor, date_, total, items
        )

# --- Agent dependencies ---
@dataclass
class Deps:
    db: DatabaseConn

# --- Pydantic schema for a single receipt ---
class RecordInput(BaseModel):
    image_path: str = Field(description="Local path to the receipt image")
    vendor: str = Field(description="Vendor or store name")
    date: date = Field(description="Date of the receipt (YYYY-MM-DD)")
    total: float = Field(description="Total amount on the receipt")
    items: List[Dict] = Field(description="Line items as list of {name, price}")

async def chat_loop(agent: Agent, deps: Deps):
    """
    Runs a REPL loop allowing the user to chat with the agent.
    Type 'exit' or 'quit' to end the session.
    """
    print("Chat initialized. Type 'exit' or 'quit' to quit.")
    history: List[Dict[str, str]] = []
    while True:
        try:
            user_input = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting chat.")
            break
        if user_input.strip().lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        history.append({"role": "user", "content": user_input})

        # Build prompt with conversation history
        convo = []
        for msg in history:
            role = msg["role"].capitalize()
            convo.append(f"{role}: {msg['content']}")
        convo.append("Assistant:")
        prompt_text = "\n".join(convo)

        # Run agent
        result = await agent.run(prompt_text, deps=deps)
        reply = result.output.strip()

        print(reply)
        history.append({"role": "assistant", "content": reply})

async def main():
    # 1. Configure Logfire for monitoring
    logfire.configure()
    logfire.instrument_asyncpg()

    # 2. Connect to Postgres and ensure table exists
    db = DatabaseConn(os.environ["DATABASE_URL"])
    await db.connect()

    # 3. Set up MCP servers over stdio
    ocr_server = MCPServerStdio(
        command="python", args=["-m", "mcp_ocr"]
    )
    filesystem_server = MCPServerStdio(
        command="python", args=["-m", "mcp_filesystem"]
    )
    python_server = MCPServerStdio(
        command="python", args=["-m", "mcp_run_python"]
    )

    # 4. Create the PydanticAI agent
    agent = Agent(
        model=os.environ.get("AGENT_MODEL", "openai:gpt-4o"),
        deps_type=Deps,
        system_prompt="""
You are an assistant that:  
1. Lists image files in './receipts' using 'list_files' from filesystem server.  
2. Loads each image via 'read_file' or 'read_binary' to get bytes.  
3. Performs OCR with 'perform_ocr' to extract raw text.  
4. Parses receipts into Pydantic records (image_path, vendor, date, total, items).  
5. Calls 'save_record' to persist.  
6. For analysis queries, use 'run_python' to analyze spending (import pandas, query DB, compute).  
If missing info, ask the user.
""",
        mcp_servers=[ocr_server, filesystem_server, python_server],
        instrument=True,
    )

    # 5. Register the save_record tool
    @agent.tool
    async def save_record(ctx: RunContext[Deps], record: RecordInput) -> bool:
        """Save a parsed receipt record into the database."""
        await ctx.deps.db.insert_record(
            image_path=record.image_path,
            vendor=record.vendor,
            date_=record.date,
            total=record.total,
            items=record.items,
        )
        return True

    # 6. Start MCP servers and launch chat loop
    async with agent.run_mcp_servers():
        await chat_loop(agent, Deps(db=db))

    # 7. Clean up DB connection
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
