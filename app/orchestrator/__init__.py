"""LangGraph-based orchestrator for the autonomous AI services business.

Layout:
- state.py        : typed graph state shared across nodes
- checkpointer.py : Postgres checkpointer (Supabase-backed) for durability
- runs.py         : run lifecycle (create row, emit events, mark terminal)
- graph.py        : supervisor graph builder + registry of run_types
- nodes/          : one file per agent (noop, eval, research, content, ...)
"""
