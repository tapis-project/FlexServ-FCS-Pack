---
title: mistral.rs Deployment Tool Spec
related:
  - ../../FlexServ-Site-Configs/spec/directory_spec.md
  - ../../FlexServ-Site-Configs/spec/backend_install_spec.md
---

# mistral.rs Deployment Tool Spec

## Deployment scope

As of November 4, 2026, FlexServ uses mistral.rs as a single-node-only backend. Each mistral.rs deployment must run entirely on one allocated node. Multiple GPUs within that node are allowed, but multi-node deployments are outside the supported scope, even when the installed binary includes NCCL support.

## Deployment wizard and CLI catalog contract

The gateway deployment wizard will load a versioned JSON catalog of mistral.rs `serve` options. The catalog is a design artifact until gateway and FCS integration is implemented. It must identify the upstream release and source revision, distinguish CLI defaults from FlexServ policy, and record each option's display name, purpose, accepted values, default, required conditions, behavior when omitted, automatic inference, conflicts, and model/build applicability. Short names and aliases count as the same option. Other commands such as `run`, `bench`, and `quantize` are outside the deployment catalog.

The wizard starts with the model, a quality/balanced/speedy preference, context length, concurrency, and allocated GPU selection. It then shows a searchable, scrollable list of named options grouped by purpose. Each option has a tooltip explaining its effect, allowed values, upstream default, and whether omission triggers automatic inference or simply leaves the feature disabled. Unset, explicitly set, and preset-selected values must remain distinguishable. The review screen shows the resolved model/artifact, quantization, GPU set, arguments, and the reasons for recommendations.

Every FlexServ mistral.rs process must receive `MISTRALRS_NO_NCCL=1`, including launches using multiple GPUs on one node. This is a fixed launch environment variable, not a CLI option or user-editable setting. Multi-node configuration is prohibited. GPU selection uses `CUDA_VISIBLE_DEVICES` for CUDA deployments. Only GPUs granted to the job may be selected. FCS must validate the selection against the allocation and preserve the scheduler's device mapping; host GPU ordinals must not be copied blindly into a job/container. Layer-mapping ordinals refer to the resulting visible device list.

GPU choices must show total and available VRAM for each allocated device. Recommendations must budget model weights, KV cache, runtime workspace, and multimodal/adapter overhead for the requested context and concurrency. A sum of device VRAM alone does not establish that a model fits. Revalidate on the compute node before launching. Unknown memory requirements must be shown as unknown rather than as a fit guarantee.

Quality, balanced, and speedy are FlexServ recommendation policies, not upstream modes. Quality prefers the selected checkpoint without additional quantization. Balanced and speedy may recommend `--quant` using a compatible quantization level after checking model support and memory requirements. Never imply that fewer bits always means faster inference. Pre-quantized checkpoints retain their original quantization when no extra quantization flag is supplied. Explicit user choices take precedence over recommendations, but cannot override allocation or single-node restrictions. Unsupported combinations must be explained before launch.

FCS will consume structured options and construct an argument array and a separate environment map, without shell interpolation. Both gateway and FCS must validate types, required conditions, conflicts, paths, and installed backend version against the catalog. Omit unset optional arguments so upstream automatic behavior remains available. A catalog version mismatch must require a reviewed catalog update rather than silently accepting unknown options.

### Catalog format and coverage

The initial catalog is [mistralrs-0.9.5.json](catalogs/mistralrs-0.9.5.json), reviewed on November 4, 2026 against upstream commit `465191d0b0a7e2432d327b0de06204ab3f94d3a2` (`v0.9.5`). It covers the flat `mistralrs serve ...` command, which automatically selects the model type. The gateway will load the matching catalog, expose it to the wizard, and include its schema version, backend version, and source revision in the deployment plan. FCS must use the same catalog revision. Distribution/loading of this artifact is part of the subsequent gateway/FCS implementation.

