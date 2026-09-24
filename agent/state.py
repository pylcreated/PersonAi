# chat-agent/agent/state.py
from typing import TypedDict, Optional


class NegotiationState(TypedDict, total=False):
    user_input: str
    conversation_id: str
    phase: str          # goal | template | slice | update | confirm | finalize | done
    round: int
    max_round: int
    goal: Optional[str]
    template: Optional[dict]
    slice_policy: Optional[dict]
    update_policy: Optional[dict]
    history: list
    confidence: float
    user_confirmed: bool
    needs_review: bool
    policy_id: Optional[str]


def init_state(user_input: str, conversation_id: str) -> NegotiationState:
    return {
        "user_input": user_input,
        "conversation_id": conversation_id,
        "phase": "goal",
        "round": 0,
        "max_round": 8,
        "goal": None,
        "template": None,
        "slice_policy": None,
        "update_policy": None,
        "history": [],
        "confidence": 0.0,
        "user_confirmed": False,
        "needs_review": False,
        "policy_id": None,
    }