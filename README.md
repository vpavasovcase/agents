
## Welcome to PydanticAI

- **What is PydanticAI?**
  - A tool that helps manage AI agents with Python.
  - Makes building smart applications easier.

---

## Setting Up Your Project

- **Step 1: Clone a Git Repository**
  - What is Git? A tool to manage code versions.
  - Command: `git clone <repository-url>`
  - `git clone https://github.com/example/repo.git`
  - Make your folder
  - VSC extension GitGraph

---

## Generate a Personal Access Token (PAT) for GitHub
1. Go to **GitHub → Settings → Developer Settings → Personal Access Tokens**.
2. Click **Generate new token (classic)**.
3. Select scopes:
   - Check **repo** (for full repo access).
   - Optionally check **workflow** if working with GitHub Actions.
4. Click **Generate token** and **copy it** (you won’t see it again).

## Use the Token Instead of a Password
When pushing/pulling:

```sh
git push origin main
```
Git will ask for a username and password:

    Username: Your GitHub username.

    Password: Paste the Personal Access Token.
    
To avoid entering the token every time, you can cache credentials.

```sh
git config --global credential.helper store
```

---

## Virtual Environments (venv)

- **Why use a virtual environment?**

  - Keeps your project dependencies separate.

- **Creating a venv:**

  - Windows: `python -m venv venv`
  - macOS/Linux: `python3 -m venv venv`

- **Activating venv:**

  - Windows: `venv\Scripts\activate`
  - macOS/Linux: `source venv/bin/activate`

---

## Installing Dependencies

- **What is `requirements.txt`?**

  - A file listing all the libraries your project needs.

- **Installing with pip:**

  - `pip install -r requirements.txt`

- **What is pip?**

  - A tool to install Python packages.

---

## Configuring Your Project with `.env`

- **What is a `.env` file?**

  - A `.env` file stores environment variables, such as API keys and configuration settings, that your project needs to run securely.

- **Example:**

  ```env
  API_KEY=your_api_key_here
  DEBUG=True
  ```

- **Important:**

  - The `.env` file should be **ignored by Git** to keep sensitive information private. Add `.env` to your `.gitignore` file.

- **Loading `.env` Variables:**

  - Use the `python-dotenv` library to load environment variables automatically.
  - Example usage in Python:
    ```python
    from dotenv import load_dotenv
    import os

    load_dotenv()
    api_key = os.getenv("API_KEY")
    print(api_key)
    ```

---

## Gemini API Key

- https://ai.google.dev/gemini-api/docs/api-key#windows

---

## Recap & Q&A

- **Key Takeaways:**

  - Set up projects with Git and virtual environments.
  - Manage dependencies with `pip` and `requirements.txt`.
  - Configure settings with `.env` files.
  - Use PydanticAI to handle data easily.

- **Questions?**

---

**Introduction to PydanticAI**

- **What is PydanticAI?**
  - A Python agent framework designed for building production-grade applications with Generative AI.
  - Created to simplify and enhance AI app development.
- **Inspired by FastAPI**
  - FastAPI transformed web development with its ergonomic design and Pydantic foundation.
  - PydanticAI aims to bring that same ease-of-use to AI development.

---

**Why Use PydanticAI?**

- **Built by the Pydantic Team**
  - The same team behind the validation layer of OpenAI SDK, Anthropic SDK, LangChain, and more.

* **Logfire Integration**

  - Provides real-time debugging, performance monitoring, and behavior tracking.

* **Type-Safe and Python-Centric**

  - Strong type-checking for structured responses.
  - Uses Python's familiar control flow for seamless AI project development.

* **Structured Responses**

  - Ensures consistency using Pydantic’s validation capabilities.

---

## Getting Started with PydanticAI

- **Installing PydanticAI:**

  - `pip install pydanticai`

- **Basic Example:**

  ```python
  from pydantic_ai import Agent

  agent = Agent(  
      'google-gla:gemini-1.5-flash',
      system_prompt='Be concise, reply with one sentence.',  
  )

  result = agent.run_sync('Where does "hello world" come from?')  
  print(result.data)
  ```

---

# Introduction to Tools & Dependency Injection

- **What is Dependency Injection?**

  - A design pattern that provides an object with its dependencies from the outside.
  - Improves modularity, testing, and flexibility.

- **Why Use Tools in PydanticAI?**

  - Tools extend the functionality of AI agents.
  - Allow agents to interact with external systems and data sources.

---

## Example: Building a Bank Support Agent

