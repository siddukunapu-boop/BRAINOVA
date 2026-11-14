import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

import { parseMermaidDiagram } from '../../src/lib/mermaidParser.ts';
import { parseMarkdownBlocks, isSafeHttpUrl } from '../../src/lib/mentorMarkdown.ts';

const ROOT = path.resolve(import.meta.dirname, '..', '..');

test('parseMermaidDiagram parses flowchart TD and LR diagrams', () => {
  const result = parseMermaidDiagram(`
flowchart TD
  A[Client] -->|HTTPS| B(API Gateway)
  B --> C{Auth OK?}
  C -.->|Yes| D((DB))
`);
  assert.equal(result.valid, true);
  if (!result.valid || result.kind !== 'flowchart') {
    assert.fail('Expected valid flowchart');
  }
  assert.equal(result.direction, 'TD');
  assert.equal(result.nodes.length, 4);
  assert.equal(result.edges.length, 3);
  assert.equal(result.edges[0].label, 'HTTPS');
  assert.equal(result.edges[2].dashed, true);
});

test('parseMermaidDiagram parses sequenceDiagram, erDiagram, mindmap, and pie', () => {
  const seq = parseMermaidDiagram(`
sequenceDiagram
  Client->>API: POST /login
  API-->>Client: 200 JWT
`);
  assert.equal(seq.valid, true);
  if (seq.valid && seq.kind === 'sequence') {
    assert.deepEqual(seq.participants, ['Client', 'API']);
    assert.equal(seq.messages.length, 2);
    assert.equal(seq.messages[1].dashed, true);
  } else {
    assert.fail('Expected valid sequence diagram');
  }

  const er = parseMermaidDiagram(`
erDiagram
  USER ||--o{ ROADMAP : owns
`);
  assert.equal(er.valid, true);
  if (er.valid && er.kind === 'er') {
    assert.equal(er.relations.length, 1);
    assert.equal(er.relations[0].left, 'USER');
    assert.equal(er.relations[0].right, 'ROADMAP');
  } else {
    assert.fail('Expected valid erDiagram');
  }

  const mm = parseMermaidDiagram(`
mindmap
  root((DSA))
    Arrays
    Graphs
`);
  assert.equal(mm.valid, true);
  if (mm.valid && mm.kind === 'mindmap') {
    assert.equal(mm.nodes.length, 3);
  } else {
    assert.fail('Expected valid mindmap');
  }

  const pie = parseMermaidDiagram(`
pie title Study Split
  "DSA" : 40
  "Projects" : 60
`);
  assert.equal(pie.valid, true);
  if (pie.valid && pie.kind === 'pie') {
    assert.equal(pie.title, 'Study Split');
    assert.equal(pie.slices.length, 2);
  } else {
    assert.fail('Expected valid pie');
  }
});

test('parseMermaidDiagram parses classDiagram, stateDiagram-v2, and gantt', () => {
  const cls = parseMermaidDiagram(`
classDiagram
  class User {
    +string id
  }
  class Roadmap
  User --> Roadmap : owns
`);
  assert.equal(cls.valid, true);
  if (cls.valid && cls.kind === 'class') {
    assert.equal(cls.classes.length, 2);
    assert.equal(cls.relations.length, 1);
  } else {
    assert.fail('Expected valid classDiagram');
  }

  const st = parseMermaidDiagram(`
stateDiagram-v2
  [*] --> Idle
  Idle --> Streaming : send
  Streaming --> [*]
`);
  assert.equal(st.valid, true);
  if (st.valid && st.kind === 'state') {
    assert.equal(st.transitions.length, 3);
  } else {
    assert.fail('Expected valid stateDiagram');
  }

  const gantt = parseMermaidDiagram(`
gantt
  title Prep Plan
  section Phase 1
  DSA Basics :done, a1, 2026-11-01, 7d
`);
  assert.equal(gantt.valid, true);
  if (gantt.valid && gantt.kind === 'gantt') {
    assert.equal(gantt.title, 'Prep Plan');
    assert.equal(gantt.tasks.length, 1);
  } else {
    assert.fail('Expected valid gantt');
  }
});

test('parseMermaidDiagram returns explicit validation error on invalid or unsupported syntax', () => {
  const empty = parseMermaidDiagram('   ');
  assert.equal(empty.valid, false);

  const unsupported = parseMermaidDiagram('quadrantChart\n  title Priority');
  assert.equal(unsupported.valid, false);
  if (!unsupported.valid) {
    assert.match(unsupported.error, /Unsupported or unrecognized Mermaid diagram/i);
  }
});

