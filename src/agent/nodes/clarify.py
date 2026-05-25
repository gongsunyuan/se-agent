# src/agent/nodes/clarify.py
from agent.state import AgentState

def clarify(state: AgentState) -> dict:
    print("[Node 3] clarify")
    return {
        "clarification_round": state["clarification_round"] + 1,
        "user_answers": [],
    }
