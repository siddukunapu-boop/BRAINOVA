/**
 * Safe rendering and normalization helpers for AI-generated educational content.
 * Prevents React Error #31 ("Objects are not valid as a React child") when
 * structured objects or unexpected AI shapes arrive in JSX.
 */

export interface NormalizedMistake {
  mistake: string;
  why_it_happens: string;
  fix: string;
}

export interface NormalizedSection {
  id: string;
  heading: string;
  level_tag: string;
  content: string;
  key_takeaway: string;
}

export interface NormalizedDiagramNode {
  id: string;
  step: string;
  label: string;
  sublabel: string;
  role: string;
}

export interface NormalizedDiagram {
  id: string;
  title: string;
  type: string;
  caption: string;
  nodes: NormalizedDiagramNode[];
}

export interface NormalizedDefinition {
  term: string;
  definition: string;
  context: string;
}

export interface NormalizedCodeExample {
  title: string;
  language: string;
  code: string;
  explanation: string;
}

export interface NormalizedComparisonTable {
  title: string;
  headers: string[];
  rows: string[][];
}

export interface NormalizedQuestion {
  question: string;
  model_answer: string;
}

export interface NormalizedReadingMaterial {
  id?: string;
  topic_id?: string;
  title: string;
  overview: string;
  sections: NormalizedSection[];
  diagrams: NormalizedDiagram[];
  key_definitions: NormalizedDefinition[];
  code_examples: NormalizedCodeExample[];
  comparison_tables: NormalizedComparisonTable[];
  common_mistakes: NormalizedMistake[];
  interview_questions: NormalizedQuestion[];
  takeaways: string[];
  summary: string;
  has_custom_reading: boolean;
  custom_title: string;
  custom_markdown: string;
  source_badge: string;
  is_user_edited: boolean;
  version: number;
}

/**
 * Safely convert any unknown value to displayable plain text.
 * Never returns `[object Object]`.
 */
export function toDisplayText(value: unknown, fallback = ''): string {
  if (value === null || value === undefined) return fallback;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    const parts = value.map((item) => toDisplayText(item)).filter(Boolean);
    return parts.length > 0 ? parts.join(', ') : fallback;
  }
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    const preferredKeys = [
      'text',
      'content',
      'description',
      'label',
      'title',
      'name',
      'heading',
      'mistake',
      'summary',
      'value',
    ];
    for (const k of preferredKeys) {
      if (typeof obj[k] === 'string' && (obj[k] as string).trim()) {
        return (obj[k] as string).trim();
      }
    }
    const entries = Object.entries(obj)
      .map(([k, v]) => {
        const text = toDisplayText(v);
        return text ? `${k.replace(/_/g, ' ')}: ${text}` : '';
      })
      .filter(Boolean);
    return entries.length > 0 ? entries.join(' • ') : fallback;
  }
  return fallback;
}

export function normalizeMistakes(raw: unknown): NormalizedMistake[] {
  if (!Array.isArray(raw)) return [];
  const result: NormalizedMistake[] = [];
  for (const item of raw) {
    if (typeof item === 'string') {
      const trimmed = item.trim();
      if (trimmed) {
        result.push({ mistake: trimmed, why_it_happens: '', fix: '' });
      }
      continue;
    }
    if (item && typeof item === 'object') {
      const obj = item as Record<string, unknown>;
      const mistake = toDisplayText(obj.mistake ?? obj.title ?? obj.pitfall, '').trim();
      const why = toDisplayText(obj.why_it_happens ?? obj.why ?? obj.reason, '').trim();
      const fix = toDisplayText(obj.fix ?? obj.solution ?? obj.remedy, '').trim();
      if (mistake || why || fix) {
        result.push({
          mistake: mistake || 'Common Pitfall',
          why_it_happens: why,
          fix,
        });
      }
    }
  }
  return result;
}

