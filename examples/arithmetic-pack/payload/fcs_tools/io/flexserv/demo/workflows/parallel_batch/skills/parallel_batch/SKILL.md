---
name: parallel-batch
description: Map complete expressions concurrently with ordered collected results
---

# Parallel Batch

Map complete expressions concurrently with ordered collected results.

Use the published input schema and a fresh single FCS target. Calls use pinned tool references. Arithmetic values must be finite and within +/-1e12. Division by zero is an error. The recorded execution report is authoritative for ordering and timings; replay does not execute tools.
