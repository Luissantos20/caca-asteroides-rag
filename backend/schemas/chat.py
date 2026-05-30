from pydantic import BaseModel, Field
from typing import Literal


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Pergunta do usuário"
    )
    history: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=10,
        description="Últimas mensagens da conversa (até 10 itens)"
    )