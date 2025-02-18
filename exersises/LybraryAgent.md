# Exercise: Build a Library Support Agent

## Scenario

Imagine you're building an AI agent for a school library. The agent helps students with common questions such as:

- "Is *The Hobbit* available?"
- "What is my due date for the book I just checked out?"
- "Can you tell me my name from the library records?"

## Your Task

Create a **Library Support Agent** using PydanticAI that:

1. **Defines Dependencies:**  
   - Create a `LibraryDependencies` dataclass that includes:
     - `student_id` (an integer)
     - `library_db` (a simulated database connection object)

2. **Sets Up a Result Model:**  
   - Create a Pydantic model (e.g., `LibraryResult`) that includes:
     - `message` (a string for the agent's reply)
     - `due_date` (an optional string, for when a book is due)

3. **Configures the Agent:**  
   - Initialize an agent with a system prompt that instructs it:  
     *"You are a helpful library support agent."*

4. **Adds Dynamic Data with a System Prompt:**  
   - Create a system prompt function that fetches the student's name from the simulated database and adds it to the context.

5. **Creates a Tool:**  
   - Define a tool function (e.g., `check_book_availability`) that takes a book title and returns whether it’s available.

6. **Runs the Agent:**  
   - Write a simple `async` main function that:
     - Creates an instance of `LibraryDependencies` with dummy data.
     - Calls the agent with a sample query (e.g., "Is *The Hobbit* available?").
     - Prints out the returned result.

## Hints

- **Simulated Database:**

  For this exercise, you can create a dummy class for `LibraryDB` with methods like:

  ```python
  class LibraryDB:
      async def get_student_name(self, student_id: int) -> str:
          # Return a dummy name, e.g., "Alice"
          return "Alice"

      async def is_book_available(self, title: str) -> bool:
          # For example, return True if the title is "The Hobbit"
          return title.lower() == "the hobbit"
