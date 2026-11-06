---
name: subtract
description: Subtract using BashKit's in-process bc builtin
---

# Subtract

Subtract using BashKit's in-process bc builtin.

Use the published input schema and a fresh single FCS target. Calls use pinned tool references. Arithmetic values must be finite and within +/-1e12. Division by zero is an error. The recorded execution report is authoritative for ordering and timings; replay does not execute tools.
