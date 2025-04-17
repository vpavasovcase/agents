"""Library Support Agent implementation using PydanticAI.

This agent helps students with common library questions about book availability,
due dates, and student information.
"""

from dataclasses import dataclass
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.gemini import GeminiModel
from dotenv import load_dotenv
import sys

import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

gemini = GeminiModel(
    model_name=os.getenv('PYDANTIC_AI_MODEL'),
    api_key=os.getenv('GEMINI_API_KEY'),
)


class LibraryDB:
    """Simulated library database connection."""

    async def get_student_name(self, student_id: int) -> str:
        """Fetch student name from the database."""
        # Return a dummy name for this example
        return "Alice"

    async def is_book_available(self, title: str) -> bool:
        """Check if a book is available."""
        # For example, return True if the title is "The Hobbit"
        return title.lower() == "the hobbit"
    
    async def get_due_date(self, student_id: int) -> str:
        """Get the due date for the student's most recent checkout."""
        # Return a dummy due date
        return "May 15, 2023"


@dataclass
class LibraryDependencies:
    """Dependencies needed for the library support agent."""
    student_id: int
    library_db: LibraryDB


class LibraryResult(BaseModel):
    """Result model for library support agent responses."""
    message: str = Field(description="The agent's reply to the student")
    due_date: str | None = Field(None, description="Due date for a book when applicable")


library_agent = Agent(
    model=gemini,
    deps_type=LibraryDependencies,
    result_type=LibraryResult,
    system_prompt="You are a helpful library support agent for a school library."
)


@library_agent.system_prompt
async def add_student_name(ctx: RunContext[LibraryDependencies]) -> str:
    """Add the student's name to the context."""
    student_name = await ctx.deps.library_db.get_student_name(ctx.deps.student_id)
    return f"The student's name is {student_name!r}"


@library_agent.tool
async def check_book_availability(
    ctx: RunContext[LibraryDependencies], title: str
) -> str:
    """Check if a specific book is available in the library."""
    is_available = await ctx.deps.library_db.is_book_available(title)
    if is_available:
        return f"'{title}' is currently available in the library."
    else:
        return f"'{title}' is currently not available in the library."


@library_agent.tool
async def get_book_due_date(ctx: RunContext[LibraryDependencies]) -> str:
    """Get the due date for the student's most recent checkout."""
    due_date = await ctx.deps.library_db.get_due_date(ctx.deps.student_id)
    return f"Your book is due on {due_date}."


async def main():
    """Run the library support agent in an interactive chat loop."""
    # Create an instance of dependencies with dummy data
    deps = LibraryDependencies(student_id=42, library_db=LibraryDB())
    
    print("=== Library Support Agent Chat ===")
    print("Type 'exit', 'quit', or 'bye' to end the conversation")
    print("Example questions:")
    print("- Is The Hobbit available?")
    print("- What is my due date for the book I just checked out?")
    print("- Can you tell me my name from the library records?")
    print("===============================")
    
    # List to store conversation history
    conversation_history = []
    
    while True:
        # Get user input
        user_query = input("\nYou: ").strip()
        
        # Check if user wants to exit
        if user_query.lower() in ["exit", "quit", "bye"]:
            print("\nThank you for using the Library Support Agent. Goodbye!")
            break
        
        if not user_query:
            continue
            
        # Process the query
        print("\nAgent is thinking...")
        try:
            result = await library_agent.run(user_query, deps=deps, message_history=conversation_history)
            print(f"\nAgent: {result.data.message}")
            
            # Store the messages from this interaction in the conversation history
            conversation_history = result.all_messages()
            
            # Display due date if it's available
            if result.data.due_date:
                print(f"Due Date: {result.data.due_date}")
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 