- **Scenario:** A support agent helps customers with banking queries.
- **Key Components:**
  - Dependencies: Customer ID, Database Connection.
  - Tools: Functions to fetch customer data.

---

## Defining Dependencies

```python
from dataclasses import dataclass
from bank_database import DatabaseConn

@dataclass
class SupportDependencies:  
    customer_id: int
    db: DatabaseConn
```

- **Explanation:**
  - `SupportDependencies` defines the external resources needed, like customer information and database access.

---

## Setting Up the Result Model

```python
from pydantic import BaseModel, Field

class SupportResult(BaseModel):  
    support_advice: str = Field(description='Advice returned to the customer')
    block_card: bool = Field(description="Whether to block the customer's card")
    risk: int = Field(description='Risk level of query', ge=0, le=10)
```

- **Purpose:** Defines the structure of the support agent's response.

---

## Creating the Support Agent

```python
from pydantic_ai import Agent

support_agent = Agent(  
    'openai:gpt-4o',  
    deps_type=SupportDependencies,
    result_type=SupportResult,  
    system_prompt=(
        'You are a support agent in our bank, give the '
        'customer support and judge the risk level of their query.'
    ),
)
```

- **Agent Configuration:**
  - Defines the model, dependencies, and expected results.
  - Includes a system prompt to guide the agent's behavior.

---

## Adding Dynamic Data with System Prompts

```python
from pydantic_ai import RunContext

@support_agent.system_prompt  
async def add_customer_name(ctx: RunContext[SupportDependencies]) -> str:
    customer_name = await ctx.deps.db.customer_name(id=ctx.deps.customer_id)
    return f"The customer's name is {customer_name!r}"
```

- **What It Does:**
  - Fetches the customer's name dynamically from the database.
  - Personalizes the agent's responses.

---

## Creating Tools for the Agent

```python
@support_agent.tool  
async def customer_balance(
    ctx: RunContext[SupportDependencies], include_pending: bool
) -> float:
    """Returns the customer's current account balance."""  
    return await ctx.deps.db.customer_balance(
        id=ctx.deps.customer_id,
        include_pending=include_pending,
    )
```

- **Tool Function:**
  - Retrieves the customer's account balance.
  - Can include or exclude pending transactions.

---

## Running the Agent

```python
async def main():
    deps = SupportDependencies(customer_id=123, db=DatabaseConn())
    result = await support_agent.run('What is my balance?', deps=deps)  
    print(result.data)

    result = await support_agent.run('I just lost my card!', deps=deps)
    print(result.data)
```

- **Sample Outputs:**

  ```
  support_advice='Hello John, your current account balance, including pending transactions, is $123.45.' block_card=False risk=1

  support_advice="I'm sorry to hear that, John. We are temporarily blocking your card to prevent unauthorized transactions." block_card=True risk=8
  ```

- **Highlights:**

  - Dynamic data integration.
  - Automated risk assessment.
  - Responsive support actions.

---

## Key Takeaways

- Dependency Injection helps manage external resources effectively.

- Tools in PydanticAI enhance agent capabilities.

- Combining both allows for powerful, dynamic AI applications.

- **Questions?**
---

**Agent objects**

- Agent interfaces in PydanticAI interact with AI models.
- A single agent can control an app, or multiple agents can work together for complex tasks.

---

**Agent Components**

- **System prompt:** Instructions guiding the AI’s behavior.
- **Function tools:** Extra functions the AI can call.
- **Structured result:** Ensures the AI’s output follows a set format.
- **Dependencies:** Inputs needed by tools or prompts.
- **LLM model:** The default AI model (optional).
- **Model settings:** Adjusts AI responses.

---

**Typing in Agents**

- Agents use type hints to ensure correct data.
- Example: `Agent[InputType, OutputType]` helps prevent errors.

---

**Example: Roulette Agent**

```python
from pydantic_ai import Agent, RunContext

roulette_agent = Agent(
    'openai:gpt-4o',
    deps_type=int,
    result_type=bool,
    system_prompt='Check if the number wins.'
)

@roulette_agent.tool
def roulette_wheel(ctx: RunContext[int], square: int) -> str:
    return 'winner' if square == ctx.deps else 'loser'
```

---

**Running Agents**

- `agent.run()`: Runs asynchronously.
- `agent.run_sync()`: Runs normally (synchronous function).
- `agent.run_stream()`: Streams results in real-time.

---

**Example: Running an Agent**

```python
from pydantic_ai import Agent

agent = Agent('google-gla:gemini-1.5-flash')
result = agent.run_sync('What is the capital of Italy?')
print(result.data)  # Rome
```

