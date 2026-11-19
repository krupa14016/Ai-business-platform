import agent_router as ai_agent

print("Ask about Apple's financials. Type 'quit' to exit.")
while True:
    q = input("\nYou: ").strip()
    if q.lower() in {"quit", "exit"}:
        break
    if not q:
        continue
    r = ai_agent.ask(q)
    print("\nAI:", r["answer"])
    print("   [tools used:", [t["tool"] for t in r["tool_calls"]], "|", r["latency_ms"], "ms ]")
