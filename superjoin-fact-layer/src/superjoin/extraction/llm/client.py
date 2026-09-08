from abc import ABC, abstractmethod
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class LLMClient(ABC):
    """Abstract interface for interacting with LLMs for structured extraction."""
    
    @abstractmethod
    def extract_structured(self, prompt: str, context: str, schema: Type[T]) -> T:
        """
        Extract structured data from context based on the prompt.
        
        Args:
            prompt: The instruction prompt for the LLM.
            context: The context string (usually JSON serialized).
            schema: The Pydantic model class defining the expected output.
            
        Returns:
            A validated Pydantic model instance of type T.
        """
        pass
