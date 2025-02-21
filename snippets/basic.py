from pydantic_ai import Agent
<<<<<<< HEAD

agent = Agent(  
    'google-gla:gemini-1.5-flash',
=======
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
>>>>>>> 51fa1648620b22abc7c2819e43ec40e378e7b1db
    system_prompt='Be concise, reply with one sentence.',  
)

result = agent.run_sync('Where does "hello world" come from?')  
<<<<<<< HEAD
print(result.data)
=======
print(result.data)


>>>>>>> 51fa1648620b22abc7c2819e43ec40e378e7b1db
