from pydantic_ai import Agent
from dotenv import load_dotenv
from httpx import AsyncClient
import os
from pydantic_ai.models.gemini import GeminiModel


load_dotenv()


model = GeminiModel(
    model_name='gemini-1.5-flash',
    api_key=os.getenv('GEMINI_API_KEY'),
    http_client=AsyncClient(),
)

agent = Agent(  
    model,
    system_prompt='Be concise, reply with one sentence.',  
)

result = agent.run_sync('Where does "hello world" come from?')  
print(result.data)


