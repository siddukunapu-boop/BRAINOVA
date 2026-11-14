import React from 'react';
import {
  normalizeReadingMaterial,
  toDisplayText,
  NormalizedReadingMaterial,
} from '../utils/safeRender';
import { EducationalDiagramRenderer } from './EducationalDiagramRenderer';

class ReadingSectionBoundary extends React.Component<
  { sectionName: string; children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { sectionName: string; children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: '12px 14px',
            borderRadius: '10px',
            background: 'var(--surface-2)',
            border: '1px solid var(--border-subtle)',
            fontSize: '0.86rem',
            color: 'var(--text-muted)',
            marginBottom: '16px',
          }}
        >
          Some content in "{this.props.sectionName}" could not be displayed cleanly.
        </div>
      );
    }
    return this.props.children;
  }
}

interface ReadingMaterialViewProps {
  reading: any;
  topic?: any;
  showTableOfContents?: boolean;
}

export const ReadingMaterialView: React.FC<ReadingMaterialViewProps> = ({
  reading: rawReading,
  topic,
  showTableOfContents = false,
}) => {
  const reading: NormalizedReadingMaterial | null = normalizeReadingMaterial(rawReading);

  if (!reading) {
    return (
      <div
        style={{
          padding: '24px',
          borderRadius: '12px',
          background: 'var(--surface-2)',
          border: '1px solid var(--border-subtle)',
          color: 'var(--text-secondary)',
          fontSize: '0.92rem',
        }}
      >
        Reading material is not available yet for this topic. Try reopening or regenerating it.
      </div>
    );
  }

  if (reading.has_custom_reading && reading.custom_markdown) {
    return (
      <div
        className="reading-prose"
        style={{ maxWidth: '78ch', lineHeight: 1.75 }}
      >
        <div
          style={{
            padding: '18px 20px',
            borderRadius: '12px',
            background: 'var(--bg-charcoal)',
            border: '1px solid rgba(168, 85, 247, 0.45)',
            whiteSpace: 'pre-wrap',
            color: 'var(--text-primary)',
          }}
        >
          {reading.custom_markdown}
        </div>
      </div>
    );
  }

  const objectives: string[] = Array.isArray(topic?.learning_objectives)
    ? topic.learning_objectives.map((o: unknown) => toDisplayText(o)).filter(Boolean)
    : [];
  const subtopics: string[] = Array.isArray(topic?.subtopics)
    ? topic.subtopics.map((s: unknown) => toDisplayText(s)).filter(Boolean)
    : [];

  return (
    <div
      className="reading-prose"
      style={{ maxWidth: '78ch', lineHeight: 1.7 }}
    >
      {/* Optional Table of Contents */}
      {showTableOfContents && reading.sections.length > 0 && (
        <nav
          aria-label="Reading Table of Contents"
          style={{
            padding: '14px 18px',
            borderRadius: '10px',
            background: 'var(--bg-charcoal)',
            border: '1px solid var(--border-subtle)',
            marginBottom: '22px',
          }}
        >
          <strong
            style={{
              fontSize: '0.78rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--accent-blue)',
            }}
          >
            In This Reading Guide
          </strong>
          <ul style={{ paddingLeft: '18px', marginTop: '8px', marginBottom: 0, fontSize: '0.88rem' }}>
            {reading.sections.map((sec, idx) => (
              <li key={sec.id || idx}>
                <a href={`#${sec.id || `sec-${idx + 1}`}`}>{sec.heading}</a>
              </li>
            ))}
            {reading.key_definitions.length > 0 && (
              <li>
                <a href="#key-definitions">Important Terminology</a>
              </li>
            )}
            {reading.code_examples.length > 0 && (
              <li>
                <a href="#code-examples">Practical & Code Examples</a>
              </li>
            )}
            {reading.comparison_tables.length > 0 && (
              <li>
                <a href="#comparison-tables">Comparison & Trade-offs</a>
              </li>
            )}
            {(reading.common_mistakes.length > 0 || reading.interview_questions.length > 0) && (
              <li>
                <a href="#common-mistakes">Common Mistakes & Practice Questions</a>
              </li>
            )}
          </ul>
        </nav>
      )}

      {/* 1. Introduction & Overview */}
      {reading.overview && (
        <ReadingSectionBoundary sectionName="Overview">
          <section style={{ marginBottom: '24px' }}>
            <h3 style={{ marginTop: 0 }}>Topic Introduction & Overview</h3>
            <p style={{ color: 'var(--text-primary)', fontSize: '1.01rem', marginBottom: 0 }}>
              {reading.overview}
            </p>
          </section>
        </ReadingSectionBoundary>
      )}

      {/* 2. Learning Objectives & Subtopics */}
      {(objectives.length > 0 || subtopics.length > 0) && (
        <ReadingSectionBoundary sectionName="Objectives & Scope">
          <div className="grid-2" style={{ marginBottom: '24px' }}>
            {objectives.length > 0 && (
              <div
                style={{
                  padding: '14px 16px',
                  borderRadius: '10px',
                  background: 'var(--bg-charcoal)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <strong style={{ fontSize: '0.84rem', color: 'var(--accent-blue)' }}>
                  Learning Objectives
                </strong>
                <ul style={{ paddingLeft: '18px', marginTop: '8px', marginBottom: 0, fontSize: '0.86rem' }}>
                  {objectives.map((obj, i) => (
                    <li key={i}>{obj}</li>
                  ))}
                </ul>
              </div>
            )}
            {subtopics.length > 0 && (
              <div
                style={{
                  padding: '14px 16px',
                  borderRadius: '10px',
                  background: 'var(--bg-charcoal)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <strong style={{ fontSize: '0.84rem', color: 'var(--accent-indigo)' }}>
                  Key Subtopics Covered
                </strong>
                <ul style={{ paddingLeft: '18px', marginTop: '8px', marginBottom: 0, fontSize: '0.86rem' }}>
                  {subtopics.map((sub, i) => (
                    <li key={i}>{sub}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </ReadingSectionBoundary>
      )}

      {/* 3. Visual Concept Diagrams */}
      {reading.diagrams.length > 0 && (
        <ReadingSectionBoundary sectionName="Visual Diagrams">
          <section style={{ marginBottom: '24px' }}>
            <h3>Visual Explanations & Diagrams</h3>
            {reading.diagrams.map((diag, idx) => (
              <EducationalDiagramRenderer key={diag.id || idx} diagram={diag} />
            ))}
          </section>
        </ReadingSectionBoundary>
      )}

      {/* 4. Core Concepts Explained Step by Step */}
      {reading.sections.length > 0 && (
        <ReadingSectionBoundary sectionName="Core Concepts">
          {reading.sections.map((sec, idx) => (
            <section
              key={sec.id || idx}
              id={sec.id || `sec-${idx + 1}`}
              style={{ marginBottom: '24px' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
                <h3 style={{ margin: 0 }}>{sec.heading}</h3>
                {sec.level_tag && <span className="badge badge-blue">{sec.level_tag}</span>}
              </div>
              <div style={{ whiteSpace: 'pre-wrap', color: 'var(--text-secondary)' }}>
                {sec.content}
              </div>
              {sec.key_takeaway && (
                <div
                  style={{
                    marginTop: '10px',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    background: 'rgba(99, 102, 241, 0.1)',
                    borderLeft: '3px solid var(--accent-indigo)',
                    fontSize: '0.88rem',
                    color: 'var(--text-primary)',
                  }}
                >
                  <strong>Key Takeaway:</strong> {sec.key_takeaway}
                </div>
              )}
            </section>
          ))}
        </ReadingSectionBoundary>
      )}

      {/* 5. Important Terminology */}
      {reading.key_definitions.length > 0 && (
        <ReadingSectionBoundary sectionName="Important Terminology">
          <section id="key-definitions" style={{ marginBottom: '24px' }}>
            <h3>Important Terminology</h3>
            <div className="grid-2">
              {reading.key_definitions.map((def, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '12px 14px',
                    borderRadius: '10px',
                    background: 'var(--bg-charcoal)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <strong style={{ color: 'var(--accent-blue)' }}>{def.term}:</strong>{' '}
                  <span style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
                    {def.definition}
                  </span>
                  {def.context && (
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 4 }}>
                      Context: {def.context}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        </ReadingSectionBoundary>
      )}

      {/* 6. Practical & Code Examples */}
      {reading.code_examples.length > 0 && (
        <ReadingSectionBoundary sectionName="Practical Examples">
          <section id="code-examples" style={{ marginBottom: '24px' }}>
            <h3>Practical & Code Examples</h3>
            {reading.code_examples.map((ex, idx) => (
              <div key={idx} style={{ marginBottom: '16px' }}>
                <div
                  style={{
                    fontSize: '0.88rem',
                    fontWeight: 700,
                    color: 'var(--accent-blue)',
                    marginBottom: '6px',
                  }}
                >
                  {ex.title} {ex.language ? `(${ex.language})` : ''}
                </div>
                <pre className="code-block">
                  <code>{ex.code}</code>
                </pre>
                {ex.explanation && (
                  <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
                    {ex.explanation}
                  </p>
                )}
              </div>
            ))}
          </section>
        </ReadingSectionBoundary>
      )}

      {/* 7. Comparison Tables */}
      {reading.comparison_tables.length > 0 && (
        <ReadingSectionBoundary sectionName="Comparison Tables">
          <section id="comparison-tables" style={{ marginBottom: '24px' }}>
            <h3>Comparisons & Trade-offs</h3>
            {reading.comparison_tables.map((tbl, idx) => (
              <div key={idx} style={{ marginBottom: '14px' }}>
                {tbl.title && (
                  <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '6px', color: 'var(--text-primary)' }}>
                    {tbl.title}
                  </div>
                )}
                <div className="table-wrapper">
                  <table className="data-table">
                    {tbl.headers.length > 0 && (
                      <thead>
                        <tr>
                          {tbl.headers.map((h, hi) => (
                            <th key={hi}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                    )}
                    <tbody>
                      {tbl.rows.map((row, ri) => (
                        <tr key={ri}>
                          {row.map((cell, ci) => (
                            <td key={ci}>{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </section>
        </ReadingSectionBoundary>
      )}

      {/* 8. Common Mistakes & Misconceptions (Structured 3-part cards — fixes Error #31) */}
      {reading.common_mistakes.length > 0 && (
        <ReadingSectionBoundary sectionName="Common Mistakes">
          <section id="common-mistakes" style={{ marginBottom: '24px' }}>
            <h3>Common Mistakes & Misconceptions</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {reading.common_mistakes.map((item, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '13px 15px',
                    borderRadius: '10px',
                    background: 'rgba(239, 68, 68, 0.08)',
                    border: '1px solid rgba(239, 68, 68, 0.28)',
                  }}
                >
                  <div style={{ fontWeight: 700, color: '#f87171', fontSize: '0.92rem' }}>
                    Pitfall: {item.mistake}
                  </div>
                  {item.why_it_happens && (
                    <div style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', marginTop: 5 }}>
                      <strong>Why it happens:</strong> {item.why_it_happens}
                    </div>
                  )}
                  {item.fix && (
                    <div style={{ fontSize: '0.86rem', color: '#34d399', marginTop: 5 }}>
                      <strong>How to fix:</strong> {item.fix}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        </ReadingSectionBoundary>
      )}

      {/* 9. Practice Questions / Knowledge Check */}
      {reading.interview_questions.length > 0 && (
        <ReadingSectionBoundary sectionName="Practice Questions">
          <section style={{ marginBottom: '24px' }}>
            <h3>Practice Questions & Knowledge Check</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {reading.interview_questions.map((iq, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '13px 15px',
                    borderRadius: '10px',
                    background: 'var(--bg-charcoal)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.92rem' }}>
                    Q{idx + 1}: {iq.question}
                  </div>
                  {iq.model_answer && (
                    <div style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginTop: 6 }}>
                      <strong>Answer:</strong> {iq.model_answer}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        </ReadingSectionBoundary>
      )}

      {/* 10. Key Points to Remember & Summary */}
      {(reading.takeaways.length > 0 || reading.summary) && (
        <ReadingSectionBoundary sectionName="Summary">
          <section
            style={{
              padding: '16px 18px',
              borderRadius: '12px',
              background: 'var(--surface-2)',
              borderLeft: '4px solid var(--accent-blue)',
            }}
          >
            {reading.takeaways.length > 0 && (
              <div style={{ marginBottom: reading.summary ? '12px' : 0 }}>
                <strong style={{ color: 'var(--accent-blue)', fontSize: '0.9rem' }}>
                  Important Points to Remember
                </strong>
                <ul style={{ paddingLeft: '18px', marginTop: '6px', marginBottom: 0, fontSize: '0.88rem' }}>
                  {reading.takeaways.map((tk, i) => (
                    <li key={i}>{tk}</li>
                  ))}
                </ul>
              </div>
            )}
            {reading.summary && (
              <div>
                <strong>Quick Revision Summary:</strong>{' '}
                <span style={{ color: 'var(--text-secondary)' }}>{reading.summary}</span>
              </div>
            )}
          </section>
        </ReadingSectionBoundary>
      )}
    </div>
  );
};

