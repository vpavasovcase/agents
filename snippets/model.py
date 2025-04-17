from pydantic_ai.models.gemini import GeminiModel
from dotenv import load_dotenv
import os

load_dotenv()

model = GeminiModel(
    model_name=os.getenv('PYDANTIC_AI_MODEL'),
    api_key=os.getenv('GEMINI_API_KEY'),
) 