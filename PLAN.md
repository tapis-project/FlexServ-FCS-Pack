# FlexServ 1.5 Alpha delivery

Approved on 2026-10-25. Ship only Gateway and Capability Server, one v1alpha2 Pack, and simple Slurm Bash entrypoints. Preserve unrelated files.

- [x] Verify remote branches and establish the official FCS checkout. Proof: remote SHA and clean tracked state.
- [ ] Remove embedded inference, rename FCS and integrate probe/job startup. Proof: Rust checks and real local job TLS/discovery after staging deletion.
- [x] Consolidate Packs in FlexServ-FCS-Pack. Proof: inventory, dependencies, visibility and runtime-generated poll approvals.
- [ ] Implement environment/install/site/launch/tunnel scripts. Proof: bash syntax and controlled lifecycle cases, without installing models or changing host services.
- [ ] Publish reusable dual-architecture CI and complete ZIP. Proof: Actions results, ELF ABI gates, exact inventory and checksums.
- [ ] Run Debug/Release dummy and Tapis fixture regression, review and record remaining site-only checks.

No GPU/HPC result may be inferred from fixtures. No restart recovery, PID adoption, live external Tapis resources or automatic model download.

## Verification checkpoint

Unified payload: 18 toolsets, 65 tools, 117 inventoried files. Packaging tests: 3 passed. ZIP bytes deterministic; original payload backup retained temporarily until final delivery. CI publication remains pending.
# Independent Pack releases (2026-10-26)

- [ ] Preserve the canonical catalog on feature/new_fcs and derive standalone
  tapis-workflow-pack.zip and vllm-pack.zip without duplicate source definitions.
- [ ] Publish both inventories and source metadata independently of Rust builds.
- [ ] Test deterministic packaging, full checksum coverage and dependency closure;
  verify Deployer can merge identical shared assets and rejects conflicts.
