# Brainstorm: Remove `.md` Frontmatter Dependency (Consolidate Metadata into the Manifest)

> **Status:** BRAINSTORM STARTING POINT — not an approved design.
> Seeded from the 2026-07-23 investigation during the sitemap-llm / `--update`
> work. Run `superpowers:brainstorming` to turn this into an approved spec
> before any implementation. No code has been written.

## Origin

While evaluating whether the scraper could fetch site-served `.md`
(`/sitemap-llm` targets) instead of crawling and converting HTML, we traced
what the converted-markdown **frontmatter** is actually used for. The finding
raised a separate question worth its own stream: *can we drop the frontmatter
dependency entirely?*

## The idea

The YAML frontmatter block that `scraper.py::_build_frontmatter` prepends to
every converted `.md` file (`title`, `url`, `hostname`, `sitename`, `date`,
`http_status`) looks like a holdover. Investigate removing the code's
dependency on it and letting `manifest.json` be the single source of ingest
metadata.

## What the code actually does today (grounded, 2026-07-23)

Two repos:
- **scrape-website** — `_build_frontmatter` writes the YAML block; `state.db`
  `visited` table is the metadata store; `export_manifest` emits
  `manifest.json`.
- **apo-mcp-server** — `ingest.py` consumes the `.md` files + `manifest.json`.

Key facts verified in code:

1. **Frontmatter is stripped before upload.** `ingest.py:348` sets
   `content = post.content` (body only, YAML removed) and uploads that at
   line 363. **The vector store never receives the frontmatter** — it is not
   part of the search corpus. Removing it has zero effect on search.
   *(Open: confirm the binary-document path at `ingest.py:385+` behaves the
   same; this brainstorm only verified the primary `.md` path.)*

2. **Frontmatter is read in exactly three spots in `ingest.py`:**
   | Field | Line | Role | Also in manifest / state.db? |
   |---|---|---|---|
   | `url` | 330 | fallback for `source_url`/`origin_url` | **yes** (`source_url`) |
   | `title` | 350 | fallback for manifest title | **yes** (`title`) |
   | `http_status` | 342-344 | **gate: skip pages where status != 200** | **NO** |

3. **`http_status` is the only real dependency.** It lives *only* in the
   frontmatter. `export_manifest` selects
   `filename, url, hostname, title, found_on, file_type, content_hash` — no
   status column in `visited`, none in `manifest.json`.

## Why this is the "one field" problem

`url` and `title` are already authoritative in the manifest; the frontmatter
reads are pure `entry.get(...) or post.metadata.get(...)` fallbacks. Delete
those and nothing breaks post-scrape (manifest is always populated).

The `http_status != 200` skip gate is the blocker. To remove frontmatter you
must relocate that signal first.

## Options for the `http_status` gate

- **Option A — Relocate to the manifest (matches existing pattern).**
  Add a `status` column to `visited`; include it in `export_manifest` and the
  entry dict; change the ingest gate to `entry.get("http_status")`. Bounded:
  one column + one Alembic-free SQLite migration in the scraper, plus the
  ingest edit. Keeps ingest-time filtering ability.
- **Option B — Filter at the scraper.** Only write `.md` for 200 responses,
  so ingest never needs the field and the gate is deleted. Simpler; loses the
  ability to decide at ingest time and changes what lands on disk.

## Convergence with the sitemap-llm work (why this matters now)

Site-served `.md` (from `/sitemap-llm`) has **no frontmatter either**. The
same relocation (Option A) that drops the frontmatter dependency *also* makes
the served `.md` ingestible as-is, with a `manifest.json` built directly from
the sitemap-llm (`- [title](url.md)` gives both `title` and `url`). One change
unlocks both paths. This is a strong reason to design them with awareness of
each other, even if shipped separately.

## Scope / boundaries

- **Separate from Task 16** (sitemap discovery) and from `--update`. Do not
  fold in.
- **Spans two repos** (scraper emits, ingest consumes) — coordinate the change
  so the scraper writes the new manifest field before ingest starts reading it
  (backward-compatible: ingest keeps the frontmatter fallback until all live
  manifests carry `http_status`).

## Open questions for the real brainstorm

1. Option A vs B — is ingest-time status filtering worth keeping?
2. Migration/rollout order across the two repos and the S3 manifests already
   in QA/prod. Can ingest read the field from manifest while old manifests
   lack it (grace period with frontmatter fallback retained)?
3. Does the binary-document ingest path (`_ingest_documents`, `ingest.py:385+`)
   read frontmatter too? Confirm before claiming full removal.
4. Is `date`/`sitename` in the frontmatter used by anything at all (Splunk,
   debugging, manual inspection)? If purely cosmetic, they go with the block.
5. Do we keep emitting frontmatter for human/debug readability even after the
   code stops depending on it, or delete it outright?
