# src/agent/nodes/checkpoints.py
from langgraph.types import interrupt
from agent.state import AgentState

def checkpoint_req_doc(state: AgentState) -> dict:
    print("[Checkpoint A] 等待用户确认需求文档...")
    result = interrupt({"type": "confirm_req_doc", "path": state.get("req_doc_path")})
    confirmed = result.get("confirmed", False)
    return {
        "req_doc_confirmed": confirmed,
        "revision_comment": result.get("comment"),
    }

def checkpoint_high_level(state: AgentState) -> dict:
    print("[Checkpoint B] 等待用户确认总体设计...")
    result = interrupt({"type": "confirm_high_level", "path": state.get("high_level_doc_path")})
    confirmed = result.get("confirmed", False)
    return {
        "high_level_confirmed": confirmed,
        "revision_comment": result.get("comment"),
    }
