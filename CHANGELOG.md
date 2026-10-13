# Changelog

All notable changes to the `compoid-mcp` package. Newest first.

## v0.1.7

- **MCP `instructions` fixed for OpenAI portal verification:** the server-level instructions block (delivered to every MCP client on connect) was rewritten as a fixed point of the portal scanner's whitespace normalization — no leading indentation, all lines start at column 0 — and kept under its ~1030-char storage budget (983 chars incl. trailing newline). The stored copy now byte-matches the live `initialize` response. All operational content preserved (auth via `X-Compoid-Repo-Key`, first-run guidance, search-before-create, create-verification canary, `Compoid_update_record` new-ID semantics, etiquette, web links). **No tool behavior change**

## v0.1.6

- **Hotfix — annotation correctness for `Compoid_update_community`:** the tool was declared `destructiveHint: false`, which per the MCP 2025-06-18 spec means "performs only additive updates" — but the tool performs a full-replacement PUT (`slug` changes break existing community URLs and `visibility: restricted` changes hide the community, both hard to reverse). It is now declared `destructiveHint: true` (also the spec default). **No behavior change** — all other tool annotations and all tool behavior are unchanged

## v0.1.5

- **Security — fail-closed per-request keys (fixes multi-tenant key bleed):** on the hosted service, a request without an API key could inherit the previous caller's key from shared process state (a keyless `Compoid_whoami` returned a borrowed identity). Keys are now reconciled back to the server's environment defaults on every request, so a keyless request can never carry a stale key — `Compoid_whoami` without a valid key now returns a clean 401
- **Bearer-token fallback:** when no `X-Compoid-Repo-Key` header is present, the `Authorization: Bearer` token is used as the repository key (hosts such as the OpenAI app portal inject the user's API key as Bearer); the explicit header still wins when both are present

## v0.1.4

- **MCP tool behavior annotations** (`readOnlyHint`, `destructiveHint`, `openWorldHint` per the MCP 2025-06-18 spec) on **all 14 tools**, so clients can see at a glance which calls are side-effect-free: searches/details/whoami/collections are `readOnly`; create/update/upload/download are state-changing but non-destructive; `Compoid_delete_record` is the single `destructive` tool (irreversible)

## v0.1.3

- **Research-domain categorization (`rdm:category`)**: the content-rating VLM now classifies each file's research domain from a 20-category vocabulary (e.g. `artificial-intelligence`, `physics`, `finance-fintech`) and stores it on the record as the `rdm:category` custom field; unknown or missing categories safely fall back to `general`
- **Category carry-over on updates**: `Compoid_update_record` preserves the record's existing `rdm:category` (off-vocabulary ids fall back to `general`)
- **Packaging hardening**: template paths now resolve relative to the installed package, so wheel installs work from any working directory

## v0.1.2

- **Resource-type vocabulary synced with the Compoid platform** (`resource_types_compoid.yaml`): added `event`, `crypto`, `forex`, `indices`, `equities`, `physicalobject`, `model`; legacy numeric dataset aliases (`dataset1`, `dataset3`, `dataset5`, `dataset254`, `dataset258`) removed. Search filters and `Compoid_create_record`/`Compoid_update_record` now accept the full 20-type platform set

## v0.1.1

- **Security:** removed debug header logging that wrote the full incoming headers (including the upload Bearer token) to a local file / stderr on every request
- **Agent-facing `instructions`:** the server now ships usage guidance with the MCP handshake, so connected agents learn the Compoid workflow (auth, search-before-create, provenance etiquette) automatically
- **README:** new setup section covering API keys and environment variables (remote vs. self-hosted)

## v0.1.0

- **Collections tools**: `Compoid_search_collections` (list/search a community's collection trees) and `Compoid_get_collection_records` (list the records in a collection)
- **`Compoid_delete_record`**: delete a published record (irreversible; creator or community owner only)
- **`subjects` parameter** on `Compoid_create_record` / `Compoid_update_record`: up to 5 subject display names from the Compoid subject vocabulary (https://www.compoid.com/subjects); "Artificial Intelligence" is always appended as a default
- **`creators` and `keywords` are now required** (non-empty lists) on `Compoid_create_record`
- **Stricter, more actionable errors**: failed create/update calls now include a `Hint:` explaining the invalid field (allowed enum values, community membership/permissions)
- **Updated resource-type vocabulary** used by search, create, and update: `analysis, image, video, audio, publication, document, software, project, dataset, presentation, workflow, tutorial, other`
- **Python 3.12+** required (was 3.11)
- **`COMPOID_AI_MODEL` default** is now `Qwen`
- **Published on PyPI** — `pip install compoid-mcp` (see Option 4)
