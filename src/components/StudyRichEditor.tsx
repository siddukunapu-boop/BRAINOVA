import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Bold,
  Italic,
  List,
  ListOrdered,
  Redo2,
  Underline,
  Undo2,
} from 'lucide-react';
import { StudySelect, StudySelectOption } from './StudyControls';
import {
  cloneStudyPageDoc,
  createEmptyStudyPageDoc,
  STUDY_FONT_OPTIONS,
  STUDY_GLITTER_OPTIONS,
  StudyDocBlock,
  StudyFontId,
  StudyGlitterId,
  StudyPageDoc,
  StudyTextRun,
} from '../types/studyJournal';

interface InlineStyleState {
  bold: boolean;
  italic: boolean;
  underline: boolean;
  font: StudyFontId;
  glitter: StudyGlitterId;
}

const DEFAULT_INLINE_STYLE: InlineStyleState = {
  bold: false,
  italic: false,
  underline: false,
  font: 'sans',
  glitter: 'default',
};

interface StudyRichEditorProps {
  pageKey: string;
  doc: StudyPageDoc;
  placeholder: string;
  onChange: (nextDoc: StudyPageDoc) => void;
}

function sameRunStyle(a: StudyTextRun, b: StudyTextRun): boolean {
  return (
    Boolean(a.bold) === Boolean(b.bold) &&
    Boolean(a.italic) === Boolean(b.italic) &&
    Boolean(a.underline) === Boolean(b.underline) &&
    (a.font || 'sans') === (b.font || 'sans') &&
    (a.glitter || 'default') === (b.glitter || 'default')
  );
}

function mergeAdjacentRuns(runs: StudyTextRun[]): StudyTextRun[] {
  const merged: StudyTextRun[] = [];
  for (const run of runs) {
    const cleanText = run.text.replace(/\u200B/g, '');
    if (!cleanText) continue;
    const normalized: StudyTextRun = {
      text: cleanText,
      ...(run.bold ? { bold: true } : {}),
      ...(run.italic ? { italic: true } : {}),
      ...(run.underline ? { underline: true } : {}),
      ...(run.font && run.font !== 'sans' ? { font: run.font } : {}),
      ...(run.glitter && run.glitter !== 'default' ? { glitter: run.glitter } : {}),
    };
    const prev = merged[merged.length - 1];
    if (prev && sameRunStyle(prev, normalized)) {
      prev.text += normalized.text;
    } else {
      merged.push(normalized);
    }
  }
  return merged;
}

function applyRunClassesAndAttrs(span: HTMLSpanElement, style: InlineStyleState): void {
  span.dataset.studyRun = '1';
  span.dataset.bold = style.bold ? '1' : '0';
  span.dataset.italic = style.italic ? '1' : '0';
  span.dataset.underline = style.underline ? '1' : '0';
  span.dataset.font = style.font;
  span.dataset.glitter = style.glitter;

  span.className = `study-font-${style.font} study-glitter-${style.glitter}`;
  span.style.fontWeight = style.bold ? '700' : '';
  span.style.fontStyle = style.italic ? 'italic' : '';
  span.style.textDecoration = style.underline ? 'underline' : '';
}

function readStyleFromElement(el: HTMLElement | null): InlineStyleState {
  if (!el) return { ...DEFAULT_INLINE_STYLE };
  const fontAttr = el.dataset.font as StudyFontId | undefined;
  const glitterAttr = el.dataset.glitter as StudyGlitterId | undefined;
  return {
    bold: el.dataset.bold === '1' || el.tagName === 'B' || el.tagName === 'STRONG',
    italic: el.dataset.italic === '1' || el.tagName === 'I' || el.tagName === 'EM',
    underline: el.dataset.underline === '1' || el.tagName === 'U',
    font: fontAttr || 'sans',
    glitter: glitterAttr || 'default',
  };
}

