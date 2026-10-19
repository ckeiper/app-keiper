"""Bounded HTTP budget for XLSX parsing on the shared Render CPU.

The real 1.9 MB reconciliation report took 23 seconds even with a single pass.
The default 30-second worker timeout left no margin for normal CPU variation.
Application upload/ZIP/row limits remain the primary resource bounds.
"""
timeout = 120