There are **89 deployment configuration options** in this default-feature build: 85 `serve` options and four inherited global options. Including `--help` and `--version`, there are **91 distinct options**. Aliases and short spellings are not counted twice. Nine options require the `code-execution` build feature; without it there are 80 configuration options. These counts are for serving, not the union of every maintenance, benchmark, and interactive subcommand. Typed model subcommands (`auto`, `text`, `multimodal`, `diffusion`, `speech`, `embedding`) have different option subsets; the wizard emits the flat form.

Each `flags` entry contains the following fields. The catalog uses JSON-native booleans and numbers for defaults, and `null` means no explicit CLI default, not necessarily that runtime behavior is disabled.

| Field | Gateway/FCS use |
|---|---|
| `id`, `flag`, `aliases`, `syntax` | Stable selection key and argument spelling. Emit the canonical long flag. |
| `label`, `group`, `description`, `when_to_set` | Named, grouped UI entries with purpose and usage tooltips. |
| `values` | Input type, enum or value syntax, numeric bounds, and dynamically discovered artifact values. These are catalog metadata, not a standalone JSON Schema. |
| `cli_default` | Default declared by the upstream CLI parser. |
| `omission.kind`, `omission.best_effort`, `omission.behavior` | Distinguish discovery/inference from a fixed default or a disabled feature; explain runtime defaults separately. |
| `required`, `requires_all`, `requires_any`, `conflicts` | Requirements and relationships between explicit options. Defaults do not activate dependency rules. |
| `applicability` | Model, device, build-feature, and additional semantic conditions. Prose conditions need explicit validation code in FCS, not evaluation as expressions. |
| `ui`, `flexserv_policy` | Common/advanced/managed presentation, editability, and FlexServ overrides separate from upstream defaults. |
| `sources` | Evidence paths relative to the pinned upstream checkout. |

The UI must display all applicable named options in a scrollable list, with common options first and advanced groups available by search/filter. Unavailable options remain discoverable with an explanation. Managed values are read-only. `informational_flags` are excluded from launch controls because they exit without serving. Booleans emit a switch only when true, `verbose` emits repeated switches, and LoRA arrays emit separate argument values. A JSON object such as `hf-overrides` is serialized as one argument. Explicit unset clears the override. Do not turn a displayed default into an explicit argument automatically.

### Required inputs and common options

No individual CLI flag is universally required in every upstream invocation. A **model source** is always required for serving. Usually that is `--model-id`; flat `serve -f /path/model.gguf` can derive it from existing local quantized files. Explicit typed model subcommands require `--model-id`. FlexServ requires a model selection and resolves it into `--model-id` for its canonical launch path.

| Option | Required by upstream? | Omitted behavior and typical use |
|---|---|---|
| `--model-id`, `-m` | Conditional as above | No default model. Select an HF repository or local checkpoint directory. |
| `--port`, `-p`; `--host` | No | Defaults `1234` and `0.0.0.0`. FCS supplies the allocated port and routed bind address. |
| `--hf-cache` | No | Uses upstream cache resolution. FCS supplies the configured FlexServ cache path. |
| `--no-ui` | No | Upstream UI is enabled. FlexServ emits this switch to use its gateway UI. |
| `--quant` | No | No additional quantization. Select an artifact or allow ISQ fallback for a supported source checkpoint. |
| `--dtype` | No | `auto` selects supported floating-point precision. It does not select a weight quantization level. |
| `--max-model-len` | No | Uses the model's native context length. Set a workload-specific cap to control memory. |
| `--max-seqs` | No | `serve` defaults to 32 concurrent sequences. This is a fixed default, not a VRAM-based guess. |
| `--device-layers`, `-n` | No | Automatic layer mapping across visible devices. Set only to override placement. |
| `--paged-attn` | No | `auto` enables supported CUDA/Metal paged attention and disables it on CPU. |
| `--gpu-memory-utilization` or `--kv-cache` | No | Automatic memory planning. The two overrides conflict; explicit goals require paged attention. |
| `--token-source` | No | Uses cached credentials. A gated/private model may need an explicit `env:VARIABLE` or `path:FILE` source. |

