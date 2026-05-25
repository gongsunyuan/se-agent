# src/agent/nodes/judge.py
from agent.state import AgentState

def judge(state: AgentState) -> dict:
    print("[Node 2] judge")
    return {"is_clear": True}
