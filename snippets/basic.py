from pydantic_ai import Agent
from snippets.model import model

agent = Agent(  
    model=model,
    system_prompt='Be concise, reply with one sentence.',  
)

result = agent.run_sync('Where does "hello world" come from?')  
print(result.data)