---
title: Model Download and Repository Management Spec
related:
  - ../../FlexServ-Site-Configs/spec/directory_spec.md
  - ../../FlexServ/spec/Architecture.md
  - ../../FlexServ/flexserv/gateway/src/model/model_catalog_config.json
---

# Model download and repository management

Status: Draft target contract. This document defines repository paths, model
IDs, directory mapping, and discovery/management UI behavior. Runtime
enforcement of the amended contracts is pending implementation.

## Repository paths

A **model repository** is a host directory containing locally stored models.
FlexServ uses two repository roots for the selected site, system, and job user:

| Repository | Path key | Host path | Managed by |
| --- | --- | --- | --- |
| Public | `public_model_repo_path` | `${flexserv_shared_resource_dir}/models` | Site administrator; readable by authorized job users |
| Private | `private_model_repo_path` | `${flexserv_user_resource_dir}/models` | Job user; default destination for model downloads |

The two resource roots come from the selected system in the
[site directory spec](../../FlexServ-Site-Configs/spec/directory_spec.md).
Resolve them first, then append `models` exactly once. Model repositories have
no additional site, partition, CPU architecture, or inference backend directory.
The same stored model can be used by vLLM or mistral.rs when compatible.

“Public” and “private” describe local ownership and access. A model downloaded
from a public upstream repository still belongs in the user's private repository
unless a site administrator explicitly publishes it to the public repository.

### Path resolution

1. Select the site and system using `FLEXSERV_SITE_ID` and
   `FLEXSERV_SYSTEM_ID`, following the site directory spec.
2. Resolve `flexserv_shared_resource_dir` and `flexserv_user_resource_dir` on
   the execution host for the job user. For `HOST_EVAL($SCRATCH)/flexserv`, use
   that user's `SCRATCH`; if it is unset or empty, use `$HOME/.flexserv` as
   specified by the site directory spec.
3. Derive both repository paths from those resolved absolute roots. Gateway and
   every participating FCS instance must agree on the paths. A collective
   download requires the private path to refer to the same shared storage on
   all participating nodes.
4. Use host paths for repository operations. If inference runs in a container,
   the launcher maps the selected host path into the container and supplies the
   corresponding container path to the backend.

Repository roots are configuration, not per-download destination inputs. A
missing or inaccessible root must produce an error identifying the path;
repository initialization creates missing roots separately. Do not silently
switch to the working directory or a library's default cache.

### Repository root versus model directory

`public_model_repo_path` and `private_model_repo_path` identify the parent
directories. Each repository revision occupies a child directory:

```text
<repository_root>/<escaped-author>--<escaped-model>[---<escaped-revision>]/
```

For example, the upstream model ID `Qwen/Qwen3-8B` maps to the local directory
name `Qwen--Qwen3-8B`. Preserve capitalization. Treat upstream IDs and local
paths as separate values; local names must be a single directory component,
must not be `.` or `..`, and must not escape the selected root through symlinks.
An explicit revision adds the `---<escaped-revision>` suffix; omitting the
revision adds no suffix. Record the requested ID and resolved immutable revision
in model metadata. Naming collisions must be reported,
never resolved by overwriting another model.

For a Vista job with these resolved resource roots:

```text
flexserv_shared_resource_dir = /work/projects/aci/cic/apps/flexserv
flexserv_user_resource_dir   = /scratch/12345/alice/flexserv
```

the repository and model paths are:

```text
Public repository:  /work/projects/aci/cic/apps/flexserv/models
Public model:       /work/projects/aci/cic/apps/flexserv/models/Qwen--Qwen3-8B

Private repository: /scratch/12345/alice/flexserv/models
Private model:      /scratch/12345/alice/flexserv/models/Qwen--Qwen3-8B
```

The scratch path above is illustrative; use the job user's resolved path.
Downloads write to the private repository by default. Ordinary download and
deployment operations must not modify the public repository or copy private
models into it automatically.

### Existing path names

Existing interfaces use the following names for these same host roots:

| Interface | Public repository | Private repository |
| --- | --- | --- |
| Site configuration's derived paths | `public_model_repo_path` | `private_model_repo_path` |
| FCS deployment profile | `public_repo` | `private_repo` |
| Tapis preparation input | `public_model_dir` | `private_model_dir` |
| Tapis job environment | `PUB_MODEL_HOST` | `PRI_MODEL_HOST` |

These are interface mappings, not additional storage locations. For a
site-configured job, populate them from the two canonical repository paths.


## FlexServ model ID

The only accepted canonical format MUST be:

```text
<SOURCE>:<author>/<model>[@<revision>][:<artifact-selector>]
```