function createRunSpan(run: StudyTextRun): HTMLSpanElement {
  const span = document.createElement('span');
  applyRunClassesAndAttrs(span, {
    bold: Boolean(run.bold),
    italic: Boolean(run.italic),
    underline: Boolean(run.underline),
    font: run.font || 'sans',
    glitter: run.glitter || 'default',
  });
  span.textContent = run.text;
  return span;
}

function renderRunsIntoElement(parent: HTMLElement, runs: StudyTextRun[]): void {
  if (runs.length === 0) {
    parent.appendChild(document.createElement('br'));
    return;
  }
  for (const run of runs) {
    if (!run.text) continue;
    parent.appendChild(createRunSpan(run));
  }
}

function hydrateEditorDom(container: HTMLElement, doc: StudyPageDoc): void {
  container.replaceChildren();
  const blocks = doc.blocks.length > 0 ? doc.blocks : createEmptyStudyPageDoc().blocks;

  for (const block of blocks) {
    if (block.type === 'paragraph') {
      const p = document.createElement('p');
      renderRunsIntoElement(p, block.runs);
      container.appendChild(p);
    } else if (block.type === 'heading') {
      const tag = block.level === 1 ? 'h1' : block.level === 2 ? 'h2' : 'h3';
      const h = document.createElement(tag);
      renderRunsIntoElement(h, block.runs);
      container.appendChild(h);
    } else {
      const listEl = document.createElement(block.type === 'bulletList' ? 'ul' : 'ol');
      if (block.type === 'orderedList') {
        listEl.dataset.listKind = 'ordered';
      } else if (block.type === 'romanList') {
        listEl.dataset.listKind = 'roman';
      }
      const items = block.items.length > 0 ? block.items : [[]];
      for (const itemRuns of items) {
        const li = document.createElement('li');
        renderRunsIntoElement(li, itemRuns);
        listEl.appendChild(li);
      }
      container.appendChild(listEl);
    }
  }
}

function collectRunsFromNode(node: Node, inherited: InlineStyleState): StudyTextRun[] {
  if (node.nodeType === Node.TEXT_NODE) {
    const text = (node.textContent || '').replace(/\u200B/g, '');
    if (!text) return [];
    return [
      {
        text,
        bold: inherited.bold,
        italic: inherited.italic,
        underline: inherited.underline,
        font: inherited.font,
        glitter: inherited.glitter,
      },
    ];
  }

  if (node.nodeType !== Node.ELEMENT_NODE) return [];
  const el = node as HTMLElement;
  if (el.tagName === 'BR') return [];

  let nextStyle = { ...inherited };
  if (el.dataset.studyRun === '1') {
    nextStyle = readStyleFromElement(el);
  } else {
    if (el.tagName === 'B' || el.tagName === 'STRONG') nextStyle.bold = true;
    if (el.tagName === 'I' || el.tagName === 'EM') nextStyle.italic = true;
    if (el.tagName === 'U') nextStyle.underline = true;
  }

  const out: StudyTextRun[] = [];
  for (const child of Array.from(el.childNodes)) {
    out.push(...collectRunsFromNode(child, nextStyle));
  }
  return out;
}

function serializeEditorDom(container: HTMLElement): StudyPageDoc {
  const blocks: StudyDocBlock[] = [];

  for (const child of Array.from(container.childNodes)) {
    if (child.nodeType === Node.TEXT_NODE) {
      const text = (child.textContent || '').replace(/\u200B/g, '');
      if (text.trim()) {
        blocks.push({
          type: 'paragraph',
          runs: mergeAdjacentRuns([{ text }]),
        });
      }
      continue;
    }

    if (child.nodeType !== Node.ELEMENT_NODE) continue;
    const el = child as HTMLElement;
    const tag = el.tagName;

    if (tag === 'H1' || tag === 'H2' || tag === 'H3') {
      const level = tag === 'H1' ? 1 : tag === 'H2' ? 2 : 3;
      blocks.push({
        type: 'heading',
        level,
        runs: mergeAdjacentRuns(collectRunsFromNode(el, DEFAULT_INLINE_STYLE)),
      });
    } else if (tag === 'UL' || tag === 'OL') {
      const listType: 'bulletList' | 'orderedList' | 'romanList' =
        tag === 'UL'
          ? 'bulletList'
          : el.dataset.listKind === 'roman'
            ? 'romanList'
            : 'orderedList';
      const items: StudyTextRun[][] = [];
      for (const li of Array.from(el.children)) {
        if (li.tagName === 'LI') {
          items.push(mergeAdjacentRuns(collectRunsFromNode(li, DEFAULT_INLINE_STYLE)));
        }
      }
      blocks.push({
        type: listType,
        items: items.length > 0 ? items : [[]],
      });
    } else {
      blocks.push({
        type: 'paragraph',
        runs: mergeAdjacentRuns(collectRunsFromNode(el, DEFAULT_INLINE_STYLE)),
      });
    }
  }

  if (blocks.length === 0) {
    return createEmptyStudyPageDoc();
  }
  return { type: 'doc', blocks };
}

