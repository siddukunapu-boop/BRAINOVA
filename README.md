# AetherLearn AI — Intelligent Learning Studio & Career Roadmap System

AetherLearn AI is a full-stack AI-powered learning platform featuring:
- **Nine AI Studio Tools**:
  1. **Audio Overview** (Two-host podcast script + genuine playable `.wav` speech synthesis via Cloud TTS or Windows `.NET System.Speech`)
  2. **Slide Deck** (Interactive presentation viewer, slide reordering, inline editing, and printable export)
  3. **Video Overview** (Source-grounded lesson script, scene storyboard, captions, and interactive narrated scene preview)
  4. **Mind Map** (Interactive SVG knowledge graph with pan, zoom, collapsible branches, and node inspector)
  5. **Study Guide / Report** (Comprehensive long-form guide with TOC, definitions, code examples, comparison tables, and edit-overwrite protection)
  6. **Flashcards** (Active-recall flip cards with spaced repetition tracking: `New`, `Learning`, `Needs Review`, `Known`)
  7. **Quiz Generator** (Configurable source-grounded assessments including 20-MCQ examinations)
  8. **Infographic** (Visual educational summary poster with KPI callouts, process flow, and comparison matrix)
  9. **Data Table** (Structured extraction with column sorting, search, and CSV export)
- **Conversational AI Roadmap Agent**: Role presets, custom learning goals, interactive preview editor, and background resource provisioning.
- **Topic Learning Workspace**:
  - **Section A — Video Tutorial**: Curated verified CS/engineering lectures + custom YouTube URL manager.
  - **Section B — Reading Material & Personal Notes**: Structured study guide + independent multi-note editor.
  - **Section C — 20-MCQ Examination Engine**: Exam Instructions Portal, 20 validated 4-option MCQs, server-side grading, detailed answer review, and persistent Practice Attempts History.
- **Source Library & Grounded RAG**: Upload `.pdf`, `.md`, `.txt`, `.csv`, `.json`, `.py`, `.js`, `.ts`, `.html` documents, extract and index chunks, and ask source-grounded questions with navigable page/section citations.

## Running the Platform

```powershell
powershell -ExecutionPolicy Bypass -File .\start_platform.ps1
```

Then open `http://127.0.0.1:8000` in your browser.