`SOURCE` is `HF`, `FLEX:PRI`, or `FLEX:PUB`. Author and model are required;
revision and artifact selector are optional. Preserve capitalization. An
omitted revision and explicit `@main` remain distinct identities.

The selector identifies an exact file, a recursive directory, or a glob rooted
at the model repository snapshot. Without a selector, the ID selects the
snapshot. The full ID is used for deployment and routing; repository inventory
and storage remain keyed by `author/model[@revision]` without the selector.

```text
HF:Qwen/Qwen3-8B
FLEX:PRI:Qwen/Qwen3-8B@main
FLEX:PUB:unsloth/Llama-3.1-8B-Instruct-GGUF@main:**/*Q4_K_M*.gguf
```

The parser MUST match the case-sensitive complete source prefix first
(`FLEX:PRI:`, `FLEX:PUB:`, or `HF:`),
then split the remainder at the first `:` for the selector, and split the
repository portion at `@` for the revision. Colons are reserved delimiters and
cannot occur within author, model, revision, or selector values. The selector
follows the revision when provided. Implementations MUST reject empty required
components, an empty explicit revision or selector, additional colons, control
characters, backslashes, and absolute or traversal paths. Author and model each
contain only letters, digits, `_`, `.`, or `-`, and cannot be `.` or `..`.
Revision names may contain `/`, such as `refs/pr/12`; each segment must be
nonempty and cannot be `.` or `..`.

| Input | Required behavior |
| --- | --- |
| `FLEX:PRI:org/model@main:weights/model.gguf` | Accept; select the file within the private `@main` repository revision |
| `FLEX:PUB:org/model:weights/**` | Accept; select the directory recursively within the public repository |
| `HF:org/model::weights/model.gguf` | Reject the old separator; do not silently normalize it |
| `HF:org/model:` | Reject an empty selector |
| `FLEX:PRI:org/model:../model.gguf` | Reject path traversal |

Bare `author/model[@revision][:selector]` is allowed only by a download input
that explicitly declares `src: "HF"`; normalize it to an `HF:` ID before model
resolution. It is not a canonical deployment ID.

