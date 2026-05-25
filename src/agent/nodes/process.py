# src/agent/nodes/process.py
from agent.state import AgentState

def process_requirement(state: AgentState) -> dict:
    print("[Node 1] process_requirement")
    return {"requirements": {}}
