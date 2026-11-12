# Research Hub · 研究進度中樞

<p align="center"><b>A local thesis-progress manager built around PaperRead.</b><br>
One line of nodes from topic to publication; research questions, variables, papers, databases, local folders, MCP agents and Python analysis code in one place.</p>

<p align="center"><a href="README.md">繁體中文</a> · <b>English</b></p>

## Quick start

Python 3.10+ only — **no packages to install** (standard library only).

```bash
./start.sh            # macOS / Linux, from the repository root
start.cmd             # Windows
./start.sh --demo     # explore with sample data (a TAM study)
./start.sh --lang en  # new workspace with English tasks and UI (default tasks are written in the workspace's starting language; edit them freely)
```

Open <http://127.0.0.1:8770/>. The root `/` is the dashboard; `/zh/` and `/en/` switch language (also from the top bar).
**Run it on your own computer**: everything happens on `127.0.0.1`, so data never leaves your computer and no Internet traffic is used, and no web fonts are downloaded. Only OpenAlex searches and the external database links go online.

Data lives in `~/ResearchHub` by default (`--data <folder>` or `RESEARCH_HUB_HOME`); change the port with `--port` or `RESEARCH_HUB_PORT`.

## Features

| Area | What it does |
|---|---|
| **Pipeline nodes** | The dashboard shows the whole study as a row of nodes (01 → 10): topic, literature review, research questions, framework & variables, methodology, data collection, analysis, results, writing, defense & publication. Each node shows a progress ring, status and task count. Stages can be added, renamed, re-ordered and removed to match your department's process chart. |
| **Stage workspace** | Click a node to expand it: status, progress, start/due dates with overdue warnings, autosaved notes, tasks, file uploads (drag & drop into the workspace folder), linked resources, and a stage module (literature, RQs, variables & model, Python, writing & citations). |
| **Research core** | A dedicated board for RQs, variables (X independent, Y dependent, M mediator, Z moderator, C control) and papers. Every variable links to its papers with a relation (supports, contradicts, mixed, defines, measure source, mentions); variables without literature support are flagged. |
| **Variable × paper matrix** | See at a glance which papers back which variable; click a cell to cycle the relation. |
| **Research model** | Draws the X → M → Y model with moderators and controls from variable roles. |
| **Literature** | OpenAlex search, BibTeX/RIS import & export (duplicates skipped by DOI, cite key or title), reading status, rating, tags, open local PDF, open in PaperRead. |
| **Integration hub** | One-click search across databases (Google Scholar, Semantic Scholar, arXiv, PubMed, Scopus, Web of Science, Airiti, NDLTD — add your own with `{q}` in the URL); scan and import local reference folders; sync a PaperRead library; MCP tool registry; Python code folder and script runs; all uploaded files. |
| **Live updates + confirmation** | When an agent finishes a task, a new file appears in a watched folder, or a PaperRead sync finds new papers or variables, the change waits in the **Inbox**. You approve it (optionally only some of its changes) before anything is written. The dashboard refreshes live over Server-Sent Events. |
| **Activity & backup** | Every change records who made it (you, an agent, the folder watcher) and when; export a full JSON backup or BibTeX. |

## Agents and MCP

Research Hub ships an MCP server (stdio, standard library). Get a ready-made command, including the agent token, from **Integration hub → MCP tools & agents → Show command**. For Claude Code:

```bash
claude mcp add research-hub -- python -m research_hub mcp --url http://127.0.0.1:8770 --token <agent token>
```

Tools: `get_overview`, `get_schema`, `list_items`, `propose_changes`, `report_stage_progress`, `propose_papers`, `check_proposals`. **Every write tool only creates a proposal.** Pair it with your own literature-search MCP server: the agent searches there and sends findings to the inbox with `propose_papers`, linked to variables or RQs.

Without MCP, use the CLI or HTTP:

```bash
python -m research_hub propose changes.json --token <agent token>
curl -X POST http://127.0.0.1:8770/api/agent/proposals -H "Authorization: Bearer <agent token>" \
     -H "Content-Type: application/json" -d '{"title":"Literature review done","ops":[{"op":"update","entity":"stage","match":{"key":"literature"},"data":{"status":"review","progress":100}}]}'
```

When you untick a "create" while reviewing, changes that refer to it are unticked too; a change whose target you edited after it was proposed is flagged as a conflict. Agent notes use `append`, added at approval time, so they never overwrite newer text.

Operations: `create` / `update` (optionally `"append": {"notes": "…"}`) / `delete` on `stage`, `task`, `rq`, `variable`, `paper`, `resource`; `link` / `unlink` for `rq_variable`, `rq_paper`, `variable_paper`. Within one batch, `"ref": "p1"` names a new object and `"$p1"` refers to it.

## PaperRead integration

- **Links**: set the PaperRead URL (default `http://127.0.0.1:8765`); papers synced from PaperRead get an "Open in PaperRead" button.
- **Sync**: set the PaperRead library folder (default `~/PaperRead/library`). "Sync library" reads each paper's `paper.json` / `item.json` read-only and turns new papers, reading-status changes and the variables PaperRead extracted (independent, dependent, mediator, moderator, control) into one proposal, with variable–paper links.
- Re-syncing never duplicates: a new sync replaces an unconfirmed older one, existing papers and the relations you set are kept, and unreadable folders are skipped and listed.
- Research Hub never writes to PaperRead's files.

## Python code

Point Settings at your analysis project; the hub lists its `.py` / `.ipynb` files. With "Allow running .py scripts" enabled (off by default) you can run a script and read its output (current Python interpreter, working directory = code folder, with a timeout).

## Security and data

- Listens on `127.0.0.1` and checks the Host header (DNS rebinding). There is no login — never expose it to the Internet.
- Every dashboard request carries a per-process page token, so other websites cannot write.
- Agents use a separate, rotatable agent token that can only read and propose.
- Local files are read only inside configured folders (reference folders, code folder, PaperRead library) and the uploads folder.
- Workspace contents: `hub.sqlite3` (all structured data) and `uploads/` (files, one folder per stage).

## System maps

Interactive diagrams generated and validated with [archify](https://github.com/tt-a1i/archify) — open "System map" in the dashboard footer or `/static/diagrams/index.html`: `architecture.html` and `confirmation-gate.html`. Sources are in `.archify/`.

## Design

Follows the [ui-ux-pro-max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) design-system recommendation: Minimalism & Swiss style, IBM Plex Sans + JetBrains Mono (Noto Sans TC for Chinese), white-first, hairline borders, a single ink-blue accent, mono micro-labels and a dotted grid; meets its pre-delivery checklist (SVG icons, 4.5:1 contrast, visible focus, keyboard support, `prefers-reduced-motion`, responsive 375–1440px).

## Development

```bash
python -m unittest discover tests
```
