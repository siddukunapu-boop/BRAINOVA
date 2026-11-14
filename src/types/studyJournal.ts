export type StudyFontId = 'handwriting' | 'serif' | 'sans' | 'soft' | 'typewriter';

export type StudyGlitterId =
  | 'default'
  | 'glitter-blue'
  | 'royal-violet'
  | 'rose-glitter'
  | 'golden-sparkle'
  | 'emerald-glow'
  | 'aqua-crystal'
  | 'sunset-copper'
  | 'pink-diamond'
  | 'sapphire'
  | 'champagne-gold'
  | 'amethyst'
  | 'mint-crystal';

export type LearningStatus = 'understood' | 'needs_revision';

export interface StudyFontOption {
  id: StudyFontId;
  label: string;
  previewText: string;
  className: string;
}

export const STUDY_FONT_OPTIONS: StudyFontOption[] = [
  {
    id: 'handwriting',
    label: 'Elegant Handwriting',
    previewText: 'Aa',
    className: 'study-font-handwriting',
  },
  {
    id: 'serif',
    label: 'Classic Serif',
    previewText: 'Aa',
    className: 'study-font-serif',
  },
  {
    id: 'sans',
    label: 'Modern Sans Serif',
    previewText: 'Aa',
    className: 'study-font-sans',
  },
  {
    id: 'soft',
    label: 'Soft Handwritten',
    previewText: 'Aa',
    className: 'study-font-soft',
  },
  {
    id: 'typewriter',
    label: 'Classic Typewriter',
    previewText: 'Aa',
    className: 'study-font-typewriter',
  },
];

export interface StudyGlitterOption {
  id: Exclude<StudyGlitterId, 'default'>;
  label: string;
  swatchClass: string;
  textClass: string;
  swatchHex: string;
}

export const STUDY_GLITTER_OPTIONS: StudyGlitterOption[] = [
  {
    id: 'glitter-blue',
    label: 'Glitter Blue',
    swatchClass: 'study-swatch-glitter-blue',
    textClass: 'study-glitter-glitter-blue',
    swatchHex: '#0284c7',
  },
  {
    id: 'royal-violet',
    label: 'Royal Violet',
    swatchClass: 'study-swatch-royal-violet',
    textClass: 'study-glitter-royal-violet',
    swatchHex: '#6d28d9',
  },
  {
    id: 'rose-glitter',
    label: 'Rose Glitter',
    swatchClass: 'study-swatch-rose-glitter',
    textClass: 'study-glitter-rose-glitter',
    swatchHex: '#be185d',
  },
  {
    id: 'golden-sparkle',
    label: 'Golden Sparkle',
    swatchClass: 'study-swatch-golden-sparkle',
    textClass: 'study-glitter-golden-sparkle',
    swatchHex: '#b45309',
  },
  {
    id: 'emerald-glow',
    label: 'Emerald Glow',
    swatchClass: 'study-swatch-emerald-glow',
    textClass: 'study-glitter-emerald-glow',
    swatchHex: '#047857',
  },
  {
    id: 'aqua-crystal',
    label: 'Aqua Crystal',
    swatchClass: 'study-swatch-aqua-crystal',
    textClass: 'study-glitter-aqua-crystal',
    swatchHex: '#0e7490',
  },
  {
    id: 'sunset-copper',
    label: 'Sunset Copper',
    swatchClass: 'study-swatch-sunset-copper',
    textClass: 'study-glitter-sunset-copper',
    swatchHex: '#c2410c',
  },
  {
    id: 'pink-diamond',
    label: 'Pink Diamond',
    swatchClass: 'study-swatch-pink-diamond',
    textClass: 'study-glitter-pink-diamond',
    swatchHex: '#db2777',
  },
  {
    id: 'sapphire',
    label: 'Sapphire',
    swatchClass: 'study-swatch-sapphire',
    textClass: 'study-glitter-sapphire',
    swatchHex: '#1d4ed8',
  },
  {
    id: 'champagne-gold',
    label: 'Champagne Gold',
    swatchClass: 'study-swatch-champagne-gold',
    textClass: 'study-glitter-champagne-gold',
    swatchHex: '#92400e',
  },
  {
    id: 'amethyst',
    label: 'Amethyst',
    swatchClass: 'study-swatch-amethyst',
    textClass: 'study-glitter-amethyst',
    swatchHex: '#7e22ce',
  },
  {
    id: 'mint-crystal',
    label: 'Mint Crystal',
    swatchClass: 'study-swatch-mint-crystal',
    textClass: 'study-glitter-mint-crystal',
    swatchHex: '#0f766e',
  },
];

export interface StudyTextRun {
  text: string;
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  font?: StudyFontId;
  glitter?: StudyGlitterId;
}

export type StudyDocBlock =
  | {
      type: 'paragraph';
      runs: StudyTextRun[];
    }
  | {
      type: 'heading';
      level: 1 | 2 | 3;
      runs: StudyTextRun[];
    }
  | {
      type: 'bulletList' | 'orderedList' | 'romanList';
      items: StudyTextRun[][];
    };

export interface StudyPageDoc {
  type: 'doc';
  blocks: StudyDocBlock[];
}

export interface StudyJournalEntry {
  id: string;
  title: string;
  subject: string;
  topic: string;
  chapter_or_module: string;
  study_date: string;
  duration_minutes: number;
  learning_status: LearningStatus;
  key_concepts: string;
  learning_outcomes: string;
  revision_notes: string;
  pages: StudyPageDoc[];
  page_count: number;
  preview: string;
  is_draft: boolean;
  client_draft_key?: string | null;
  created_at: string;
  updated_at: string;
}

export function createEmptyStudyPageDoc(): StudyPageDoc {
  return {
    type: 'doc',
    blocks: [{ type: 'paragraph', runs: [] }],
  };
}

export function cloneStudyPageDoc(doc: StudyPageDoc): StudyPageDoc {
  return JSON.parse(JSON.stringify(doc)) as StudyPageDoc;
}

export function extractStudyPlainText(doc: StudyPageDoc): string {
  const parts: string[] = [];
  for (const block of doc.blocks) {
    if (block.type === 'paragraph' || block.type === 'heading') {
      const line = block.runs.map((r) => r.text).join('').trim();
      if (line) parts.push(line);
    } else {
      for (const item of block.items) {
        const line = item.map((r) => r.text).join('').trim();
        if (line) parts.push(line);
      }
    }
  }
  return parts.join(' ').trim();
}

