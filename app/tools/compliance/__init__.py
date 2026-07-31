"""Compliance layer for outbound calling and messaging.

Modules:
- dnc        : Do-Not-Call list checks (national + state + internal)
- tcpa       : Time-of-day window guard in recipient timezone
- consent    : Immutable consent log writer
- disclosure : Recording / AI disclosure phrase builder

These wrap raw rules; legal sign-off on the consent model and call scripts is
required before phase 3 outbound calling goes live.
"""
