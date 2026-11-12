# Research Hub · 研究進度中樞

<p align="center"><b>A local thesis-progress manager.</b><br>
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

**Navigation**: the menu button (top left) lists the sections; one section is shown at a time and the top bar lists only that section's sub-options. Settings and language live at the bottom of the menu; press `m` to open it.

| Area | What it does |
|---|---|
| **Pipeline nodes** | The dashboard shows the whole study as a row of nodes (01 → 10): topic, literature review, research questions, framework & variables, methodology, data collection, analysis, results, writing, defense & publication. Each node shows a progress ring, status and task count. Stages can be added, renamed, re-ordered and removed to match your department's process chart. |
| **Stage workspace** | Click a node to expand it: status, progress, start/due dates with overdue warnings, autosaved notes, tasks, file uploads (drag & drop into the workspace folder), linked resources, and a stage module (literature, RQs, variables & model, Python, writing & citations). |
| **Research core** | A dedicated board for RQs, variables (X independent, Y dependent, M mediator, Z moderator, C control) and papers. Every variable links to its papers with a relation (supports, contradicts, mixed, defines, measure source, mentions); variables without literature support are flagged. |
| **Variable × paper matrix** | See at a glance which papers back which variable; click a cell to cycle the relation. |
| **Research model** | Draws the X → M → Y model with moderators and controls from variable roles. |
| **Literature** | OpenAlex search, BibTeX/RIS import & export (duplicates skipped by DOI, cite key or title), reading status, rating, tags, open local PDF. |
| **Integration hub** | One-click search across databases (Google Scholar, Semantic Scholar, arXiv, PubMed, Scopus, Web of Science, Airiti, NDLTD — add your own with `{q}` in the URL); scan and import local reference folders; MCP tool registry; Python code folder and script runs; all uploaded files. |
| **Live updates + confirmation** | When an agent finishes a task, a new file appears in a watched folder, or literature tracking finds related new papers, the change waits in the **Inbox**. You approve it (optionally only some of its changes) before anything is written. The dashboard refreshes live over Server-Sent Events. |
| **Activity & backup** | Every change records who made it (you, an agent, the folder watcher) and when; export a full JSON backup or BibTeX. |

## Upload & progress check-in (v1.1)

