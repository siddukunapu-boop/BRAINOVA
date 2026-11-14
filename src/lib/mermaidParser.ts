/**
 * Zero-dependency Mermaid syntax parser & validator for BRAINOVA AI Mentor.
 * Supports: flowchart/graph, sequenceDiagram, erDiagram, mindmap, and pie.
 * Returns structured ASTs for SVG rendering or an explicit validation error.
 */

export type MermaidDiagramKind =
  | 'flowchart'
  | 'sequence'
  | 'er'
  | 'class'
  | 'state'
  | 'gantt'
  | 'mindmap'
  | 'pie';

export interface ClassNode {
  name: string;
  members: string[];
}

export interface ClassRelation {
  from: string;
  to: string;
  symbol: string;
  label?: string;
}

export interface StateTransition {
  from: string;
  to: string;
  label?: string;
}

export interface GanttTask {
  section: string;
  label: string;
  order: number;
  status?: 'done' | 'active' | 'crit';
}

export interface FlowchartNode {
  id: string;
  label: string;
  shape: 'rect' | 'round' | 'diamond' | 'circle';
  layer: number;
  order: number;
}

export interface FlowchartEdge {
  from: string;
  to: string;
  label?: string;
  dashed?: boolean;
}

export interface SequenceMessage {
  from: string;
  to: string;
  label: string;
  dashed: boolean;
}

export interface ErRelation {
  left: string;
  right: string;
  cardinality: string;
  label: string;
}

export interface MindmapNode {
  label: string;
  depth: number;
}

export interface PieSlice {
  label: string;
  value: number;
}

export type ParsedMermaidResult =
  | {
      valid: true;
      kind: 'flowchart';
      direction: 'TD' | 'LR';
      nodes: FlowchartNode[];
      edges: FlowchartEdge[];
    }
  | {
      valid: true;
      kind: 'sequence';
      participants: string[];
      messages: SequenceMessage[];
    }
  | {
      valid: true;
      kind: 'er';
      entities: string[];
      relations: ErRelation[];
    }
  | {
      valid: true;
      kind: 'mindmap';
      nodes: MindmapNode[];
    }
  | {
      valid: true;
      kind: 'pie';
      title: string;
      slices: PieSlice[];
    }
  | {
      valid: true;
      kind: 'class';
      classes: ClassNode[];
      relations: ClassRelation[];
    }
  | {
      valid: true;
      kind: 'state';
      states: string[];
      transitions: StateTransition[];
    }
  | {
      valid: true;
      kind: 'gantt';
      title: string;
      tasks: GanttTask[];
    }
  | {
      valid: false;
      error: string;
    };

function parseNodeToken(raw: string): { id: string; label: string; shape: FlowchartNode['shape'] } {
  const token = raw.trim();
  const diamond = token.match(/^([A-Za-z0-9_]+)\{(.+?)\}$/);
  if (diamond) return { id: diamond[1], label: diamond[2].trim(), shape: 'diamond' };

  const circle = token.match(/^([A-Za-z0-9_]+)\(\((.+?)\)\)$/);
  if (circle) return { id: circle[1], label: circle[2].trim(), shape: 'circle' };

  const round = token.match(/^([A-Za-z0-9_]+)\((.+?)\)$/);
  if (round) return { id: round[1], label: round[2].trim(), shape: 'round' };

  const rect = token.match(/^([A-Za-z0-9_]+)\[(.+?)\]$/);
  if (rect) return { id: rect[1], label: rect[2].trim(), shape: 'rect' };

  const bare = token.match(/^([A-Za-z0-9_]+)$/);
  if (bare) return { id: bare[1], label: bare[1], shape: 'rect' };

  return { id: token.replace(/[^A-Za-z0-9_]/g, '_') || 'node', label: token, shape: 'rect' };
}