---

**Usage Limits**

- Limits responses to prevent overuse.
- Example:

```python
from pydantic_ai.usage import UsageLimits
result = agent.run_sync('Answer briefly.', usage_limits=UsageLimits(response_tokens_limit=10))
```

---

**Model Settings**

- Adjust randomness and response length.
- Example:

```python
result = agent.run_sync('What is the capital of Italy?', model_settings={'temperature': 0.0})
```

---

## Introduction to System Prompts

- **What is a System Prompt?**

  - A predefined instruction that guides an AI agent’s behavior.
  - Helps set the tone, style, and context for AI responses.

- **Why Use System Prompts?**

  - Provides consistent responses.
  - Tailors the AI's role and expertise.
  - Ensures the agent aligns with business needs.

---

## Types of Prompts

1. **System Prompt:** Defines the AI's behavior.
2. **User Prompt:** The actual input from the user.
3. **Assistant Response:** The AI’s output based on the prompts.

- **Example:**
  - System Prompt: “You are a helpful customer support agent.”
  - User Prompt: “How do I reset my password?”
  - Assistant Response: “Sure, go to the settings page and click on ‘Reset Password.’”

---

## Setting Up a System Prompt in PydanticAI

```python
from pydantic_ai import Agent

system_prompt = (
    "You are a helpful weather assistant. Your goal is to provide the weather in requested locations."
    " First, ALWAYS use the `get_lat_lng` tool to find the latitude and longitude of the requested locations."
    " The `get_lat_lng` tool takes one argument: `location_description`, which is a string describing the location."
    " Once you have the latitude and longitude, IMMEDIATELY use the `get_weather` tool to get the weather at that location."
    " The `get_weather` tool takes two arguments: `lat` (latitude) and `lng` (longitude), both floating-point numbers."
    " After calling the `get_weather` tool, respond to the user with a single, concise sentence summarizing the weather."
    " Do NOT make up latitude or longitude values. You MUST use the tools."
    " Example: User: What's the weather in Paris? You MUST call get_lat_lng first. Then call get_weather."
)

weather_agent = Agent(
    'openai:gpt-4o',
    system_prompt=system_prompt
)
```

- **Key Parts:**
  - **Model:** Defines which AI model to use.
  - **System Prompt:** Provides specific, step-by-step instructions.

---

## Dynamic System Prompts with Context

```python
from pydantic_ai import RunContext

@weather_agent.system_prompt
async def add_user_context(ctx: RunContext) -> str:
    user_name = "John Doe"  # Example dynamic data
    return f"You are assisting {user_name}. Provide accurate weather updates."
```

- **Purpose:**
  - Adapts responses based on dynamic information.
  - Enhances user engagement with personalized replies.

---

## Best Practices for System Prompts

1. **Be Clear and Specific:**
   - Example: “Always use the `get_lat_lng` tool before `get_weather`.”
2. **Set the Right Tone:**
   - Friendly, professional, or formal as needed.
3. **Use Dynamic Data Wisely:**
   - Personalization increases user satisfaction.
4. **Keep It Updated:**
   - Regularly review prompts to align with business goals.

---

## Recap & Q&A

- **Key Takeaways:**

  - System prompts guide AI behavior effectively.
  - Dynamic prompts enhance personalization.
  - Best practices ensure consistent and quality responses.

- **Questions?**

---

**Error Handling & Retries**

- AI can retry failed responses.
- Example:

```python
@agent.tool(retries=2)
def get_user(ctx: RunContext, name: str) -> int:
    if name not in ctx.deps:
        raise ModelRetry('Provide full name.')
```

---

**Handling Errors**

- Detects unexpected behavior and responds accordingly.
- Example:

```python
try:
    result = agent.run_sync('Find volume of size 6.')
except UnexpectedModelBehavior as e:
    print(e)
```

---

**Runs vs. Conversations**

- A single run can handle a full conversation.
- Multiple runs help maintain state over time.

```
# First run
result1 = agent.run_sync('Who was Albert Einstein?')
print(result1.data)
#> Albert Einstein was a German-born theoretical physicist.

# Second run, passing previous messages
result2 = agent.run_sync(
    'What was his most famous equation?',
    message_history=result1.new_messages(),  
)
```

---

**Type Safety in PydanticAI**

- Works with static type checkers like mypy.
- Type hints prevent coding errors.
- Example:

```python
agent = Agent('test', deps_type=int, result_type=bool)
```

---

**Key Takeaways**