export function normalizeReadingMaterial(raw: any): NormalizedReadingMaterial | null {
  if (!raw || typeof raw !== 'object') return null;

  const sections: NormalizedSection[] = Array.isArray(raw.sections)
    ? raw.sections
        .map((s: any, idx: number) => {
          if (typeof s === 'string') {
            return {
              id: `sec-${idx + 1}`,
              heading: `Section ${idx + 1}`,
              level_tag: '',
              content: s,
              key_takeaway: '',
            };
          }
          if (!s || typeof s !== 'object') return null;
          return {
            id: toDisplayText(s.id, `sec-${idx + 1}`),
            heading: toDisplayText(s.heading ?? s.title, `Section ${idx + 1}`),
            level_tag: toDisplayText(s.level_tag, ''),
            content: toDisplayText(s.content ?? s.body ?? s.explanation, ''),
            key_takeaway: toDisplayText(s.key_takeaway, ''),
          };
        })
        .filter((s: NormalizedSection | null): s is NormalizedSection => Boolean(s && (s.heading || s.content)))
    : [];

  const diagrams: NormalizedDiagram[] = Array.isArray(raw.diagrams)
    ? raw.diagrams
        .map((d: any, idx: number) => {
          if (!d || typeof d !== 'object') return null;
          const rawNodes = Array.isArray(d.nodes) ? d.nodes : Array.isArray(d.steps) ? d.steps : [];
          const nodes: NormalizedDiagramNode[] = rawNodes
            .map((nd: any, nIdx: number) => {
              if (typeof nd === 'string') {
                return {
                  id: `n-${nIdx + 1}`,
                  step: String(nIdx + 1).padStart(2, '0'),
                  label: nd,
                  sublabel: '',
                  role: '',
                };
              }
              if (!nd || typeof nd !== 'object') return null;
              return {
                id: toDisplayText(nd.id, `n-${nIdx + 1}`),
                step: toDisplayText(nd.step, String(nIdx + 1).padStart(2, '0')),
                label: toDisplayText(nd.label ?? nd.title ?? nd.name, `Stage ${nIdx + 1}`),
                sublabel: toDisplayText(nd.sublabel ?? nd.detail ?? nd.description, ''),
                role: toDisplayText(nd.role ?? nd.tag, ''),
              };
            })
            .filter((n: NormalizedDiagramNode | null): n is NormalizedDiagramNode => Boolean(n));
          if (nodes.length === 0) return null;
          return {
            id: toDisplayText(d.id, `diag-${idx + 1}`),
            title: toDisplayText(d.title, 'Concept Diagram'),
            type: toDisplayText(d.type, 'flow').toLowerCase(),
            caption: toDisplayText(d.caption ?? d.explanation, ''),
            nodes,
          };
        })
        .filter((d: NormalizedDiagram | null): d is NormalizedDiagram => Boolean(d))
    : [];

  const rawDefs = Array.isArray(raw.key_definitions)
    ? raw.key_definitions
    : Array.isArray(raw.terminology)
    ? raw.terminology
    : [];
  const key_definitions: NormalizedDefinition[] = rawDefs
    .map((d: any) => {
      if (!d || typeof d !== 'object') return null;
      const term = toDisplayText(d.term ?? d.name, '').trim();
      const definition = toDisplayText(d.definition ?? d.meaning, '').trim();
      if (!term && !definition) return null;
      return {
        term: term || 'Term',
        definition,
        context: toDisplayText(d.context, ''),
      };
    })
    .filter((d: NormalizedDefinition | null): d is NormalizedDefinition => Boolean(d));

  const code_examples: NormalizedCodeExample[] = Array.isArray(raw.code_examples)
    ? raw.code_examples
        .map((ex: any) => {
          if (!ex || typeof ex !== 'object') return null;
          const code = toDisplayText(ex.code, '');
          if (!code.trim()) return null;
          return {
            title: toDisplayText(ex.title, 'Example'),
            language: toDisplayText(ex.language, 'text'),
            code,
            explanation: toDisplayText(ex.explanation, ''),
          };
        })
        .filter((ex: NormalizedCodeExample | null): ex is NormalizedCodeExample => Boolean(ex))
    : [];

  const comparison_tables: NormalizedComparisonTable[] = Array.isArray(raw.comparison_tables)
    ? raw.comparison_tables
        .map((tbl: any) => {
          if (!tbl || typeof tbl !== 'object') return null;
          const headers = Array.isArray(tbl.headers) ? tbl.headers.map((h: unknown) => toDisplayText(h)) : [];
          const rows = Array.isArray(tbl.rows)
            ? tbl.rows
                .filter((r: unknown) => Array.isArray(r))
                .map((r: unknown[]) => r.map((cell) => toDisplayText(cell)))
            : [];
          if (headers.length === 0 && rows.length === 0) return null;
          return {
            title: toDisplayText(tbl.title, ''),
            headers,
            rows,
          };
        })
        .filter((t: NormalizedComparisonTable | null): t is NormalizedComparisonTable => Boolean(t))
    : [];

  const common_mistakes = normalizeMistakes(
    Array.isArray(raw.common_mistakes) && raw.common_mistakes.length > 0
      ? raw.common_mistakes
      : raw.mistakes
  );

  const interview_questions: NormalizedQuestion[] = Array.isArray(raw.interview_questions)
    ? raw.interview_questions
        .map((q: any) => {
          if (!q || typeof q !== 'object') return null;
          const question = toDisplayText(q.question, '').trim();
          const model_answer = toDisplayText(q.model_answer ?? q.answer, '').trim();
          if (!question) return null;
          return { question, model_answer };
        })
        .filter((q: NormalizedQuestion | null): q is NormalizedQuestion => Boolean(q))
    : [];

  const takeaways: string[] = Array.isArray(raw.takeaways)
    ? raw.takeaways.map((t: unknown) => toDisplayText(t)).filter(Boolean)
    : [];

  return {
    id: raw.id ? toDisplayText(raw.id) : undefined,
    topic_id: raw.topic_id ? toDisplayText(raw.topic_id) : undefined,
    title: toDisplayText(raw.title, 'Topic Reading Material'),
    overview: toDisplayText(raw.overview, ''),
    sections,
    diagrams,
    key_definitions,
    code_examples,
    comparison_tables,
    common_mistakes,
    interview_questions,
    takeaways,
    summary: toDisplayText(raw.summary, ''),
    has_custom_reading: Boolean(raw.has_custom_reading),
    custom_title: toDisplayText(raw.custom_title, ''),
    custom_markdown: toDisplayText(raw.custom_markdown, ''),
    source_badge: toDisplayText(raw.source_badge, raw.has_custom_reading ? 'CUSTOMIZED' : 'ORIGINAL'),
    is_user_edited: Boolean(raw.is_user_edited),
    version: typeof raw.version === 'number' ? raw.version : 1,
  };
}