Other conditional requirements include paired X-LoRA/legacy-LoRA ordering files, a MatFormer config when selecting a slice, and an enabled execution tool when configuring its interpreter/workdir. Missing or ambiguous model assets can require explicit tokenizer/projector/template choices. The catalog records these cases; “automatic” does not promise that any checkpoint will load.

Sampling controls such as temperature, top-p, output-token limits, and per-request reasoning controls belong to inference API requests. Do not import flags exclusive to `run` into a `serve` deployment.

### Quantization recommendation flow

1. Resolve the checkpoint format, supported model architecture, selected GPU set, context length, concurrency, and optional adapters/media workload.
2. On the allocated compute node, run `mistralrs tune -m <model> --profile <profile> --json` with the same GPU visibility and `MISTRALRS_NO_NCCL=1` as the eventual server. Map quality/balanced/speedy to upstream quality/balanced/fast. Carry compatible model-source options into this probe, but do not pass `serve` runtime flags that `tune` does not accept.
3. Read `candidates`, fit status, estimated memory/context, `recommended_isq`, placement, warnings, and notes as structured data. Never execute `recommended_command`. Treat hybrid CPU offload as an explicit tradeoff in the UI. Tuning is an estimate, not a measured speed result or a guarantee for the requested serving workload. It rejects configured adapters; their memory and other unsupported workloads need separate planning.
4. For quality, first evaluate the unchanged checkpoint candidate against the full workload. Upstream's quality profile itself prefers quantized candidates, so blindly copying its recommendation would not implement FlexServ's original-model preference. When it does not fit, present compatible alternatives and their precision tradeoffs. Balanced typically starts at Q6K on CUDA/CPU or AFQ6 on Metal; speedy starts at Q4K or AFQ4. Lower-bit alternatives must be shown explicitly, not silently selected after an out-of-memory failure.
5. Resolve the chosen candidate to an explicit `--quant` value or omit extra quantization flags for the unchanged checkpoint. Save the resolved artifact identity and format in the deployment plan. `--quant` can discover a different published artifact, so recheck that artifact's memory/support and record what was actually loaded. If tuning is unsupported or fails, show an unknown estimate and require a compatible manual choice instead of inventing a recommendation.

For ISQ, numeric levels `2`, `3`, `4`, `5`, `6`, `8` resolve on CUDA/CPU to Q2K, Q3K, Q4K, Q5K, Q6K, Q8_0; Metal resolves them to AFQ2, AFQ3, AFQ4, Q5K, AFQ6, AFQ8. Published GGUF/UQFF artifact selection can have different concrete formats. A smaller bit width does not guarantee higher throughput, and checkpoint quality must be evaluated for the intended use.

Code inspection adds a detail not listed in the generated flag summary: `serve --quant auto` invokes balanced tuning for eligible non-GGUF source checkpoints. It is optional and differs from omitting `--quant`. GGUF discovery and `tune --quant auto` reject `auto`. FlexServ's reviewed launch plan uses the resolved explicit choice so a user can see its precision before launch. `--isq` forces runtime quantization, while `--from-uqff` loads a specified artifact. `--quant` conflicts with both and with `--quantized-file`. GPTQ/AWQ/native quantized checkpoints can load their existing quantization without any of these extra switches.

### GPU selection and launch example

With NCCL disabled, multiple visible CUDA devices use layer mapping with peer transfers where supported and CPU staging otherwise. This does not enable NCCL tensor parallelism. Keep `RING_CONFIG` and all `MISTRALRS_MN_*` variables out of the child environment to enforce the single-node scope even when inherited from the job environment.

The default GPU selection is the scheduler-granted visible set. The user may choose a subset using the allocation inventory and per-device VRAM. For example, if the job grants host devices `2,5`, selection of the second granted device must resolve through that mapping rather than blindly setting host device `1`. Use stable allocation/device identifiers and resolve them inside the actual container/job namespace. Once visibility is narrowed, layer-mapping ordinal `0` is the first device in the narrowed list. Never widen visibility beyond the allocation. CPU mode must not emit a contradictory GPU selection.