- **Agents manage AI interactions efficiently.**
- **Reusable and modular, like small apps.**
- **Use type hints for structured, predictable results.**
- **Customizable with settings and prompts.**
- **Handles errors and retries automatically.**


---



## Introduction to Logfire

- **What is Logfire?**
  - A logging library designed for monitoring and debugging AI applications.
  - Provides real-time insights into agent behavior and performance.

- **Why Use Logfire with PydanticAI?**
  - Tracks API calls, system prompts, and tool executions.
  - Helps diagnose issues quickly.
  - Improves system reliability.

---

## Setting Up Logfire with PydanticAI

- **Installation:**
  ```bash
  pip install logfire
  ```

- **Basic Configuration:**
  ```python
  import logfire
  from pydantic_ai import Agent

  logfire.configure(api_key="your_api_key")

  agent = Agent(
      'openai:gpt-4o',
      system_prompt='You are a helpful assistant.'
  )
  ```

- **Key Features:**
  - Centralized logging for AI workflows.
  - Simple API integration.

---

## Logging Agent Activity

```python
@agent.tool
async def get_user_data(user_id: int):
    logfire.info(f"Fetching data for user_id: {user_id}")
    # Simulate data retrieval
    return {"name": "John Doe", "balance": 250.0}

async def main():
    result = await agent.run('Get user data for ID 123')
    logfire.info(f"Agent response: {result.data}")
    print(result.data)
```

- **What’s Happening:**
  - `logfire.info()` logs important events.
  - Helps track the flow of data and identify issues.

---

## Advanced Features

- **Structured Logging:**
  ```python
  logfire.log("UserLogin", user_id=123, status="success")
  ```

- **Error Tracking:**
  ```python
  try:
      risky_operation()
  except Exception as e:
      logfire.error("An error occurred", error=str(e))
  ```

- **Performance Monitoring:**
  - Logs execution times.
  - Identifies bottlenecks in AI workflows.

---

## Recap & Q&A

- **Key Takeaways:**
  - Logfire enhances observability in PydanticAI projects.
  - Simplifies debugging with structured logs.
  - Essential for production-level AI applications.

- **Questions?**

---

## Introduction to Gradio

- **What is Gradio?**
  - A Python library for creating simple web interfaces for machine learning models.
  - Allows quick deployment of interactive demos.

- **Why Use Gradio with PydanticAI?**
  - Provides an easy way to showcase AI models.
  - Enables real-time interaction with PydanticAI agents.
  - No need for complex web development.

---

## Setting Up Gradio with PydanticAI

- **Installation:**
  ```bash
  pip install gradio
  ```

- **Basic Configuration:**
  ```python
  import gradio as gr
  from pydantic_ai import Agent

  agent = Agent(
      'openai:gpt-4o',
      system_prompt='You are a helpful assistant.'
  )
  
  def ai_response(prompt):
      result = agent.run_sync(prompt)
      return result.data

  interface = gr.Interface(fn=ai_response, inputs="text", outputs="text")
  interface.launch()
  ```

- **Key Features:**
  - Quick to set up.
  - Interactive user interface.

---

## Customizing the Gradio Interface

- **Adding More Inputs:**
  ```python
  interface = gr.Interface(
      fn=ai_response,
      inputs=[gr.Textbox(label="Your Query"), gr.Checkbox(label="Urgent")],
      outputs="text"
  )
  interface.launch()
  ```

- **Explanation:**
  - Customizes input components.
  - Adjusts the interface layout.

---

## Integrating with PydanticAI Tools

```python
@agent.tool
async def get_user_info(user_id: int):
    return {"name": "Alice", "status": "Active"}

interface = gr.Interface(
    fn=lambda user_id: agent.run_sync(f"Get info for user {user_id}"),
    inputs="number",
    outputs="text"
)
interface.launch()
```

- **What’s Happening:**
  - Gradio interfaces with PydanticAI tools.
  - Users interact with backend AI logic seamlessly.

---

## Best Practices for Using Gradio

1. **Keep It Simple:**
   - Focus on clean and intuitive interfaces.
2. **Ensure Responsiveness:**
   - Optimize for fast response times.
3. **Add Clear Labels:**
   - Help users understand input and output fields.
4. **Test Thoroughly:**
   - Ensure smooth interaction before deployment.

---

## Recap & Q&A

- **Key Takeaways:**
  - Gradio enables quick UI development for AI models.
  - Seamlessly integrates with PydanticAI agents.
  - Ideal for demos, prototypes, and interactive applications.

- **Questions?**