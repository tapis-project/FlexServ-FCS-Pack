---
name: deployment-recipe-resolve
description: Use the reviewed vLLM deployment tools through an authorized FCS target.
---

# edu.utexas.tacc.flexserv.deployment.vllm.recipe.resolve

Use this tool with one authorized FCS target. Retain owner-bound references from inspect and prepare; plan returns the exact reviewed revision and digest. Execute accepts those references, never a caller-supplied command. Monitor can poll or return an authenticated event subscription. Cancel handles startup cancellation and stopping a ready deployment. The new executor currently supports single-node TP/PP; use the retained reviewed workflow for other layouts.