Illustrative launch after FCS has resolved the paths and network settings, with the scheduler's GPU selection retained:

```sh
MISTRALRS_NO_NCCL=1 \
  "$CARGO_INSTALL_ROOT/mistralrs-$FLEXSERV_SYSTEM_ID-$SLURM_JOB_PARTITION/bin/mistralrs" \
  serve --model-id "$model_path" --host "$bind_address" --port "$assigned_port" \
  --hf-cache "$model_cache" --no-ui
```

A reviewed quantized deployment adds, for example, `--quant 6`. GPU subset selection is applied separately to the child environment after allocation validation. This example documents the launch contract; it does not implement a launcher in this repository.

### Evidence and validation

The flag inventory comes from the upstream [generated serve reference](../../mistral.rs/docs/src/content/docs/reference/cli/serve.md) and [global options](../../mistral.rs/docs/src/content/docs/reference/cli/index.md), checked against [CLI definitions](../../mistral.rs/mistralrs-cli/src/args/mod.rs), [model options](../../mistral.rs/mistralrs-cli/src/args/model.rs), and the server, cache, and sandbox argument modules. Automatic behavior was checked in [serve resolution](../../mistral.rs/mistralrs-cli/src/commands/serve.rs), [quant resolution](../../mistral.rs/mistralrs-cli/src/commands/quant.rs), [tuning](../../mistral.rs/mistralrs-core/src/tuning.rs), and the [distributed inference guide](../../mistral.rs/docs/src/content/docs/guides/perf/distributed-inference.mdx).

Run `python3 -m unittest discover -s tests -p 'test_mistralrs_catalog.py'` from `FlexServ-FCS-Pack` to check catalog completeness and policy metadata. Source-parity checks use the adjacent pinned `mistral.rs` checkout when available. A backend upgrade requires reviewing defaults, feature gates, conflicts, and inference behavior before updating the catalog and its version. Runtime UI integration and GPU/model smoke tests remain subsequent implementation work.

## Prerequisites

This guide assumes the site administrator has already installed uv, uv-managed CPython, and the Rust toolchain (including `rustc` and Cargo) for the node's architecture. Before running setup commands, set `FLEXSERV_SHARED_RESOURCE_DIR` to the site's shared root and source `"$FLEXSERV_SHARED_RESOURCE_DIR/flexserv-env.sh"`. See [Software installed by site init](../../FlexServ-Site-Configs/spec/directory_spec.md#software-installed-by-site-init).

## Site installation

A site administrator installs an exact mistral.rs release before an FCS job deploys a model. From the root of `FlexServ-Site-Configs`, use the shared resource directory selected for the target system and run the installer on a node with the intended accelerator visible.

```sh
# Example inside a Vista allocation; Slurm supplies SLURM_JOB_PARTITION.
export FLEXSERV_SYSTEM_ID=Vista

# Install the selected release for this system and partition.
sh scripts/site_init/backend_install.sh mistralrs v0.9.5

# To replace the same release with a fresh installation:
sh scripts/site_init/backend_install.sh --reinstall mistralrs v0.9.5
```

## Executable used by the deployment tool

The proposed deployment tool should resolve `tools/<arch>/rust/apps/mistralrs-<system>-<partition>/bin/mistralrs` under the selected shared resource directory. Before launching `mistralrs serve`, it should check that the executable runs on the allocated node and reports the deployment's requested version. If the executable is missing or the version differs, report the selected system, partition, path, and expected version so the site administrator can provision it.

For example, after sourcing the site environment, this check should print `mistralrs 0.9.5` for the example above:

```sh
"$CARGO_INSTALL_ROOT/mistralrs-$FLEXSERV_SYSTEM_ID-$SLURM_JOB_PARTITION/bin/mistralrs" --version
```

The backend installation spec describes hardware selection, bundled libraries, and how a successful reinstall takes effect for subsequent jobs. [Backend installation spec](../../FlexServ-Site-Configs/spec/backend_install_spec.md)
