import React, { Suspense, useMemo, useState } from 'react';
import { Check, Copy, Hash } from 'lucide-react';
import { isSafeHttpUrl, parseMarkdownBlocks } from '../lib/mentorMarkdown';

const LazyMermaidDiagramBlock = React.lazy(() => import('./MermaidDiagramBlock'));

function formatLatexText(expr: string): string {
  return expr
    .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, '($1)/($2)')
    .replace(/\\sqrt\{([^}]+)\}/g, '√($1)')
    .replace(/\\log_?([0-9a-zA-Z]*)/g, (_, b) => (b ? `log_${b}` : 'log'))
    .replace(/\\ln\b/g, 'ln')
    .replace(/\\sum\b/g, '∑')
    .replace(/\\prod\b/g, '∏')
    .replace(/\\int\b/g, '∫')
    .replace(/\\infty\b/g, '∞')
    .replace(/\\times\b/g, '×')
    .replace(/\\cdot\b/g, '·')
    .replace(/\\pm\b/g, '±')
    .replace(/\\le\b/g, '≤')
    .replace(/\\ge\b/g, '≥')
    .replace(/\\neq\b/g, '≠')
    .replace(/\\approx\b/g, '≈')
    .replace(/\\rightarrow\b|\\to\b/g, '→')
    .replace(/\\leftarrow\b/g, '←')
    .replace(/\\alpha\b/g, 'α')
    .replace(/\\beta\b/g, 'β')
    .replace(/\\gamma\b/g, 'γ')
    .replace(/\\delta\b/g, 'δ')
    .replace(/\\theta\b/g, 'θ')
    .replace(/\\lambda\b/g, 'λ')
    .replace(/\\pi\b/g, 'π')
    .replace(/\\sigma\b/g, 'σ')
    .replace(/\\Omega\b/g, 'Ω')
    .replace(/\\Theta\b/g, 'Θ')
    .replace(/\\left\(|\\right\)/g, (m) => (m.includes('(') ? '(' : ')'))
    .replace(/\\\{|\\}/g, (m) => m.slice(1));
}

