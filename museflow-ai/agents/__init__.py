"""Deterministic agent-role simulations.

Each module implements one *role* as a plain, deterministic Python function. These are
NOT autonomous LLM agents: they are orchestrated by a real LangGraph StateGraph, read
synthetic fixtures, and call only allowlisted, simulated tools.
"""
