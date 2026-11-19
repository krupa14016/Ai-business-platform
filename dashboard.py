import streamlit as st
import pandas as pd

from free_agent import ask
from ai_tools import run_tool

st.set_page_config(
    page_title="AI Business Intelligence",
    page_icon="📊",
    layout="wide",
)

st.title("AI Business Intelligence Platform")
st.caption("Financial analytics and database-grounded AI assistance")

# Load verified summary data through the existing analytics tool.
try:
    summary = run_tool("get_summary", {})
    if not isinstance(summary, dict) or summary.get("error"):
        summary = {}
except Exception:
    summary = {}

st.subheader("Financial overview")

if summary:
    cols = st.columns(4)
    cards = [
        ("Revenue", "revenue_display"),
        ("Net income", "net_income_display"),
        ("Net profit margin", "net_margin_pct_display"),
        ("Current ratio", "current_ratio_display"),
    ]

    for col, (label, key) in zip(cols, cards):
        value = summary.get(key)
        with col:
            st.metric(label, value if value is not None else "Not available")

    if summary.get("fiscal_year") is not None:
        st.caption(f"Latest fiscal year in the data: {summary['fiscal_year']}")
else:
    st.warning(
        "The summary could not be loaded. "
        "The chat may still work; check your analytics tool if this persists."
    )

st.divider()
st.subheader("Ask your financial data")

st.write(
    "Ask about historical revenue, profit, margins, annual comparisons, "
    "financial trends, or balance-sheet metrics."
)

with st.expander("Example questions"):
    st.markdown(
        """
        - What was Apple's revenue in 2024?
        - Which fiscal year had the highest revenue?
        - Compare revenue in 2023 and 2024.
        - What was the net profit margin in 2025?
        - Show the revenue trend.
        """
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask a question about Apple's financial data...")

if question:
    st.session_state.messages.append(
        {"role": "user", "content": question}
    )

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Checking the financial data..."):
            try:
                result = ask(question)
                answer = result.get(
                    "answer",
                    "The system did not return an answer."
                )
                status = result.get("status", "unknown")
                tool_calls = result.get("tool_calls", [])
                latency = result.get("latency_ms")

                st.markdown(answer)

                if status != "ok":
                    st.warning("The request encountered an error.")

                with st.expander("Answer details"):
                    st.write("Status:", status)
                    st.write("Tools used:", [
                        item.get("tool", "unknown")
                        for item in tool_calls
                    ])
                    if latency is not None:
                        st.write("Response time:", f"{latency} ms")

            except Exception as exc:
                answer = (
                    "I could not process that question. "
                    "Check the terminal for the underlying error."
                )
                st.error(answer)
                print(f"Dashboard error: {exc!r}")

    st.session_state.messages.append(
        {"role": "assistant", "content": answer}
    )

if st.button("Clear conversation"):
    st.session_state.messages = []
    st.rerun()

st.divider()
st.caption(
    "Prototype: financial answers depend on the connected database and "
    "the supported question patterns. Always validate results before "
    "using them for business decisions."
)
