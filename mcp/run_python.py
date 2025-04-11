from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.providers.openai import OpenAIProvider
from dotenv import load_dotenv
import asyncio
import os


load_dotenv(override=True)

servers = [
    MCPServerStdio('npx', ['-y', '@pydantic/mcp-run-python', 'stdio']),
]

model = OpenAIModel('gpt-4o', provider=OpenAIProvider(api_key=os.getenv('OPENAI_API_KEY')))

agent = Agent(
    model=model,
    system_prompt="You are an assistant. You can use a tool to run python.",
    mcp_servers=servers
)

async def main():
    print("=== Python Assistant Chat ===")
    print("The assistant can write and run python code")
    print("Type 'exit', 'quit', or 'bye' to end the conversation")
    print("===============================")

    # List to store conversation history
    conversation_history = []

    async with agent.run_mcp_servers():
        while True:
            user_input = input("\n[You] ")
            
            # Check if user wants to exit
            if user_input.lower() in ['exit', 'quit', 'bye', 'goodbye']:
                print("Goodbye!")
                break

            try:
                result = await agent.run(user_input, message_history=conversation_history)
                print('[Assistant] ', result.data)
                
                # Store the messages from this interaction in the conversation history
                conversation_history = result.all_messages()
            except Exception as e:
                print(f"\nError: {e}")

if __name__ == '__main__':
    asyncio.run(main())    
    