This changes the previous `::` selector separator to `:`. Gateway and FCS
parser updates are pending; the former `::` spelling is invalid under this
target contract. The historical `model:variant@revision` syntax remains
superseded. All other selector semantics and validation rules follow the
[reviewed identity spec, section 4](../../FlexServ_harness/spec/flexserv_identity_backend_model_api_ui_codex_reviewed.md#4-canonical-flexserv-model-id).

## Model ID to directory mapping

Choose the root strictly from the source. `FLEX:PRI` MUST use
`private_model_repo_path`; `FLEX:PUB` MUST use `public_model_repo_path`. A missing
model in the selected pool MUST NOT fall back to the other pool. `HF` identifies
an upstream source; managed downloads materialize into the private pool and
return the corresponding `FLEX:PRI` ID, preserving revision and selector.

After parsing the ID, derive the model directory and adjacent metadata sidecar:

```text
directory_name = escape(author) + "--" + escape(model)
if revision is present:
    directory_name += "---" + escape_revision(revision)

model_directory = repository_root / directory_name
metadata_file   = repository_root / (directory_name + ".json")
```

Use uppercase percent encoding of UTF-8 bytes. Keep ASCII letters, digits,
`_`, `.`, and `-` unchanged, except that every hyphen belonging to a run of two
or more hyphens in author or model MUST be encoded as `%2D` to protect the `--`
delimiter. Encode other bytes, including `/` as `%2F` and `%` as `%25`.
Revision hyphens can remain literal after the `---` separator. This encoding is
for filesystem names only; preserve the original values in IDs and metadata.
Rebuilding an index MUST read identity from metadata, not infer it by decoding
a directory name.

In the following examples, `PRI` and `PUB` stand for the resolved private and
public repository roots:

| Model ID | Model directory | Selected content |
| --- | --- | --- |
| `FLEX:PRI:Qwen/Qwen3-8B` | `PRI/Qwen--Qwen3-8B/` | Snapshot |
| `FLEX:PRI:Qwen/Qwen3-8B@main` | `PRI/Qwen--Qwen3-8B---main/` | Snapshot |
| `FLEX:PUB:org/model@refs/pr/12` | `PUB/org--model---refs%2Fpr%2F12/` | Snapshot |
| `FLEX:PRI:org/model@main:weights/model.gguf` | `PRI/org--model---main/` | `weights/model.gguf` within that directory |
| `FLEX:PUB:org/model@main:weights/**` | `PUB/org--model---main/` | All regular files under `weights/` |
| `FLEX:PRI:org/model@main:**/*.gguf` | `PRI/org--model---main/` | Matching regular files, sorted by relative path |
| `FLEX:PRI:org/my--model` | `PRI/org--my%2D%2Dmodel/` | Snapshot |

The selector MUST NOT enter the model directory name, metadata filename, or
index key. Multiple selectors for the same repository revision share the same
directory and sidecar; preserve upstream relative file paths within it. A glob
is a selection expression, never a literal filesystem path. Canonicalized
directories and selected files MUST stay within the configured repository root.

The private and public indexes use source-free `author/model[@revision]` keys.
Both `.flexserv_model_index_pri.json` and `.flexserv_model_index_pub.json` live
under the private repository root; the public index refers to public content.
Omitted revision and `@main` remain separate entries and directories even if
they currently resolve to the same commit. Store that commit as
`resolved_revision` without rewriting the requested identity.

## Model discovery and management UI

This section consolidates the existing
[Model Catalog requirements](../../FlexServ/spec/Architecture.md#model-catalog)
and [repository inventory contract](../../FlexServ_harness/spec/flexserv_api/3_model.md).
Preserve the current Gateway UI's overall layout while applying the model ID
and artifact-selection rules in this document.

### Discovery categories and family coverage

The Gateway-owned
[catalog registry](../../FlexServ/flexserv/gateway/src/model/model_catalog_config.json)
is the source of task labels, variants, publisher identities, family prefixes,
candidate backends, and approved quantization providers. The browser MUST read
the taxonomy from `GET /v1/flexserv/model-catalog/taxonomy` rather than maintain
a separate policy list. Keep these five top-level tabs in this order:

| Tab | Choices |
| --- | --- |
| LLM / VLM | Text Generation, Image → Text, Any → Any |
| Pooling | Embeddings (text/image), Classification (text), Rerank / Scoring (text) |
| Audio Recognition | ASR, Realtime ASR |
| Audio Generation | Text to Audio, Text to Speech |
| YOLO | Object Detection, Segmentation, OBB, Pose, Classification |

The existing registry provides the following initial discovery coverage.
These are publisher/family grouping labels, not a guarantee that every model
or task in the family runs on every backend. They are not an exhaustive
checkpoint allowlist; exact results come from provider discovery and validation.

| Publisher namespace | Registered family prefixes or grouping |
| --- | --- |
| `Qwen` | Qwen2, Qwen2.5, Qwen3 |
| `meta-llama` | Llama-2, Llama-3, Llama-3.1, Llama-3.2, Llama-3.3, Llama-4 |
| `meta-models` | Muse-Glimmer |
| `google` | Gemma, Gemma-2, Gemma-3, T5, FLAN-T5 |
| `mistralai` | Mistral, Mixtral, Ministral, Codestral, Pixtral |
| `microsoft` | Phi, Florence |
| `deepseek-ai` | DeepSeek |
| `nvidia` | Nemotron, NVLM |
| `ibm-granite` | Granite |
| `sentence-transformers` | Publisher grouping; no fixed family prefixes |
| `BAAI` | BGE |
| `jinaai` | Jina |
| `openai` | Whisper |
| `facebook` | Wav2Vec, HuBERT, MusicGen |
| `suno` | Bark |
| `coqui` | XTTS |
| `Ultralytics` | YOLO; show YOLO26, YOLO11, and YOLOv8 when matching artifacts exist |

This table summarizes the checked-in registry, not live upstream availability.
Future additions MUST update the registry and its validation coverage. Family
labels organize browsing only; they MUST NOT replace the exact model ID,
repository name, or artifact task classification.

### Discovery results and selection

`GET /v1/flexserv/model-catalog/models` performs bounded server-side Hugging
Face discovery for the selected task and variant. Require positive official
evidence from the trusted publisher registry plus provider metadata or
validated artifacts. A familiar name alone is insufficient. Show truthful
empty, unavailable, and error states instead of inserting demonstration models
into production results.

Keep family search, server pagination, stable sorting, and filters for model
size, license, gated access, publisher, and candidate backend. Family search
narrows discovery; it is not an arbitrary download destination. Present
families expanded by default, with checkpoint details accessible in the Models
workspace's single scroll surface. Preserve the adjustable divider above
Downloaded models without adding a nested catalog scroller.

Each result MUST identify the exact repository and, when applicable, artifact.
Show publisher, task, model size/parameters when known, download/like counts,
license, update date, gated status, local download state, and backend/API
compatibility status. Repository storage size and selected download size MUST
be labeled separately. Use reported byte counts; never infer them from parameter
counts or display unknown values as zero.

A catalog match means discoverable, not deployment-validated. Candidate
backends and APIs MUST retain their validation status and reason. Downloading
weights does not by itself establish runtime compatibility. Quantization
discovery MUST be tied to the exact selected source checkpoint, verify the
declared base-model relationship, and use the registry's approved providers
(currently `unsloth`). A `.gguf` extension alone is insufficient evidence of
compatibility; multi-artifact repositories require an explicit artifact choice.

### YOLO checkpoint selection

For official Hugging Face YOLO repositories, use `Ultralytics` as author and
the exact repository name, such as `YOLO26`, `YOLO11`, or `YOLOv8`, as model.
List the repository's actual `.pt` files and classify each checkpoint by task.
Do not classify an entire family repository as detection merely because its
name lacks a task suffix, or exclude its artifacts solely because its
repository-level pipeline tag names a different task.

Within the selected task, group available files by family and show size
variants such as `n`, `s`, `m`, `l`, and `x`. Use verified file listings and
task evidence; do not synthesize missing filenames. Filename suffixes provide
the standard task cues:

| Task | Example checkpoint within `Ultralytics/YOLO26` |
| --- | --- |
| Object Detection | `yolo26n.pt` |
| Segmentation | `yolo26n-seg.pt` |
| OBB | `yolo26n-obb.pt` |
| Pose | `yolo26n-pose.pt` |
| Classification | `yolo26n-cls.pt` |

Availability MUST be checked at the selected revision. Do not assume all five
tasks or all sizes exist in every family repository. Show unavailable task/size
combinations clearly. Each checkpoint row uses its exact filename as selector,
shows its own file size and download state, and downloads that selection:

```text
Source: HF:Ultralytics/YOLO26@main:yolo26n-seg.pt
Local:  FLEX:PRI:Ultralytics/YOLO26@main:yolo26n-seg.pt
File:   <private_repo>/Ultralytics--YOLO26---main/yolo26n-seg.pt
```

The UI MUST use the single-colon selector format. This example explicitly
selects `@main`; the UI must preserve an omitted revision when none was chosen.

### Downloads and local inventory

Discovery is read-only. An explicit download selection goes through the
approved asynchronous FCS model-transfer workflow, with the exact source ID,
selected artifacts, and resolved private destination visible to the user.
Enable download controls only when that workflow is available. Show queued,
downloading, validating, ready, failed, and cancelled states from operation
data; browser polling alone cannot cancel a transfer. Check space, duplicates,
integrity, and required artifact structure before reporting ready. Report
requested-backend compatibility separately and identify failures with the
repository, artifact, reason, and useful next action.

The Downloaded models view shows private and public inventories separately.
Each pool has one parent row per repository revision with artifact children,
not a separate repository row for every selector. A parent containing multiple
deployment targets requires a child selection before deployment. Show local
bytes without double-counting overlapping selections, per-artifact readiness,
and live backends attached to the exact deployed ID. Downloading one YOLO
checkpoint MUST NOT mark all checkpoints in that repository as downloaded.
Repository copy/delete acts on the parent; artifact copy/delete acts on the
selected owned content while preserving files shared with other selections.
Public publication and deletion remain subject to site permissions.

## Required follow-up agent task

Implement this contract across Gateway, FCS, and model-management callers.
This task MUST:

1. Enforce the single-colon selector grammar in parsing, validation,
   serialization, API examples, and UI-generated IDs. Reject `::` at runtime;
   handle existing persisted IDs through an explicit migration that preserves
   repository, revision, and selector meaning.
2. Use the same directory encoding and pool selection everywhere. Cover the
   valid and invalid examples above with parser and directory-mapping tests,
   including omitted revision versus `@main`, escaped revisions, delimiter
   collisions, and selectors sharing one model directory.
3. Reconcile the previous harness documentation, including
   [the consolidated identity spec](../../FlexServ_harness/spec/flexserv_identity_backend_model_api_ui_codex_reviewed.md),
   [identity conventions](../../FlexServ_harness/spec/flexserv_api/0_identity.md),
   and [repository management](../../FlexServ_harness/spec/flexserv_api/3_model.md),
   plus their current examples and references. Earlier edits are only an
   initial amendment; audit remaining documentation for conflicting grammar
   and directory layouts. Keep superseded designs clearly marked historical.
4. Update runtime/API documentation and remove pending-implementation notices
   only after the implementation and integration checks pass.
5. Reconcile the discovery and management UI with this section, including
   registry-driven family coverage, file-level YOLO task discovery, exact
   selector IDs, and per-artifact download state. Update the older
   [Architecture Model Catalog section](../../FlexServ/spec/Architecture.md#model-catalog)
   and harness UI documentation alongside the implementation. Cover mixed-task
   repositories and missing task/size combinations with representative fixtures.

For the selector separator and directory mapping, this document is the target
contract if older documentation conflicts. Updating prose alone does not
complete the runtime enforcement task.
