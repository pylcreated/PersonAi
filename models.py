# chat-agent/models.py
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Message:
    role: str
    content: str
    timestamp: Optional[str] = None

@dataclass
class Conversation:
    source: str
    conversation_id: str
    title: str
    created_at: str
    updated_at: Optional[str] = None
    messages: List[Message] = field(default_factory=list)

@dataclass
class Turn:
    turn_index: int
    question: str
    answer_plain: str
    text_plain: str
    user_timestamp: Optional[str] = None
    assistant_timestamp: Optional[str] = None

@dataclass
class CleanedConversation:
    conversation_id: str
    source: str
    title: str
    created_at: str
    turns: List[Turn] = field(default_factory=list)
    clean_hash: str = ""