export function parseMermaidDiagram(source: string): ParsedMermaidResult {
  const cleaned = (source || '').replace(/\r\n/g, '\n').trim();
  if (!cleaned) {
    return { valid: false, error: 'Diagram source is empty.' };
  }

  const lines = cleaned
    .split('\n')
    .map((l) => l.trimEnd())
    .filter((l) => l.trim() && !l.trim().startsWith('%%'));

  if (lines.length === 0) {
    return { valid: false, error: 'Diagram contains no renderable statements.' };
  }

  const header = lines[0].trim();

  // 1. Flowchart / Graph
  if (/^(flowchart|graph)\s+(TD|TB|LR|RL)\b/i.test(header) || /^(flowchart|graph)$/i.test(header)) {
    const dirMatch = header.match(/\b(TD|TB|LR|RL)\b/i);
    const direction: 'TD' | 'LR' = dirMatch && /LR|RL/i.test(dirMatch[1]) ? 'LR' : 'TD';
    const nodeMap = new Map<string, FlowchartNode>();
    const edges: FlowchartEdge[] = [];

    const ensureNode = (rawToken: string): string => {
      const parsed = parseNodeToken(rawToken);
      const existing = nodeMap.get(parsed.id);
      if (!existing) {
        nodeMap.set(parsed.id, {
          id: parsed.id,
          label: parsed.label,
          shape: parsed.shape,
          layer: 0,
          order: nodeMap.size,
        });
      } else if (parsed.label !== parsed.id && existing.label === existing.id) {
        existing.label = parsed.label;
        existing.shape = parsed.shape;
      }
      return parsed.id;
    };

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (/^(subgraph|end|style|classDef|class|linkStyle)\b/i.test(line)) {
        continue;
      }
      // Match edges: A -->|label| B, A -- label --> B, A -.-> B, A ==> B, A --> B
      const pipeEdge = line.match(/^(.+?)\s*(-->|-.->|==>)\|([^|]+)\|\s*(.+)$/);
      const inlineLabelEdge = line.match(/^(.+?)\s*--\s*([^-]+?)\s*-->\s*(.+)$/);
      const simpleEdge = line.match(/^(.+?)\s*(-->|-.->|==>)\s*(.+)$/);

      if (pipeEdge) {
        const from = ensureNode(pipeEdge[1]);
        const to = ensureNode(pipeEdge[4]);
        edges.push({ from, to, label: pipeEdge[3].trim(), dashed: pipeEdge[2] === '-.->' });
      } else if (inlineLabelEdge) {
        const from = ensureNode(inlineLabelEdge[1]);
        const to = ensureNode(inlineLabelEdge[3]);
        edges.push({ from, to, label: inlineLabelEdge[2].trim() });
      } else if (simpleEdge) {
        const from = ensureNode(simpleEdge[1]);
        const to = ensureNode(simpleEdge[3]);
        edges.push({ from, to, dashed: simpleEdge[2] === '-.->' });
      } else if (/^[A-Za-z0-9_]+(\[|\(|\{)/.test(line)) {
        ensureNode(line);
      }
    }

    if (nodeMap.size === 0) {
      return { valid: false, error: 'Flowchart has no valid nodes or connections.' };
    }

    // Assign topological layers via BFS relaxation
    for (let pass = 0; pass < nodeMap.size; pass++) {
      for (const edge of edges) {
        const u = nodeMap.get(edge.from);
        const v = nodeMap.get(edge.to);
        if (u && v && u.id !== v.id && v.layer <= u.layer) {
          v.layer = Math.min(nodeMap.size - 1, u.layer + 1);
        }
      }
    }

    return {
      valid: true,
      kind: 'flowchart',
      direction,
      nodes: Array.from(nodeMap.values()),
      edges,
    };
  }

  // 2. Sequence Diagram
  if (/^sequenceDiagram$/i.test(header)) {
    const participants: string[] = [];
    const messages: SequenceMessage[] = [];
    const addParticipant = (name: string) => {
      const clean = name.trim();
      if (clean && !participants.includes(clean)) {
        participants.push(clean);
      }
    };

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      const pMatch = line.match(/^(?:participant|actor)\s+([A-Za-z0-9_ ]+?)(?:\s+as\s+(.+))?$/i);
      if (pMatch) {
        addParticipant(pMatch[1]);
        continue;
      }
      const msgMatch = line.match(/^([A-Za-z0-9_ ]+?)\s*(->>|-->>|->|-->)\s*([A-Za-z0-9_ ]+?)\s*:\s*(.+)$/);
      if (msgMatch) {
        const from = msgMatch[1].trim();
        const to = msgMatch[3].trim();
        addParticipant(from);
        addParticipant(to);
        messages.push({
          from,
          to,
          label: msgMatch[4].trim(),
          dashed: msgMatch[2].startsWith('--'),
        });
      }
    }

    if (participants.length === 0 || messages.length === 0) {
      return { valid: false, error: 'Sequence diagram requires participants and messages.' };
    }
    return { valid: true, kind: 'sequence', participants, messages };
  }

  // 3. ER Diagram
  if (/^erDiagram$/i.test(header)) {
    const entities: string[] = [];
    const relations: ErRelation[] = [];
    const addEntity = (name: string) => {
      const clean = name.trim();
      if (clean && !entities.includes(clean)) {
        entities.push(clean);
      }
    };

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      const relMatch = line.match(/^([A-Za-z0-9_]+)\s+([|o}{]+--[|o}{]+)\s+([A-Za-z0-9_]+)\s*:\s*(.+)$/);
      if (relMatch) {
        addEntity(relMatch[1]);
        addEntity(relMatch[3]);
        relations.push({
          left: relMatch[1],
          right: relMatch[3],
          cardinality: relMatch[2],
          label: relMatch[4].replace(/^"|"$/g, '').trim(),
        });
      }
    }

    if (entities.length === 0) {
      return { valid: false, error: 'ER diagram contains no valid entity relationships.' };
    }
    return { valid: true, kind: 'er', entities, relations };
  }

  // 4. Mindmap
  if (/^mindmap$/i.test(header)) {
    const nodes: MindmapNode[] = [];
    for (let i = 1; i < lines.length; i++) {
      const raw = lines[i];
      const indent = raw.search(/\S/);
      if (indent < 0) continue;
      const label = raw.trim().replace(/^root\(\((.+?)\)\)$/, '$1').replace(/^\[(.+?)\]$/, '$1').replace(/^\((.+?)\)$/, '$1');
      if (label) {
        nodes.push({ label, depth: Math.floor(indent / 2) });
      }
    }
    if (nodes.length === 0) {
      return { valid: false, error: 'Mindmap contains no nodes.' };
    }
    return { valid: true, kind: 'mindmap', nodes };
  }

  // 5. Pie Chart
  if (/^pie\b/i.test(header)) {
    let title = header.replace(/^pie\s*(?:showData)?\s*(?:title\s+)?/i, '').trim() || 'Distribution';
    const slices: PieSlice[] = [];
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (/^title\s+/i.test(line)) {
        title = line.replace(/^title\s+/i, '').trim();
        continue;
      }
      const sliceMatch = line.match(/^"([^"]+)"\s*:\s*([0-9]+(?:\.[0-9]+)?)$/);
      if (sliceMatch) {
        const value = Number(sliceMatch[2]);
        if (Number.isFinite(value) && value > 0) {
          slices.push({ label: sliceMatch[1], value });
        }
      }
    }
    if (slices.length === 0) {
      return { valid: false, error: 'Pie chart requires at least one `"Label" : value` slice.' };
    }
    return { valid: true, kind: 'pie', title, slices };
  }

  // 6. Class Diagram
  if (/^classDiagram$/i.test(header)) {
    const classMap = new Map<string, ClassNode>();
    const relations: ClassRelation[] = [];
    let activeClass: string | null = null;

    const ensureClass = (name: string) => {
      const clean = name.trim();
      if (clean && !classMap.has(clean)) {
        classMap.set(clean, { name: clean, members: [] });
      }
      return clean;
    };

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (activeClass) {
        if (line === '}') {
          activeClass = null;
          continue;
        }
        classMap.get(activeClass)?.members.push(line);
        continue;
      }
      const blockOpen = line.match(/^class\s+([A-Za-z0-9_]+)\s*\{$/);
      if (blockOpen) {
        activeClass = ensureClass(blockOpen[1]);
        continue;
      }
      const singleClass = line.match(/^class\s+([A-Za-z0-9_]+)$/);
      if (singleClass) {
        ensureClass(singleClass[1]);
        continue;
      }
      const memberLine = line.match(/^([A-Za-z0-9_]+)\s*:\s*(.+)$/);
      if (memberLine) {
        const cls = ensureClass(memberLine[1]);
        classMap.get(cls)?.members.push(memberLine[2].trim());
        continue;
      }
      const relMatch = line.match(
        /^([A-Za-z0-9_]+)\s*(<\|--|\*--|o--|-->|\.\.>|<\.\.|--)\s*([A-Za-z0-9_]+)(?:\s*:\s*(.+))?$/
      );
      if (relMatch) {
        const from = ensureClass(relMatch[1]);
        const to = ensureClass(relMatch[3]);
        relations.push({
          from,
          to,
          symbol: relMatch[2],
          label: relMatch[4]?.trim(),
        });
      }
    }

    const classes = Array.from(classMap.values());
    if (classes.length === 0) {
      return { valid: false, error: 'Class diagram contains no classes or relationships.' };
    }
    return { valid: true, kind: 'class', classes, relations };
  }

  // 7. State Diagram
  if (/^stateDiagram(?:-v2)?$/i.test(header)) {
    const stateSet = new Set<string>();
    const transitions: StateTransition[] = [];
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (/^(direction|note|end note|\{|\})/i.test(line)) continue;
      const alias = line.match(/^state\s+"([^"]+)"\s+as\s+([A-Za-z0-9_]+)$/i);
      if (alias) {
        stateSet.add(alias[2]);
        continue;
      }
      const tr = line.match(/^(\[\*\]|[A-Za-z0-9_]+)\s*-->\s*(\[\*\]|[A-Za-z0-9_]+)(?:\s*:\s*(.+))?$/);
      if (tr) {
        const from = tr[1] === '[*]' ? 'Start' : tr[1];
        const to = tr[2] === '[*]' ? 'End' : tr[2];
        stateSet.add(from);
        stateSet.add(to);
        transitions.push({ from, to, label: tr[3]?.trim() });
      }
    }
    const states = Array.from(stateSet);
    if (states.length === 0) {
      return { valid: false, error: 'State diagram contains no valid states or transitions.' };
    }
    return { valid: true, kind: 'state', states, transitions };
  }

  // 8. Gantt Chart
  if (/^gantt$/i.test(header)) {
    let title = 'Project Schedule';
    let currentSection = 'Timeline';
    const tasks: GanttTask[] = [];
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (/^title\s+/i.test(line)) {
        title = line.replace(/^title\s+/i, '').trim() || title;
        continue;
      }
      if (/^section\s+/i.test(line)) {
        currentSection = line.replace(/^section\s+/i, '').trim() || currentSection;
        continue;
      }
      if (/^(dateFormat|axisFormat|excludes|todayMarker)/i.test(line)) continue;
      const taskMatch = line.match(/^([^:]+):\s*(.*)$/);
      if (taskMatch) {
        const meta = taskMatch[2].toLowerCase();
        const status: GanttTask['status'] = meta.includes('crit')
          ? 'crit'
          : meta.includes('done')
            ? 'done'
            : meta.includes('active')
              ? 'active'
              : undefined;
        tasks.push({
          section: currentSection,
          label: taskMatch[1].trim(),
          order: tasks.length,
          status,
        });
      }
    }
    if (tasks.length === 0) {
      return { valid: false, error: 'Gantt chart contains no tasks.' };
    }
    return { valid: true, kind: 'gantt', title, tasks };
  }

  return {
    valid: false,
    error: `Unsupported or unrecognized Mermaid diagram header: "${header}".`,
  };
}

