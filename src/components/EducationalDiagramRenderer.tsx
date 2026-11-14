import React from 'react';
import { ArrowRight } from 'lucide-react';
import { NormalizedDiagram } from '../utils/safeRender';

class DiagramErrorBoundary extends React.Component<
  { title: string; children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { title: string; children: React.ReactNode }) {
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
            padding: '14px 16px',
            borderRadius: '10px',
            background: 'var(--surface-2)',
            border: '1px solid var(--border-subtle)',
            fontSize: '0.86rem',
            color: 'var(--text-muted)',
          }}
        >
          Unable to render visual diagram for "{this.props.title}".
        </div>
      );
    }
    return this.props.children;
  }
}

const DIAGRAM_TYPE_LABELS: Record<string, string> = {
  flow: 'Concept Flow Diagram',
  process: 'Step-by-Step Process',
  architecture: 'Architecture Diagram',
  sequence: 'Execution Sequence',
  comparison: 'Comparison Flow',
  concept_map: 'Concept Map',
};

export const EducationalDiagramRenderer: React.FC<{
  diagram: NormalizedDiagram;
}> = ({ diagram }) => {
  if (!diagram || !Array.isArray(diagram.nodes) || diagram.nodes.length === 0) {
    return null;
  }

  const typeLabel = DIAGRAM_TYPE_LABELS[diagram.type] || 'Visual Concept Diagram';

  return (
    <DiagramErrorBoundary title={diagram.title}>
      <figure
        style={{
          margin: '0 0 18px 0',
          padding: '18px',
          borderRadius: '14px',
          background: 'var(--surface-1)',
          border: '1px solid var(--border-default)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '10px',
            flexWrap: 'wrap',
            marginBottom: '14px',
          }}
        >
          <figcaption
            style={{
              fontWeight: 700,
              fontSize: '0.96rem',
              color: 'var(--text-primary)',
            }}
          >
            {diagram.title}
          </figcaption>
          <span className="badge badge-indigo">{typeLabel}</span>
        </div>

        {/* Responsive node flow: wraps cleanly on smaller viewports without text clipping */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'stretch',
            gap: '10px',
          }}
        >
          {diagram.nodes.map((node, idx) => (
            <React.Fragment key={node.id || idx}>
              <div
                style={{
                  flex: '1 1 160px',
                  minWidth: '150px',
                  padding: '12px 14px',
                  borderRadius: '12px',
                  background: 'var(--surface-2)',
                  border:
                    idx === 0
                      ? '1.5px solid var(--accent-blue)'
                      : '1px solid var(--border-default)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '6px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '6px',
                  }}
                >
                  <span
                    style={{
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      letterSpacing: '0.04em',
                      color: 'var(--accent-blue)',
                      textTransform: 'uppercase',
                    }}
                  >
                    {node.step}
                  </span>
                  {node.role && (
                    <span
                      style={{
                        fontSize: '0.68rem',
                        fontWeight: 600,
                        padding: '2px 7px',
                        borderRadius: '999px',
                        background: 'var(--bg-charcoal)',
                        color: 'var(--text-secondary)',
                        border: '1px solid var(--border-subtle)',
                      }}
                    >
                      {node.role}
                    </span>
                  )}
                </div>

                <div
                  style={{
                    fontWeight: 700,
                    fontSize: '0.9rem',
                    color: 'var(--text-primary)',
                    lineHeight: 1.3,
                    overflowWrap: 'anywhere',
                  }}
                >
                  {node.label}
                </div>

                {node.sublabel && (
                  <div
                    style={{
                      fontSize: '0.8rem',
                      color: 'var(--text-secondary)',
                      lineHeight: 1.4,
                      overflowWrap: 'anywhere',
                    }}
                  >
                    {node.sublabel}
                  </div>
                )}
              </div>

              {idx < diagram.nodes.length - 1 && (
                <div
                  aria-hidden="true"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--accent-blue)',
                    padding: '0 2px',
                    flexShrink: 0,
                  }}
                >
                  <ArrowRight size={16} />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>

        {diagram.caption && (
          <p
            style={{
              margin: '12px 0 0 0',
              fontSize: '0.85rem',
              color: 'var(--text-secondary)',
              lineHeight: 1.55,
            }}
          >
            {diagram.caption}
          </p>
        )}
      </figure>
    </DiagramErrorBoundary>
  );
};