function renderInlineTokens(text: string): React.ReactNode[] {
  // Tokenize inline code `...`, inline math $...$, bold **...**, italic *...*, and markdown links [label](url)
  const pattern = /(`[^`]+`|\$[^$\n]+\$|\*\*[^*]+\*\*|\*[^*\n]+\*|\[[^\]]+\]\([^)]+\))/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let keyIdx = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    const k = `tok-${keyIdx++}`;
    if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code key={k} className="bnv-inline-code">
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith('$') && token.endsWith('$')) {
      parts.push(
        <span key={k} className="bnv-inline-math">
          {formatLatexText(token.slice(1, -1))}
        </span>
      );
    } else if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(<strong key={k}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(<em key={k}>{token.slice(1, -1)}</em>);
    } else if (token.startsWith('[')) {
      const linkMatch = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (linkMatch && isSafeHttpUrl(linkMatch[2].trim())) {
        parts.push(
          <a
            key={k}
            href={linkMatch[2].trim()}
            target="_blank"
            rel="noopener noreferrer"
            className="bnv-md-link"
          >
            {linkMatch[1]}
          </a>
        );
      } else {
        parts.push(token);
      }
    } else {
      parts.push(token);
    }
    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}

const KEYWORD_RE =
  /\b(const|let|var|function|return|if|else|for|while|switch|case|break|continue|class|interface|type|import|export|from|async|await|try|catch|def|elif|pass|yield|lambda|public|private|static|void|int|float|double|boolean|struct|SELECT|FROM|WHERE|JOIN|GROUP BY|ORDER BY|INSERT|UPDATE|DELETE)\b/g;

function highlightCodeLine(line: string): React.ReactNode {
  const commentIdx = line.indexOf('//');
  const pyCommentIdx = line.trimStart().startsWith('#') ? line.indexOf('#') : -1;
  const splitAt = commentIdx >= 0 ? commentIdx : pyCommentIdx;
  const codePart = splitAt >= 0 ? line.slice(0, splitAt) : line;
  const commentPart = splitAt >= 0 ? line.slice(splitAt) : '';

  const nodes: React.ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  const re = new RegExp(KEYWORD_RE.source, 'g');
  let k = 0;
  while ((m = re.exec(codePart)) !== null) {
    if (m.index > last) {
      nodes.push(codePart.slice(last, m.index));
    }
    nodes.push(
      <span key={`kw-${k++}`} className="bnv-code-kw">
        {m[0]}
      </span>
    );
    last = re.lastIndex;
  }
  if (last < codePart.length) {
    nodes.push(codePart.slice(last));
  }
  if (commentPart) {
    nodes.push(
      <span key="cmt" className="bnv-code-cmt">
        {commentPart}
      </span>
    );
  }
  return nodes.length > 0 ? nodes : '\n';
}

const CodeBlock: React.FC<{ language: string; code: string }> = ({ language, code }) => {
  const [copied, setCopied] = useState(false);
  const [showLineNumbers, setShowLineNumbers] = useState(false);
  const lines = useMemo(() => code.split('\n'), [code]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // ignore clipboard errors
    }
  };

  return (
    <div className="bnv-code-block">
      <div className="bnv-code-header">
        <span className="bnv-code-lang">{language || 'code'}</span>
        <div className="bnv-code-actions">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setShowLineNumbers((v) => !v)}
            aria-label="Toggle line numbers"
            title="Toggle line numbers"
          >
            <Hash size={13} />
            <span>{showLineNumbers ? 'Hide #' : 'Lines'}</span>
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={handleCopy} aria-label="Copy code">
            {copied ? <Check size={13} /> : <Copy size={13} />}
            <span>{copied ? 'Copied' : 'Copy code'}</span>
          </button>
        </div>
      </div>
      <pre className="bnv-code-pre">
        <code>
          {lines.map((ln, idx) => (
            <span key={idx} className="bnv-code-line">
              {showLineNumbers && <span className="bnv-code-line-num">{idx + 1}</span>}
              {highlightCodeLine(ln)}
              {idx < lines.length - 1 ? '\n' : ''}
            </span>
          ))}
        </code>
      </pre>
    </div>
  );
};

export const MentorMarkdownRenderer: React.FC<{ content: string }> = ({ content }) => {
  const blocks = useMemo(() => parseMarkdownBlocks(content), [content]);

  return (
    <div className="bnv-markdown-body">
      {blocks.map((block, idx) => {
        switch (block.type) {
          case 'heading': {
            const Tag = (`h${block.level}` as 'h1' | 'h2' | 'h3' | 'h4');
            return (
              <Tag key={idx} className={`bnv-md-h${block.level}`}>
                {renderInlineTokens(block.text)}
              </Tag>
            );
          }
          case 'paragraph':
            return (
              <p key={idx} className="bnv-md-p">
                {renderInlineTokens(block.text)}
              </p>
            );
          case 'code':
            return <CodeBlock key={idx} language={block.language} code={block.code} />;
          case 'mermaid':
            return (
              <Suspense
                key={idx}
                fallback={<div className="bnv-mermaid-loading">Rendering diagram…</div>}
              >
                <LazyMermaidDiagramBlock source={block.source} />
              </Suspense>
            );
          case 'math':
            return (
              <div key={idx} className="bnv-math-block" aria-label="Mathematical equation">
                {formatLatexText(block.formula)}
              </div>
            );
          case 'blockquote':
            return (
              <blockquote key={idx} className="bnv-md-quote">
                {renderInlineTokens(block.text)}
              </blockquote>
            );
          case 'list':
            return block.ordered ? (
              <ol key={idx} className="bnv-md-list">
                {block.items.map((item, i) => (
                  <li key={i}>{renderInlineTokens(item)}</li>
                ))}
              </ol>
            ) : (
              <ul key={idx} className="bnv-md-list">
                {block.items.map((item, i) => (
                  <li key={i}>{renderInlineTokens(item)}</li>
                ))}
              </ul>
            );
          case 'table':
            return (
              <div key={idx} className="table-wrapper bnv-md-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      {block.headers.map((h, i) => (
                        <th key={i}>{renderInlineTokens(h)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {block.rows.map((row, rIdx) => (
                      <tr key={rIdx}>
                        {block.headers.map((_, cIdx) => (
                          <td key={cIdx}>{renderInlineTokens(row[cIdx] || '')}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          default:
            return null;
        }
      })}
    </div>
  );
};

