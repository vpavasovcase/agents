
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.providers.openai import OpenAIProvider
from dotenv import load_dotenv
import asyncio
import os


load_dotenv(override=True)

server = [
    MCPServerStdio('npx', ['-y', '@pydantic/mcp-run-python', 'stdio'])
]

model = OpenAIModel('gpt-4o', provider=OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')))

agent = Agent(
    model=model,
    system_prompt="You are a local filesystem assistant.",
    mcp_servers=[server]
)

async def main():
    async with agent.run_mcp_servers():
        result = await agent.run('How many days between 2000-01-01 and 2025-03-18?')
    print(result.data)

if __name__ == '__main__':
    asyncio.run(main())    