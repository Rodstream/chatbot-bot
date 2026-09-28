from pydantic import BaseModel
from typing import List, Literal, Optional


class ChatMessage(BaseModel):
    """Modelo para un mensaje individual en el chat"""
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Modelo para la petición de chat"""
    message: str
    conversation_history: Optional[List[ChatMessage]] = []

    @property
    def safe_message(self) -> str:
        return self.message[:2000].strip() if self.message else ""


class ChatResponse(BaseModel):
    """Modelo para la respuesta de chat"""
    model_config = {"protected_namespaces": ()}

    response: str
    model_used: str
    tokens_used: Optional[int] = None