function isDocVisuallyEmpty(doc: StudyPageDoc): boolean {
  if (doc.blocks.length > 1) return false;
  const first = doc.blocks[0];
  if (!first) return true;
  if (first.type === 'paragraph' && first.runs.length === 0) return true;
  return false;
}

export const StudyRichEditor: React.FC<StudyRichEditorProps> = ({
  pageKey,
  doc,
  placeholder,
  onChange,
}) => {
  const editorRef = useRef<HTMLDivElement | null>(null);
  const lastSerializedRef = useRef<string>('');
  const savedRangeRef = useRef<Range | null>(null);
  const historyMapRef = useRef<Map<string, { past: StudyPageDoc[]; future: StudyPageDoc[] }>>(
    new Map()
  );

  const [activeStyle, setActiveStyle] = useState<InlineStyleState>({ ...DEFAULT_INLINE_STYLE });
  const [activeBlockType, setActiveBlockType] = useState<string>('paragraph');
  const [isEmpty, setIsEmpty] = useState<boolean>(() => isDocVisuallyEmpty(doc));
  const [historyTick, setHistoryTick] = useState(0);

  const fontOptions = useMemo<StudySelectOption<StudyFontId>[]>(
    () =>
      STUDY_FONT_OPTIONS.map((opt) => ({
        value: opt.id,
        label: opt.label,
        previewClassName: opt.className,
      })),
    []
  );

  const getPageHistory = useCallback((key: string) => {
    let entry = historyMapRef.current.get(key);
    if (!entry) {
      entry = { past: [], future: [] };
      historyMapRef.current.set(key, entry);
    }
    return entry;
  }, []);

  const captureCurrentRange = useCallback(() => {
    const container = editorRef.current;
    const sel = window.getSelection();
    if (!container || !sel || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0);
    if (container.contains(range.commonAncestorContainer)) {
      savedRangeRef.current = range.cloneRange();
    }
  }, []);

  const ensureEditorSelection = useCallback((): Range | null => {
    const container = editorRef.current;
    if (!container) return null;
    container.focus();

    const sel = window.getSelection();
    if (!sel) return null;

    if (sel.rangeCount > 0) {
      const current = sel.getRangeAt(0);
      if (container.contains(current.commonAncestorContainer)) {
        savedRangeRef.current = current.cloneRange();
        return current;
      }
    }

    if (savedRangeRef.current && container.contains(savedRangeRef.current.commonAncestorContainer)) {
      const restored = savedRangeRef.current.cloneRange();
      sel.removeAllRanges();
      sel.addRange(restored);
      return restored;
    }

    if (!container.firstElementChild) {
      const p = document.createElement('p');
      p.appendChild(document.createElement('br'));
      container.appendChild(p);
    }
    const targetBlock = container.lastElementChild || container;
    const fallbackRange = document.createRange();
    fallbackRange.selectNodeContents(targetBlock);
    fallbackRange.collapse(false);
    sel.removeAllRanges();
    sel.addRange(fallbackRange);
    savedRangeRef.current = fallbackRange.cloneRange();
    return fallbackRange;
  }, []);

  useEffect(() => {
    const el = editorRef.current;
    if (!el) return;
    const incomingJson = JSON.stringify(doc);
    if (incomingJson === lastSerializedRef.current) return;
    hydrateEditorDom(el, doc);
    lastSerializedRef.current = incomingJson;
    savedRangeRef.current = null;
    setIsEmpty(isDocVisuallyEmpty(doc));
  }, [pageKey, doc]);

  const syncToolbarFromSelection = useCallback(() => {
    const container = editorRef.current;
    const sel = window.getSelection();
    if (!container || !sel || sel.rangeCount === 0) return;
    const anchor = sel.anchorNode;
    if (!anchor || !container.contains(anchor)) return;

    captureCurrentRange();

    let cursor: Node | null = anchor;
    let foundRun: HTMLElement | null = null;
    let foundBlock: HTMLElement | null = null;

    while (cursor && cursor !== container) {
      if (cursor.nodeType === Node.ELEMENT_NODE) {
        const el = cursor as HTMLElement;
        if (!foundRun && el.dataset.studyRun === '1') {
          foundRun = el;
        }
        if (!foundBlock) {
          if (el.tagName === 'LI') {
            const listParent = el.parentElement;
            if (listParent?.tagName === 'UL' || listParent?.tagName === 'OL') {
              foundBlock = listParent;
            }
          } else if (['P', 'H1', 'H2', 'H3', 'DIV'].includes(el.tagName)) {
            foundBlock = el;
          }
        }
      }
      cursor = cursor.parentNode;
    }

    if (foundRun) {
      setActiveStyle(readStyleFromElement(foundRun));
    }

    if (foundBlock) {
      const tag = foundBlock.tagName;
      if (tag === 'H1') setActiveBlockType('h1');
      else if (tag === 'H2') setActiveBlockType('h2');
      else if (tag === 'H3') setActiveBlockType('h3');
      else if (tag === 'UL') setActiveBlockType('bulletList');
      else if (tag === 'OL') {
        setActiveBlockType(foundBlock.dataset.listKind === 'roman' ? 'romanList' : 'orderedList');
      } else {
        setActiveBlockType('paragraph');
      }
    }
  }, [captureCurrentRange]);

  useEffect(() => {
    const handleSelectionChange = () => {
      syncToolbarFromSelection();
    };
    document.addEventListener('selectionchange', handleSelectionChange);
    return () => document.removeEventListener('selectionchange', handleSelectionChange);
  }, [syncToolbarFromSelection]);

  const commitFromDom = useCallback(
    (pushUndo = true) => {
      const el = editorRef.current;
      if (!el) return;
      const nextDoc = serializeEditorDom(el);
      const nextJson = JSON.stringify(nextDoc);
      if (nextJson === lastSerializedRef.current) return;

      if (pushUndo && lastSerializedRef.current) {
        const hist = getPageHistory(pageKey);
        hist.past.push(JSON.parse(lastSerializedRef.current) as StudyPageDoc);
        if (hist.past.length > 60) hist.past.shift();
        hist.future = [];
        setHistoryTick((t) => t + 1);
      }

      lastSerializedRef.current = nextJson;
      setIsEmpty(isDocVisuallyEmpty(nextDoc));
      onChange(nextDoc);
    },
    [getPageHistory, onChange, pageKey]
  );

  const handleUndo = useCallback(() => {
    const hist = getPageHistory(pageKey);
    if (hist.past.length === 0) return;
    const previous = hist.past.pop()!;
    if (lastSerializedRef.current) {
      hist.future.push(JSON.parse(lastSerializedRef.current) as StudyPageDoc);
    }
    const el = editorRef.current;
    if (el) {
      hydrateEditorDom(el, previous);
    }
    lastSerializedRef.current = JSON.stringify(previous);
    savedRangeRef.current = null;
    setIsEmpty(isDocVisuallyEmpty(previous));
    setHistoryTick((t) => t + 1);
    onChange(cloneStudyPageDoc(previous));
  }, [getPageHistory, onChange, pageKey]);

  const handleRedo = useCallback(() => {
    const hist = getPageHistory(pageKey);
    if (hist.future.length === 0) return;
    const next = hist.future.pop()!;
    if (lastSerializedRef.current) {
      hist.past.push(JSON.parse(lastSerializedRef.current) as StudyPageDoc);
    }
    const el = editorRef.current;
    if (el) {
      hydrateEditorDom(el, next);
    }
    lastSerializedRef.current = JSON.stringify(next);
    savedRangeRef.current = null;
    setIsEmpty(isDocVisuallyEmpty(next));
    setHistoryTick((t) => t + 1);
    onChange(cloneStudyPageDoc(next));
  }, [getPageHistory, onChange, pageKey]);

  const applyInlinePatch = useCallback(
    (patch: Partial<InlineStyleState>) => {
      const container = editorRef.current;
      if (!container) return;

      const nextActive: InlineStyleState = { ...activeStyle, ...patch };
      setActiveStyle(nextActive);

      const range = ensureEditorSelection();
      const sel = window.getSelection();
      if (!range || !sel) return;

      if (range.collapsed) {
        // If caret is already inside an empty carrier span, update it in place so multiple
        // toolbar clicks (e.g., Font + Glitter Colour + Bold) combine cleanly before typing.
        const anchorEl =
          range.startContainer.nodeType === Node.ELEMENT_NODE
            ? (range.startContainer as HTMLElement)
            : range.startContainer.parentElement;

        if (
          anchorEl?.dataset.studyRun === '1' &&
          (anchorEl.textContent || '').replace(/\u200B/g, '') === ''
        ) {
          applyRunClassesAndAttrs(anchorEl, nextActive);
          savedRangeRef.current = range.cloneRange();
          return;
        }

        // Remove placeholder <br> in empty block if present
        if (anchorEl && ['P', 'H1', 'H2', 'H3', 'LI'].includes(anchorEl.tagName)) {
          const br = anchorEl.querySelector('br');
          if (br && anchorEl.childNodes.length === 1) {
            br.remove();
          }
        }

        const span = document.createElement('span');
        applyRunClassesAndAttrs(span, nextActive);
        const zwsp = document.createTextNode('\u200B');
        span.appendChild(zwsp);
        range.insertNode(span);
        const newRange = document.createRange();
        newRange.setStart(zwsp, 1);
        newRange.collapse(true);
        sel.removeAllRanges();
        sel.addRange(newRange);
        savedRangeRef.current = newRange.cloneRange();
        return;
      }

      // Non-collapsed selection: update ONLY selected text nodes and preserve selection
      const root = range.commonAncestorContainer;
      const textNodes: Text[] = [];
      const walker = document.createTreeWalker(
        root.nodeType === Node.TEXT_NODE ? root.parentNode || container : root,
        NodeFilter.SHOW_TEXT
      );
      let current: Node | null = walker.nextNode();
      while (current) {
        const textNode = current as Text;
        if (range.intersectsNode(textNode) && (textNode.textContent || '').length > 0) {
          textNodes.push(textNode);
        }
        current = walker.nextNode();
      }

      if (textNodes.length === 0) return;

      let firstInsertedSpan: HTMLSpanElement | null = null;
      let lastInsertedSpan: HTMLSpanElement | null = null;

      for (const textNode of textNodes) {
        const fullText = textNode.textContent || '';
        const startOffset = textNode === range.startContainer ? range.startOffset : 0;
        const endOffset = textNode === range.endContainer ? range.endOffset : fullText.length;
        if (startOffset >= endOffset) continue;

        const beforeText = fullText.slice(0, startOffset);
        const selectedText = fullText.slice(startOffset, endOffset);
        const afterText = fullText.slice(endOffset);

        const parentEl = textNode.parentElement;
        const baseStyle =
          parentEl?.dataset.studyRun === '1'
            ? readStyleFromElement(parentEl)
            : { ...DEFAULT_INLINE_STYLE };
        const updatedStyle: InlineStyleState = { ...baseStyle, ...patch };

        const frag = document.createDocumentFragment();
        if (beforeText) {
          frag.appendChild(
            parentEl?.dataset.studyRun === '1'
              ? createRunSpan({ text: beforeText, ...baseStyle })
              : document.createTextNode(beforeText)
          );
        }
        const selSpan = createRunSpan({ text: selectedText, ...updatedStyle });
        if (!firstInsertedSpan) firstInsertedSpan = selSpan;
        lastInsertedSpan = selSpan;
        frag.appendChild(selSpan);
        if (afterText) {
          frag.appendChild(
            parentEl?.dataset.studyRun === '1'
              ? createRunSpan({ text: afterText, ...baseStyle })
              : document.createTextNode(afterText)
          );
        }

        if (parentEl?.dataset.studyRun === '1' && parentEl.parentNode) {
          parentEl.parentNode.replaceChild(frag, parentEl);
        } else {
          textNode.parentNode?.replaceChild(frag, textNode);
        }
      }

      if (firstInsertedSpan && lastInsertedSpan) {
        const nextRange = document.createRange();
        nextRange.setStartBefore(firstInsertedSpan);
        nextRange.setEndAfter(lastInsertedSpan);
        sel.removeAllRanges();
        sel.addRange(nextRange);
        savedRangeRef.current = nextRange.cloneRange();
      }

      commitFromDom(true);
    },
    [activeStyle, commitFromDom, ensureEditorSelection]
  );

  const applyBlockType = useCallback(
    (requested: 'paragraph' | 'h1' | 'h2' | 'h3' | 'bulletList' | 'orderedList' | 'romanList') => {
      const container = editorRef.current;
      if (!container) return;

      const range = ensureEditorSelection();
      const sel = window.getSelection();
      if (!range || !sel) return;

      const target =
        requested !== 'paragraph' && activeBlockType === requested ? 'paragraph' : requested;

      const anchor = range.startContainer;
      let blockEl: HTMLElement | null =
        anchor.nodeType === Node.ELEMENT_NODE
          ? (anchor as HTMLElement)
          : anchor.parentElement;

      while (blockEl && blockEl.parentElement !== container) {
        blockEl = blockEl.parentElement;
      }

      if (!blockEl || blockEl === container) {
        const p = document.createElement('p');
        p.appendChild(document.createElement('br'));
        container.appendChild(p);
        blockEl = p;
      }

      const runs = mergeAdjacentRuns(collectRunsFromNode(blockEl, DEFAULT_INLINE_STYLE));

      if (target === 'bulletList' || target === 'orderedList' || target === 'romanList') {
        const listEl = document.createElement(target === 'bulletList' ? 'ul' : 'ol');
        if (target === 'orderedList') listEl.dataset.listKind = 'ordered';
        if (target === 'romanList') listEl.dataset.listKind = 'roman';

        if (blockEl.tagName === 'UL' || blockEl.tagName === 'OL') {
          while (blockEl.firstChild) {
            listEl.appendChild(blockEl.firstChild);
          }
        } else {
          const li = document.createElement('li');
          renderRunsIntoElement(li, runs);
          listEl.appendChild(li);
        }
        container.replaceChild(listEl, blockEl);
        const firstLi = listEl.querySelector('li');
        if (firstLi) {
          const r = document.createRange();
          r.selectNodeContents(firstLi);
          r.collapse(false);
          sel.removeAllRanges();
          sel.addRange(r);
          savedRangeRef.current = r.cloneRange();
        }
      } else {
        let sourceRuns = runs;
        if (blockEl.tagName === 'UL' || blockEl.tagName === 'OL') {
          const li = blockEl.querySelector('li');
          sourceRuns = li
            ? mergeAdjacentRuns(collectRunsFromNode(li, DEFAULT_INLINE_STYLE))
            : [];
        }
        const tag =
          target === 'h1' ? 'h1' : target === 'h2' ? 'h2' : target === 'h3' ? 'h3' : 'p';
        const nextEl = document.createElement(tag);
        renderRunsIntoElement(nextEl, sourceRuns);
        container.replaceChild(nextEl, blockEl);

        const r = document.createRange();
        r.selectNodeContents(nextEl);
        r.collapse(false);
        sel.removeAllRanges();
        sel.addRange(r);
        savedRangeRef.current = r.cloneRange();
      }

      setActiveBlockType(target);
      commitFromDom(true);
    },
    [activeBlockType, commitFromDom, ensureEditorSelection]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'z') {
      e.preventDefault();
      handleUndo();
      return;
    }
    if (
      (e.ctrlKey || e.metaKey) &&
      (e.key.toLowerCase() === 'y' || (e.shiftKey && e.key.toLowerCase() === 'z'))
    ) {
      e.preventDefault();
      handleRedo();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
      e.preventDefault();
      applyInlinePatch({ bold: !activeStyle.bold });
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'i') {
      e.preventDefault();
      applyInlinePatch({ italic: !activeStyle.italic });
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'u') {
      e.preventDefault();
      applyInlinePatch({ underline: !activeStyle.underline });
    }
  };

  const hist = getPageHistory(pageKey);
  void historyTick;

  return (
    <div className="space-y-3 min-w-0">
      {/* Rich-Text Formatting Toolbar */}
      <div
        className="study-rich-toolbar"
        role="toolbar"
        aria-label="Study Journal rich text formatting"
      >
        {/* Text Emphasis */}
        <div className="study-toolbar-group">
          <button
            type="button"
            className={`study-tool-btn ${activeStyle.bold ? 'active' : ''}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => applyInlinePatch({ bold: !activeStyle.bold })}
            title="Bold (Ctrl+B)"
            aria-label="Bold"
            aria-pressed={activeStyle.bold}
          >
            <Bold size={16} className="shrink-0" />
          </button>
          <button
            type="button"
            className={`study-tool-btn ${activeStyle.italic ? 'active' : ''}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => applyInlinePatch({ italic: !activeStyle.italic })}
            title="Italic (Ctrl+I)"
            aria-label="Italic"
            aria-pressed={activeStyle.italic}
          >
            <Italic size={16} className="shrink-0" />
          </button>
          <button
            type="button"
            className={`study-tool-btn ${activeStyle.underline ? 'active' : ''}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => applyInlinePatch({ underline: !activeStyle.underline })}
            title="Underline (Ctrl+U)"
            aria-label="Underline"
            aria-pressed={activeStyle.underline}
          >
            <Underline size={16} className="shrink-0" />
          </button>
        </div>

        {/* Headings & Paragraph */}
        <div className="study-toolbar-group">
          <button
            type="button"
            className={`study-tool-btn ${activeBlockType === 'paragraph' ? 'active' : ''}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => applyBlockType('paragraph')}
            title="Normal paragraph"
            aria-label="Normal paragraph"
            aria-pressed={activeBlockType === 'paragraph'}
          >
            P
          </button>
          <button
            type="button"
            className={`study-tool-btn ${activeBlockType === 'h1' ? 'active' : ''}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => applyBlockType('h1')}
            title="Heading 1"
            aria-label="Heading 1"
            aria-pressed={activeBlockType === 'h1'}
          >
            H1
          </button>
          <button
            type="button"
            className={`study-tool-btn ${activeBlockType === 'h2' ? 'active' : ''}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => applyBlockType('h2')}
            title="Heading 2"
            aria-label="Heading 2"
            aria-pressed={activeBlockType === 'h2'}
          >
            H2
          </button>
          <button
            type="button"
            className={`study-tool-btn ${activeBlockType === 'h3' ? 'active' : ''}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => applyBlockType('h3')}
            title="Heading 3"
            aria-label="Heading 3"
            aria-pressed={activeBlockType === 'h3'}
          >
            H3
          </button>
        </div>

        {/* Lists: Bullet, Numbered, Roman Numerals */}
        <div className="study-toolbar-group">
          <button
            type="button"
            className={`study-tool-btn ${activeBlockType === 'bulletList' ? 'active' : ''}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => applyBlockType('bulletList')}
            title="Bullet List"
            aria-label="Bullet List"
            aria-pressed={activeBlockType === 'bulletList'}
          >
            <List size={16} className="shrink-0" />
          </button>
          <button
            type="button"
            className={`study-tool-btn ${activeBlockType === 'orderedList' ? 'active' : ''}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => applyBlockType('orderedList')}
            title="Numbered List (1, 2, 3)"
            aria-label="Numbered List"
            aria-pressed={activeBlockType === 'orderedList'}
          >
            <ListOrdered size={16} className="shrink-0" />
          </button>
          <button
            type="button"
            className={`study-tool-btn ${activeBlockType === 'romanList' ? 'active' : ''}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => applyBlockType('romanList')}
            title="Roman Numeral List (I, II, III)"
            aria-label="Roman Numeral List"
            aria-pressed={activeBlockType === 'romanList'}
          >
            I.II
          </button>
        </div>

        {/* Undo / Redo */}
        <div className="study-toolbar-group">
          <button
            type="button"
            className="study-tool-btn"
            disabled={hist.past.length === 0}
            onMouseDown={(e) => e.preventDefault()}
            onClick={handleUndo}
            title="Undo (Ctrl+Z)"
            aria-label="Undo"
          >
            <Undo2 size={16} className="shrink-0" />
          </button>
          <button
            type="button"
            className="study-tool-btn"
            disabled={hist.future.length === 0}
            onMouseDown={(e) => e.preventDefault()}
            onClick={handleRedo}
            title="Redo (Ctrl+Y)"
            aria-label="Redo"
          >
            <Redo2 size={16} className="shrink-0" />
          </button>
        </div>

        {/* Custom 5-Font Picker (preserves editor focus/selection!) */}
        <div className="study-toolbar-group">
          <StudySelect<StudyFontId>
            ariaLabel="Font style"
            variant="paper"
            preserveEditorFocus
            value={activeStyle.font}
            options={fontOptions}
            onChange={(nextFont) => applyInlinePatch({ font: nextFont })}
            className="study-font-picker"
          />
        </div>

        {/* 12 Glitter-Inspired Text Colours + Classic Ink */}
        <div className="study-glitter-bar" role="group" aria-label="Glitter ink colours">
          <button
            type="button"
            className={`study-glitter-swatch study-swatch-default ${
              activeStyle.glitter === 'default' ? 'active' : ''
            }`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => applyInlinePatch({ glitter: 'default' })}
            title="Classic Ink"
            aria-label="Classic Ink"
            aria-pressed={activeStyle.glitter === 'default'}
          />
          {STUDY_GLITTER_OPTIONS.map((g) => (
            <button
              key={g.id}
              type="button"
              className={`study-glitter-swatch ${g.swatchClass} ${
                activeStyle.glitter === g.id ? 'active' : ''
              }`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => applyInlinePatch({ glitter: g.id })}
              title={g.label}
              aria-label={g.label}
              aria-pressed={activeStyle.glitter === g.id}
            />
          ))}
        </div>
      </div>

      {/* Ruled ContentEditable Paper Surface */}
      <div className="diary-ruled-surface">
        <div
          ref={editorRef}
          contentEditable
          suppressContentEditableWarning
          role="textbox"
          aria-multiline="true"
          aria-label="Study journal page editor"
          data-placeholder={placeholder}
          data-empty={isEmpty ? 'true' : 'false'}
          className="study-editor-canvas"
          onInput={() => {
            captureCurrentRange();
            commitFromDom(true);
          }}
          onKeyUp={syncToolbarFromSelection}
          onMouseUp={syncToolbarFromSelection}
          onBlur={captureCurrentRange}
          onKeyDown={handleKeyDown}
        />
      </div>
    </div>
  );
};
