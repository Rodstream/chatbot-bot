from anthropic import Anthropic
from app.core.config import settings
from app.models.chat import ChatMessage
from typing import List, Optional


class ClaudeService:
    """Servicio para interactuar con Claude API de Anthropic"""

    def __init__(self):
        """Inicializa el cliente de Anthropic"""
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY no está configurada en las variables de entorno")

        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-5"  # Claude Sonnet 4.5 - Balance perfecto para RAG
        self.max_tokens = 2048  # Aumentamos tokens para respuestas más completas

    async def chat(
        self,
        message: str,
        conversation_history: List[ChatMessage] = None,
        system_prompt: Optional[str] = None
    ) -> dict:
        """
        Envía un mensaje a Claude y obtiene la respuesta

        Args:
            message: Mensaje del usuario
            conversation_history: Historial de conversación previo
            system_prompt: Prompt del sistema para configurar el comportamiento

        Returns:
            dict con la respuesta y metadatos
        """
        try:
            # Construir el historial de mensajes en el formato de Anthropic
            messages = []

            # Agregar historial previo si existe
            if conversation_history:
                for msg in conversation_history:
                    messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })

            # Agregar el mensaje actual del usuario
            messages.append({
                "role": "user",
                "content": message
            })

            # Preparar parámetros de la llamada
            params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": messages
            }

            # Agregar system prompt si existe
            if system_prompt:
                params["system"] = system_prompt

            # Llamar a la API de Claude
            response = self.client.messages.create(**params)

            # Extraer la respuesta
            assistant_message = response.content[0].text

            return {
                "response": assistant_message,
                "model_used": self.model,
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens
            }

        except Exception as e:
            raise Exception(f"Error al comunicarse con Claude API: {str(e)}")

    def chat_stream(
        self,
        message: str,
        conversation_history: List[ChatMessage] = None,
        system_prompt: Optional[str] = None
    ):
        """
        Stream de respuesta de Claude, yield cada chunk de texto.

        Yields:
            dict con type="token" y content, o type="done" con metadatos
        """
        messages = []

        if conversation_history:
            for msg in conversation_history:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        messages.append({
            "role": "user",
            "content": message
        })

        params = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages
        }

        if system_prompt:
            params["system"] = system_prompt

        with self.client.messages.stream(**params) as stream:
            for text in stream.text_stream:
                yield {"type": "token", "content": text}

            # Al terminar, obtener metadatos del mensaje final
            response = stream.get_final_message()
            yield {
                "type": "done",
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
                "model": self.model
            }

    async def chat_simple(self, message: str) -> str:
        """
        Versión simplificada para obtener solo la respuesta de texto

        Args:
            message: Mensaje del usuario

        Returns:
            Respuesta de Claude como string
        """
        result = await self.chat(message)
        return result["response"]


# Instancia global del servicio
claude_service = ClaudeService()