Every upload opens an **Upload & progress check-in** dialog (also available from the hero button and each stage's "Report progress"):

1. **Auto-archive**: the stage is picked from the file and folder names (`analysis_regression.py` goes to Data Analysis, `文獻探討_v2.docx` to Literature Review). Add your own `keyword => stage key` rules in Settings; they take priority.
2. **Where are you? (required)**: every upload records what you finished, what is blocking you and what comes next, in the stage's **Progress log**.
3. **Progress**: ticking finished tasks recalculates progress from the checklist (can be turned off), or set it with the slider.
4. **Completion goal**: the stage's target date and definition of done, plus the thesis deadline, shown as a countdown on the dashboard.
5. **Track related literature**: after saving, related new papers are searched in the background and land in the Inbox for approval.

**Automatic tracking**: stages with start and due dates compare actual progress with the progress expected by today and show "N% behind" or "N% ahead" on the node and in the stage panel.

### Literature sources (free; daily quotas reset at local midnight)

| Source | How | Key needed |
|---|---|---|
| OpenAlex | free official API | no |
| Wiley | free Crossref API filtered to Wiley publications | no |
| Semantic Scholar | free official API | no |
| Web of Science | Clarivate Starter API | yes (free plan on the Clarivate developer portal, or ask your library) |
| Google Scholar | no official API; opens a search in a new tab (no scraping, which breaks its terms) | — |

### AI assistant (optional)

Choose Google Gemini (free tier), Groq, OpenRouter free models, a local Ollama, or any OpenAI-compatible service in Settings. It is called only when you press "Read with AI": it reads your note and suggests progress, finished tasks and search keywords, which you confirm before saving. Keys stay on this computer and are never sent back to the page.

### Daily usage

**Today's usage** in the Integration hub shows requests and tokens per source and for the AI, the limits, and the time until reset. Limits are set in Settings; when one is reached, that source stops for the day and resets at local midnight.

## 5C research story and 5C reading notes

Based on Lange & Pfarrer (2017, *AMR*), "Sense and structure":

- **Story board** (first tab of the Research core): common ground → complication → concern → course of action → contribution. One sentence each (We know that… / Yet… / This matters because… / We develop… / This changes…), with guiding questions, notes and the papers that support each block. The five sentences form the five-sentence pitch (an abstract draft of about 200 words) and can go into the slides. A length guide is included (abstract ≈200 words, introduction 3–4 pages, second section 5–7, main body 10–15, discussion 3–5 — guidelines, not rules).
- **5C reading notes** for every paper: the five questions, the complication type (problem / puzzle / twist) and which block of your story the paper supports. The literature list shows 5C completeness; **5C compare** lines papers up side by side.
- Agents can propose story edits over MCP (you confirm).

## Title strength check

At the top of the 5C story tab, the title is rated Easy / Medium / Hard like a password meter: word segmentation (Chinese lexicon + bigrams), automatic Chinese → English translation (AI → MyMemory → built-in glossary), overlap with published work in Taiwan and abroad via OpenAlex (≥70% crowded, 50–70% done before, 30–50% partial, <30% rare), and a story score — why this topic, what it enables, who it helps. Without the online comparison the level is capped at Medium. The online check sends the title to OpenAlex and the translator; untick it to stay offline.

## Research design check

The Design check tab follows Bono & McNamara (2011): five pre-submission design questions, the conditions for a causal claim, and automatic warnings from each variable's measurement source, wave and the three control-variable judgments.

## Exam practice

A section of its own. **Questions from an uploaded paper**: drop a PDF, .docx or .txt; the hub detects the title, methods, labelled hypotheses and key terms and drafts essay questions with outlines — only the ones you tick are saved (tick AI for questions written from the text). PDFs are read best with Poppler's `pdftotext`; the built-in fallback only handles simple Latin-text PDFs.

Folders for questions and readings, question prediction (rules or AI), question analysis with an answer outline, reading analysis from 5C notes, and timed essay practice graded by outline coverage (plus AI comments when available). Every hand-in is kept, so each question shows its score history; Weak spots ranks folders by average latest score; a spaced-review schedule (1→3→7→14→30→60 days, back to tomorrow after a weak answer) drives the Review today list for questions and papers. A 16-question research-methods starter bank (in Chinese, original wording) is included.

## Voice podcast

Turn the story, reading notes or an exam analysis into a script, choose voice, tone, pitch and speed, preview in the browser and export WAV with the computer's built-in voices (macOS `say`, Windows speech, Linux `espeak-ng`). Nothing is uploaded.

## Word thesis export

Export Word builds a .docx draft: cover, acknowledgements, abstract, contents and lists (pages i, ii, iii), chapters 1–3 (pages from 1), APA references. Body text uses a style named 論文設定0; fonts, size, line spacing and margins are configurable. In Word, right-click the contents and choose Update Field.

## Research model from your own writing

In **Research core → Research model**, choose **From my writing** and paste or upload your draft (`.docx`, `.txt`, `.md`, `.tex`):

- **Rule-based reading (free, offline)** finds hypothesis sentences in Chinese or English, such as "H1: Perceived usefulness positively affects behavioral intention", "Trust moderates the relationship between X and Y" or "Attitude mediates …", and works out X, Y, mediators and moderators.
- **AI reading (optional)** is more accurate when the draft has no explicit hypothesis sentences; it counts toward today's quota.
- **Review before applying**: a preview diagram, the variables (symbol, name and role are editable; names that match existing variables reuse them) and every path can be unticked; nothing is saved until **Apply to research core**.
- **The research model** is drawn from the hypothesis paths: labels and direction on each line, negative paths dashed red, moderators pointing at the path they moderate, and paths that skip a column routed above the boxes. Paths can also be added by hand.
- **Download SVG** gives a clean vector figure (no paper counts or RQ markers) for the thesis or slides.

## PowerPoint export

**Make slides** on the dashboard (or in the Writing stage) opens the **slide design instructions** window:

1. **Design instructions**: describe the deck in a sentence, e.g. "progress report for my advisor, 10 slides, navy, serif titles, Microsoft JhengHei body, no literature". **Apply instructions** sets colours, fonts, purpose, slide count, language, size and which slides to include or drop. Optionally let the AI write each slide's key message and speaker notes (counts toward today's quota); otherwise they are generated from your data.
2. **Purpose**: advisor progress report, thesis defense or conference talk, each with default slides.
3. **Slides**: cover, research story 5C, progress overview, research questions, research model, hypotheses, variables table, literature, recent progress, next steps, closing Q&A.
4. **Look & fonts**: five colour themes; separate heading and body fonts — Noto Serif TC (open-source Ming/Song), PMingLiU (Windows Ming), Microsoft JhengHei, Noto Sans TC, DFKai-SB, PingFang TC. Fonts are set on every text run and in the deck theme, so new text typed in PowerPoint uses them too. Open-source fonts must be installed on the computer that shows the deck (links in the window).
5. **Export PowerPoint**: a `.pptx` (16:9 or 4:3) whose research model is drawn with native, editable PowerPoint shapes; optionally filed under the Defense stage.

The deck is built in the browser with the bundled PptxGenJS (MIT), offline; only the optional AI writing step calls your AI service.

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

## Python code

Point Settings at your analysis project; the hub lists its `.py` / `.ipynb` files. With "Allow running .py scripts" enabled (off by default) you can run a script and read its output (current Python interpreter, working directory = code folder, with a timeout).

## Security and data

- Listens on `127.0.0.1` and checks the Host header (DNS rebinding). There is no login — never expose it to the Internet.
- Every dashboard request carries a per-process page token, so other websites cannot write.
- Agents use a separate, rotatable agent token that can only read and propose.
- Local files are read only inside configured folders (reference folders, code folder) and the uploads folder.
- Workspace contents: `hub.sqlite3` (all structured data) and `uploads/` (files, one folder per stage).

## System maps

Interactive diagrams generated and validated with [archify](https://github.com/tt-a1i/archify) — open "System map" in the dashboard footer or `/static/diagrams/index.html`: `architecture.html` and `confirmation-gate.html`. Sources are in `.archify/`.

## Design

The icon is a silhouette of a squirrel holding a nut (`research_hub/web/favicon.svg`, `squirrel.svg`). The visual design follows the [ui-ux-pro-max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) design-system recommendation: Minimalism & Swiss style, IBM Plex Sans + JetBrains Mono (Noto Sans TC for Chinese), white-first, hairline borders, a single ink-blue accent, mono micro-labels and a dotted grid; meets its pre-delivery checklist (SVG icons, 4.5:1 contrast, visible focus, keyboard support, `prefers-reduced-motion`, responsive 375–1440px).

## Development

```bash
python -m unittest discover tests
```
