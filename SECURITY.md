# Security and data handling

**Review date:** 4 November 2026  
**Assessment:** Research prototype; not approved for sensitive or regulated data.

This review describes the current implementation and its operational limits. It does not constitute a penetration test, cryptographic audit, or production-readiness certification.

## Implemented controls

- The provider-neutral model input is an allowlist containing only bounded `working_context` and `current_user_message`. Audit metadata, omitted-event details, memory IDs, hashes, and diagnostic information are kept out of that model-input object.
- The optional Ollama adapter accepts only an HTTP loopback origin and refuses model names ending in `:cloud`. It does not send to a cloud URL or use an API token.
- Workspace-rooted artifact reads reject absolute paths, parent traversal, and paths that resolve outside the workspace. Checkpoint exports encode project/chat identifiers into filename components and use unique checkpoint IDs so repeated exports do not overwrite prior snapshots.
- AEL event rows, memory-event history, revision history, and outputs have SQLite triggers that reject ordinary update/delete operations through the runtime's database connection.
- Q-Batch event logs use append-only writes, per-event hashes, artifact hashes/sizes, and final event-stream checksums. These checks detect many accidental or unsynchronised modifications.

These are application-level safeguards, not a security boundary against a user or process with control of the machine, database file, or repository.

## Data persisted and where it goes

- The AEL SQLite ledger stores user events, assistant responses, project/chat identifiers, source references, and memory/revision history.
- Checkpoint Markdown/JSON exports and CLI response/audit files are ordinary filesystem files.
- The default AEL data directory is under the current user's home/profile directory (`~/.ael-runtime` or `%LOCALAPPDATA%\\AELRuntime`); `AEL_RUNTIME_HOME` can redirect it. The application relies on operating-system file permissions and does not add encryption or a separate application access-control layer.
- CT/Q-Batch experiment evidence can include raw model requests/responses, tool arguments/results, command stdout/stderr, workspace snapshots, generated files, and validation reports. Hashes provide integrity checks; they do not make this content private.

## Public GitHub artifact exposure

The `memoryprismv1/ael-runtime-accountability` repository is public. Its real-model workflow uploads an artifact named `ct-ab-audit-evidence` containing raw experiment logs and evidence. GitHub documents that Actions artifact endpoints are available to anyone with repository read access, and public resources can be accessed without authentication ([GitHub Actions artifacts API](https://docs.github.com/en/rest/actions/artifacts)).

Therefore:

- Treat the uploaded audit evidence as public, not private to experiment operators or assessors.
- A/B condition blinding is not a confidentiality control on this public repository: raw request/response traces can reveal the enabled condition.
- Do not put private prompts, personal data, customer data, credentials, confidential source code, or other sensitive material into these public experiment runs.
- The real-model pilot is manual-dispatch only. Do not start it with private inputs. A future blinded or sensitive-data pilot would require a private evidence destination or a repository with appropriately restricted access before execution.

## Important limits

- **No encryption at rest:** ledger databases, checkpoint exports, response files, and local audit files are plaintext unless the host operating system or storage layer encrypts them.
- **No built-in backup/restore or secure deletion:** the prototype does not provide a complete database backup/restore workflow, cryptographic key management, or secure erasure. Do not treat deleting a record or export as guaranteed erasure from backups or storage media.
- **Append-only is not tamper-proof:** SQLite triggers constrain normal runtime operations, but a database owner/administrator can alter the database file or schema. A hash chain can be recomputed by an actor who can rewrite the complete event stream and its hashes.
- **Loopback is not a sandbox:** the local Ollama process and downloaded model are part of the trusted computing base. Another local process, host compromise, or network forwarding can cross assumptions that the runtime does not enforce.
- **Generated code is not sandboxed by the tool interface:** the CT acceptance suite executes generated application code as the current runner user. The hosted workflow uses an ephemeral runner, but it is not a hardened OS sandbox.
- **Filesystem checks do not stop a hostile concurrent local process:** path resolution and hashing protect against ordinary traversal and changed-source mistakes; they do not provide race-free isolation against another process that can modify the same workspace.
- **Real inference remains unverified in this development environment:** AEL's Ollama adapter and interactive shell have mock-service tests, not a live local-model acceptance result.

## Operating rule

Use only non-sensitive test data with the current prototype. Before recommending use with sensitive or regulated content, separately assess and implement appropriate storage encryption, OS access controls, backup/restore, retention/deletion requirements, process isolation, and a private evidence destination. Those capabilities are not part of the current stabilisation baseline.
