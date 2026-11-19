import os

from dotenv import load_dotenv

from audit import ensure_audit_table  # noqa: F401  (re-exported for bi_api.py)

load_dotenv()


def ask(question):
    """Chooses which "brain" answers. Default is the free rule-based one."""
    provider = os.getenv("AI_PROVIDER", "rules").strip().lower()
    if provider == "anthropic":
        import ai_agent
        return ai_agent.ask(question)
    import free_agent
    return free_agent.ask(question)
