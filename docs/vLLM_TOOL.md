---
title: vLLM Tool Spec
related:
  - ../../FlexServ-Site-Configs/spec/directory_spec.md
---

# vLLM Tool Spec

## Prerequisites

This guide assumes the site administrator has already installed uv, uv-managed CPython, and the Rust toolchain (including `rustc` and Cargo) for the node's architecture. Before running setup commands, set `FLEXSERV_SHARED_RESOURCE_DIR` to the site's shared root and source `"$FLEXSERV_SHARED_RESOURCE_DIR/flexserv-env.sh"`. See [Software installed by site init](../../FlexServ-Site-Configs/spec/directory_spec.md#software-installed-by-site-init).

## Site installation

Provision an exact vLLM package version on the target compute partition. From the root of `FlexServ-Site-Configs`, with `FLEXSERV_SHARED_RESOURCE_DIR`, `FLEXSERV_SYSTEM_ID`, and `SLURM_JOB_PARTITION` set, run:

```sh
sh scripts/site_init/backend_install.sh vllm 0.33.0
```

FCS uses `virt_envs/vllm-<system>-<partition>/bin/vllm` under the shared root. For accelerator-specific wheel selection and forced reinstallation, see the [backend installation spec](../../FlexServ-Site-Configs/spec/backend_install_spec.md#how-vllm-is-installed).

The `io.flexserv.vllm.advanced.inspect` and `io.flexserv.vllm.execute` wrappers
bind process-group ABI version 1 in their native call envelopes. FCS advertises
and executes process-group layouts when both the loaded Pack and site permit
them. User arguments contain only the deployment inputs.