test('parseMarkdownBlocks extracts code, mermaid, math, and tables cleanly', () => {
  const md = [
    '# System Design',
    '',
    '$$T(n) = O(n \\log n)$$',
    '',
    '```python',
    'def solve(arr):',
    '    return sorted(arr)',
    '```',
    '',
    '```mermaid',
    'flowchart LR',
    '  A[Load Balancer] --> B[Service]',
    '```',
    '',
    '| Topic | Target |',
    '| --- | --- |',
    '| DSA | 85% |',
  ].join('\n');

  const blocks = parseMarkdownBlocks(md);
  assert.equal(blocks[0].type, 'heading');
  assert.equal(blocks[1].type, 'math');
  assert.equal(blocks[2].type, 'code');
  assert.equal(blocks[3].type, 'mermaid');
  assert.equal(blocks[4].type, 'table');
  if (blocks[4].type === 'table') {
    assert.deepEqual(blocks[4].headers, ['Topic', 'Target']);
    assert.deepEqual(blocks[4].rows, [['DSA', '85%']]);
  }
});

test('isSafeHttpUrl rejects javascript:, data:, and malformed URLs', () => {
  assert.equal(isSafeHttpUrl('https://brainova.ai/docs'), true);
  assert.equal(isSafeHttpUrl('http://localhost:8000/api'), true);
  assert.equal(isSafeHttpUrl('javascript:alert(1)'), false);
  assert.equal(isSafeHttpUrl('data:text/html,<script>alert(1)</script>'), false);
  assert.equal(isSafeHttpUrl('not a url'), false);
});

test('Career Launchpad & AI Mentor frontend wiring is complete and consistent', () => {
  const appTsx = fs.readFileSync(path.join(ROOT, 'src/App.tsx'), 'utf8');
  const appShellTsx = fs.readFileSync(path.join(ROOT, 'src/components/AppShell.tsx'), 'utf8');
  const mainTsx = fs.readFileSync(path.join(ROOT, 'src/main.tsx'), 'utf8');
  const pageTsx = fs.readFileSync(path.join(ROOT, 'src/pages/CareerLaunchpadPage.tsx'), 'utf8');
  const mentorTsx = fs.readFileSync(path.join(ROOT, 'src/components/CareerMentorPanel.tsx'), 'utf8');

  assert.match(appTsx, /path="\/career-launchpad"/);
  assert.match(appTsx, /CareerLaunchpadPage/);
  assert.match(appShellTsx, /to:\s*'\/career-launchpad'/);
  assert.match(mainTsx, /career-launchpad\.css/);

  // Backend endpoint contracts
  assert.match(pageTsx, /\/api\/career-launchpad\/overview/);
  assert.match(pageTsx, /\/api\/career-launchpad\/profile/);
  assert.match(pageTsx, /\/api\/career-launchpad\/assessment/);
  assert.match(pageTsx, /\/api\/career-launchpad\/assessment\/submit/);
  assert.match(pageTsx, /\/api\/career-launchpad\/plan\/generate/);
  assert.match(pageTsx, /\/api\/roadmaps/);
  assert.match(pageTsx, /sessionStorage/);
  assert.match(pageTsx, /readiness\.disclaimer/);
  assert.doesNotMatch(pageTsx, /Quick Launchpad Summary/);

  // Mentor streaming, AbortController Stop, Regenerate, history, feedback, image, and scrollbar hiding
  assert.match(mentorTsx, /\/api\/mentor\/conversations/);
  assert.match(mentorTsx, /\/api\/mentor\/conversations\/.*\/stream/);
  assert.match(mentorTsx, /\/api\/mentor\/conversations\/.*\/image/);
  assert.match(mentorTsx, /AbortController/);
  assert.match(mentorTsx, /Regenerate/);
  assert.match(mentorTsx, /feedback/);
  assert.match(mentorTsx, /placeholder="Ask anything \.\.\."/);

  const cssText = fs.readFileSync(path.join(ROOT, 'src/styles/career-launchpad.css'), 'utf8');
  assert.match(cssText, /\.bnv-mentor-messages[\s\S]*background:\s*#000000/);
  assert.match(cssText, /\.bnv-mentor-messages[\s\S]*color:\s*#ffffff/);
  assert.match(cssText, /\.bnv-mentor-messages[\s\S]*scrollbar-width:\s*none/);
  assert.match(cssText, /\.bnv-mentor-conv-list[\s\S]*scrollbar-width:\s*none/);
  assert.match(cssText, /\.bnv-code-pre[\s\S]*scrollbar-width:\s*none/);
  assert.match(cssText, /\.bnv-md-table-wrap[\s\S]*scrollbar-width:\s*none/);

  const mermaidBlockTsx = fs.readFileSync(path.join(ROOT, 'src/components/MermaidDiagramBlock.tsx'), 'utf8');
  assert.doesNotMatch(mermaidBlockTsx, /bnv-mermaid-badge/);
});
