import React, { useMemo, useRef, useState } from 'react';
import { Check, Code2, Copy, Download, Maximize2, RotateCcw, X, ZoomIn, ZoomOut } from 'lucide-react';
import { parseMermaidDiagram, ParsedMermaidResult } from '../lib/mermaidParser';

interface MermaidDiagramBlockProps {
  source: string;
}

const PIE_COLORS = ['#6366f1', '#22d3ee', '#a78bfa', '#fbbf24', '#34d399', '#f472b6', '#38bdf8'];

function renderSvgContent(parsed: Extract<ParsedMermaidResult, { valid: true }>): React.ReactNode {
  if (parsed.kind === 'flowchart') {
    const layers = new Map<number, typeof parsed.nodes>();
    for (const node of parsed.nodes) {
      const arr = layers.get(node.layer) || [];
      arr.push(node);
      layers.set(node.layer, arr);
    }
    const maxLayer = Math.max(...Array.from(layers.keys()), 0);
    const maxPerLayer = Math.max(...Array.from(layers.values()).map((a) => a.length), 1);

    const nodeW = 160;
    const nodeH = 48;
    const gapX = 48;
    const gapY = 54;
    const pad = 32;

    const coords = new Map<string, { x: number; y: number; cx: number; cy: number }>();
    const isLR = parsed.direction === 'LR';

    for (let l = 0; l <= maxLayer; l++) {
      const group = layers.get(l) || [];
      group.forEach((n, idx) => {
        const offsetCentered = idx - (group.length - 1) / 2;
        if (isLR) {
          const x = pad + l * (nodeW + gapX);
          const cy = pad + ((maxPerLayer - 1) / 2 + offsetCentered) * (nodeH + gapY) + nodeH / 2;
          const y = cy - nodeH / 2;
          coords.set(n.id, { x, y, cx: x + nodeW / 2, cy });
        } else {
          const cx = pad + ((maxPerLayer - 1) / 2 + offsetCentered) * (nodeW + gapX) + nodeW / 2;
          const x = cx - nodeW / 2;
          const y = pad + l * (nodeH + gapY);
          coords.set(n.id, { x, y, cx, cy: y + nodeH / 2 });
        }
      });
    }

    const svgW = isLR
      ? pad * 2 + (maxLayer + 1) * nodeW + maxLayer * gapX
      : pad * 2 + maxPerLayer * nodeW + Math.max(0, maxPerLayer - 1) * gapX;
    const svgH = isLR
      ? pad * 2 + maxPerLayer * nodeH + Math.max(0, maxPerLayer - 1) * gapY
      : pad * 2 + (maxLayer + 1) * nodeH + maxLayer * gapY;

    return (
      <svg
        viewBox={`0 0 ${Math.max(320, svgW)} ${Math.max(160, svgH)}`}
        className="bnv-mermaid-svg"
        role="img"
        aria-label="Flowchart diagram"
      >
        <defs>
          <marker id="bnvArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,1 L7,4 L0,7 Z" fill="#38bdf8" />
          </marker>
        </defs>

        {parsed.edges.map((edge, idx) => {
          const from = coords.get(edge.from);
          const to = coords.get(edge.to);
          if (!from || !to) return null;
          const x1 = isLR ? from.x + nodeW : from.cx;
          const y1 = isLR ? from.cy : from.y + nodeH;
          const x2 = isLR ? to.x : to.cx;
          const y2 = isLR ? to.cy : to.y;
          const mx = (x1 + x2) / 2;
          const my = (y1 + y2) / 2;
          return (
            <g key={`${edge.from}-${edge.to}-${idx}`}>
              <line
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="rgba(56, 189, 248, 0.72)"
                strokeWidth={1.8}
                strokeDasharray={edge.dashed ? '5 4' : undefined}
                markerEnd="url(#bnvArrow)"
              />
              {edge.label && (
                <g transform={`translate(${mx}, ${my})`}>
                  <rect x={-36} y={-10} width={72} height={20} rx={6} fill="#0b1224" stroke="rgba(139, 92, 246, 0.45)" />
                  <text x={0} y={4} textAnchor="middle" fill="#cbd5e1" fontSize={10.5} fontWeight={600}>
                    {edge.label.slice(0, 14)}
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {parsed.nodes.map((node) => {
          const pos = coords.get(node.id);
          if (!pos) return null;
          const labelText = node.label.length > 22 ? `${node.label.slice(0, 20)}…` : node.label;
          return (
            <g key={node.id} transform={`translate(${pos.x}, ${pos.y})`}>
              {node.shape === 'diamond' ? (
                <polygon
                  points={`${nodeW / 2},0 ${nodeW},${nodeH / 2} ${nodeW / 2},${nodeH} 0,${nodeH / 2}`}
                  fill="rgba(22, 33, 62, 0.96)"
                  stroke="rgba(251, 191, 36, 0.7)"
                  strokeWidth={1.5}
                />
              ) : (
                <rect
                  width={nodeW}
                  height={nodeH}
                  rx={node.shape === 'round' || node.shape === 'circle' ? 22 : 10}
                  fill="rgba(19, 28, 54, 0.96)"
                  stroke="rgba(139, 92, 246, 0.62)"
                  strokeWidth={1.5}
                />
              )}
              <text
                x={nodeW / 2}
                y={nodeH / 2 + 4}
                textAnchor="middle"
                fill="#f8fafc"
                fontSize={12}
                fontWeight={600}
              >
                {labelText}
              </text>
            </g>
          );
        })}
      </svg>
    );
  }

  if (parsed.kind === 'sequence') {
    const colW = 160;
    const pad = 28;
    const svgW = Math.max(360, pad * 2 + parsed.participants.length * colW);
    const svgH = 110 + parsed.messages.length * 46;
    const pIndex = new Map(parsed.participants.map((p, idx) => [p, idx]));

    return (
      <svg viewBox={`0 0 ${svgW} ${svgH}`} className="bnv-mermaid-svg" role="img" aria-label="Sequence diagram">
        <defs>
          <marker id="bnvSeqArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,1 L7,4 L0,7 Z" fill="#a78bfa" />
          </marker>
        </defs>
        {parsed.participants.map((p, idx) => {
          const cx = pad + idx * colW + colW / 2;
          return (
            <g key={p}>
              <rect x={cx - 58} y={18} width={116} height={34} rx={8} fill="#131c36" stroke="rgba(56, 189, 248, 0.55)" />
              <text x={cx} y={39} textAnchor="middle" fill="#f8fafc" fontSize={12} fontWeight={700}>
                {p.slice(0, 16)}
              </text>
              <line x1={cx} y1={52} x2={cx} y2={svgH - 20} stroke="rgba(148, 163, 184, 0.3)" strokeDasharray="4 4" />
            </g>
          );
        })}
        {parsed.messages.map((m, idx) => {
          const i1 = pIndex.get(m.from) ?? 0;
          const i2 = pIndex.get(m.to) ?? 0;
          const x1 = pad + i1 * colW + colW / 2;
          const x2 = pad + i2 * colW + colW / 2;
          const y = 84 + idx * 46;
          return (
            <g key={idx}>
              <line
                x1={x1}
                y1={y}
                x2={x2}
                y2={y}
                stroke="#a78bfa"
                strokeWidth={1.8}
                strokeDasharray={m.dashed ? '5 4' : undefined}
                markerEnd="url(#bnvSeqArrow)"
              />
              <text x={(x1 + x2) / 2} y={y - 7} textAnchor="middle" fill="#e2e8f0" fontSize={11}>
                {m.label.slice(0, 36)}
              </text>
            </g>
          );
        })}
      </svg>
    );
  }

  if (parsed.kind === 'er') {
    const boxW = 148;
    const boxH = 44;
    const gap = 80;
    const pad = 28;
    const svgW = Math.max(360, pad * 2 + parsed.entities.length * (boxW + gap) - gap);
    const svgH = 160 + parsed.relations.length * 24;
    const eIdx = new Map(parsed.entities.map((e, i) => [e, i]));

    return (
      <svg viewBox={`0 0 ${svgW} ${svgH}`} className="bnv-mermaid-svg" role="img" aria-label="ER diagram">
        {parsed.relations.map((rel, idx) => {
          const i1 = eIdx.get(rel.left) ?? 0;
          const i2 = eIdx.get(rel.right) ?? 0;
          const x1 = pad + i1 * (boxW + gap) + boxW / 2;
          const x2 = pad + i2 * (boxW + gap) + boxW / 2;
          const y = 96 + idx * 24;
          return (
            <g key={idx}>
              <path d={`M ${x1} 72 L ${x1} ${y} L ${x2} ${y} L ${x2} 72`} fill="none" stroke="rgba(56, 189, 248, 0.7)" strokeWidth={1.6} />
              <text x={(x1 + x2) / 2} y={y - 5} textAnchor="middle" fill="#fde68a" fontSize={10.5}>
                {rel.cardinality} · {rel.label}
              </text>
            </g>
          );
        })}
        {parsed.entities.map((e, idx) => {
          const x = pad + idx * (boxW + gap);
          return (
            <g key={e} transform={`translate(${x}, 28)`}>
              <rect width={boxW} height={boxH} rx={8} fill="#131c36" stroke="rgba(251, 191, 36, 0.65)" strokeWidth={1.5} />
              <text x={boxW / 2} y={27} textAnchor="middle" fill="#f8fafc" fontSize={12.5} fontWeight={700}>
                {e.slice(0, 18)}
              </text>
            </g>
          );
        })}
      </svg>
    );
  }

  if (parsed.kind === 'mindmap') {
    const rowH = 38;
    const svgH = Math.max(120, 32 + parsed.nodes.length * rowH);
    const svgW = 540;
    return (
      <svg viewBox={`0 0 ${svgW} ${svgH}`} className="bnv-mermaid-svg" role="img" aria-label="Mind map diagram">
        {parsed.nodes.map((n, idx) => {
          const x = 24 + Math.min(n.depth, 5) * 34;
          const y = 18 + idx * rowH;
          const isRoot = n.depth === 0;
          return (
            <g key={idx} transform={`translate(${x}, ${y})`}>
              <rect
                width={Math.min(340, Math.max(130, n.label.length * 8 + 28))}
                height={28}
                rx={isRoot ? 14 : 8}
                fill={isRoot ? 'rgba(99, 102, 241, 0.32)' : 'rgba(19, 28, 54, 0.92)'}
                stroke={isRoot ? '#38bdf8' : 'rgba(139, 92, 246, 0.5)'}
              />
              <text x={14} y={18} fill="#f8fafc" fontSize={12} fontWeight={isRoot ? 700 : 500}>
                {n.label.slice(0, 40)}
              </text>
            </g>
          );
        })}
      </svg>
    );
  }

  if (parsed.kind === 'pie') {
    const total = parsed.slices.reduce((acc, s) => acc + s.value, 0) || 1;
  let angle = -Math.PI / 2;
  const cx = 110;
  const cy = 110;
  const r = 78;

  return (
    <svg viewBox="0 0 460 220" className="bnv-mermaid-svg" role="img" aria-label={parsed.title}>
      <text x={220} y={24} fill="#f8fafc" fontSize={13} fontWeight={700}>
        {parsed.title}
      </text>
      {parsed.slices.map((slice, idx) => {
        const sweep = (slice.value / total) * Math.PI * 2;
        const x1 = cx + r * Math.cos(angle);
        const y1 = cy + r * Math.sin(angle);
        angle += sweep;
        const x2 = cx + r * Math.cos(angle);
        const y2 = cy + r * Math.sin(angle);
        const largeArc = sweep > Math.PI ? 1 : 0;
        const color = PIE_COLORS[idx % PIE_COLORS.length];
        const pathData = `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;
        const pct = Math.round((slice.value / total) * 100);
        return (
          <g key={slice.label}>
            <path d={pathData} fill={color} stroke="#090f20" strokeWidth={2} />
            <rect x={220} y={44 + idx * 24} width={12} height={12} rx={3} fill={color} />
            <text x={240} y={54 + idx * 24} fill="#e2e8f0" fontSize={12}>
              {slice.label.slice(0, 22)} ({pct}%)
            </text>
          </g>
        );
      })}
    </svg>
  );
  }

  if (parsed.kind === 'class') {
    const cols = Math.min(3, Math.max(1, parsed.classes.length));
    const cardW = 190;
    const gapX = 36;
    const gapY = 34;
    const pad = 28;
    const cardHeights = parsed.classes.map((c) => 40 + Math.max(1, c.members.length) * 18 + 12);
    const rows = Math.ceil(parsed.classes.length / cols);
    const maxCardH = Math.max(...cardHeights, 86);
    const svgW = pad * 2 + cols * cardW + Math.max(0, cols - 1) * gapX;
    const svgH = pad * 2 + rows * maxCardH + Math.max(0, rows - 1) * gapY + (parsed.relations.length > 0 ? 36 : 0);

    const posMap = new Map<string, { x: number; y: number; h: number }>();
    parsed.classes.forEach((cls, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      posMap.set(cls.name, {
        x: pad + col * (cardW + gapX),
        y: pad + row * (maxCardH + gapY),
        h: cardHeights[idx],
      });
    });

    return (
      <svg
        viewBox={`0 0 ${Math.max(360, svgW)} ${Math.max(200, svgH)}`}
        className="bnv-mermaid-svg"
        role="img"
        aria-label="Class diagram"
      >
        <defs>
          <marker id="bnvClsArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,1 L7,4 L0,7 Z" fill="#a78bfa" />
          </marker>
        </defs>
        {parsed.relations.map((rel, idx) => {
          const from = posMap.get(rel.from);
          const to = posMap.get(rel.to);
          if (!from || !to) return null;
          const x1 = from.x + cardW / 2;
          const y1 = from.y + from.h / 2;
          const x2 = to.x + cardW / 2;
          const y2 = to.y + to.h / 2;
          return (
            <g key={`crel-${idx}`}>
              <line
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="rgba(167, 139, 250, 0.7)"
                strokeWidth={1.6}
                strokeDasharray={rel.symbol.includes('..') ? '5 4' : undefined}
                markerEnd="url(#bnvClsArrow)"
              />
              {rel.label && (
                <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 5} textAnchor="middle" fill="#cbd5e1" fontSize={10}>
                  {rel.label.slice(0, 18)}
                </text>
              )}
            </g>
          );
        })}
        {parsed.classes.map((cls) => {
          const p = posMap.get(cls.name)!;
          return (
            <g key={cls.name} transform={`translate(${p.x}, ${p.y})`}>
              <rect width={cardW} height={p.h} rx={10} fill="#0e1730" stroke="#6366f1" strokeWidth={1.5} />
              <rect width={cardW} height={32} rx={10} fill="rgba(99, 102, 241, 0.24)" />
              <text x={cardW / 2} y={21} textAnchor="middle" fill="#e0e7ff" fontSize={12.5} fontWeight={700}>
                {cls.name.slice(0, 22)}
              </text>
              {cls.members.slice(0, 8).map((m, mi) => (
                <text key={mi} x={10} y={50 + mi * 18} fill="#94a3b8" fontSize={11}>
                  {m.slice(0, 25)}
                </text>
              ))}
            </g>
          );
        })}
      </svg>
    );
  }

  if (parsed.kind === 'state') {
    const nodeW = 148;
    const nodeH = 44;
    const gapX = 52;
    const pad = 32;
    const cols = Math.min(4, Math.max(1, parsed.states.length));
    const rows = Math.ceil(parsed.states.length / cols);
    const gapY = 64;
    const svgW = pad * 2 + cols * nodeW + Math.max(0, cols - 1) * gapX;
    const svgH = pad * 2 + rows * nodeH + Math.max(0, rows - 1) * gapY;

    const coords = new Map<string, { x: number; y: number; cx: number; cy: number }>();
    parsed.states.forEach((st, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      const x = pad + col * (nodeW + gapX);
      const y = pad + row * (nodeH + gapY);
      coords.set(st, { x, y, cx: x + nodeW / 2, cy: y + nodeH / 2 });
    });

    return (
      <svg
        viewBox={`0 0 ${Math.max(360, svgW)} ${Math.max(180, svgH)}`}
        className="bnv-mermaid-svg"
        role="img"
        aria-label="State diagram"
      >
        <defs>
          <marker id="bnvStArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,1 L7,4 L0,7 Z" fill="#22d3ee" />
          </marker>
        </defs>
        {parsed.transitions.map((tr, idx) => {
          const f = coords.get(tr.from);
          const t = coords.get(tr.to);
          if (!f || !t) return null;
          return (
            <g key={`st-${idx}`}>
              <line
                x1={f.cx}
                y1={f.cy}
                x2={t.cx}
                y2={t.cy}
                stroke="rgba(34, 211, 238, 0.72)"
                strokeWidth={1.7}
                markerEnd="url(#bnvStArrow)"
              />
              {tr.label && (
                <g transform={`translate(${(f.cx + t.cx) / 2}, ${(f.cy + t.cy) / 2 - 6})`}>
                  <rect x={-38} y={-10} width={76} height={18} rx={5} fill="#080e1f" stroke="rgba(34, 211, 238, 0.35)" />
                  <text x={0} y={3} textAnchor="middle" fill="#bae6fd" fontSize={10}>
                    {tr.label.slice(0, 14)}
                  </text>
                </g>
              )}
            </g>
          );
        })}
        {parsed.states.map((st) => {
          const p = coords.get(st)!;
          const isEndpoint = st === 'Start' || st === 'End';
          return (
            <g key={st} transform={`translate(${p.x}, ${p.y})`}>
              <rect
                width={nodeW}
                height={nodeH}
                rx={isEndpoint ? 22 : 12}
                fill={isEndpoint ? '#172554' : '#0f172a'}
                stroke={isEndpoint ? '#fbbf24' : '#38bdf8'}
                strokeWidth={1.6}
              />
              <text x={nodeW / 2} y={nodeH / 2 + 4} textAnchor="middle" fill="#f1f5f9" fontSize={12} fontWeight={600}>
                {st.slice(0, 20)}
              </text>
            </g>
          );
        })}
      </svg>
    );
  }

  // Gantt chart
  const rowH = 34;
  const labelW = 190;
  const trackW = 360;
  const pad = 24;
  const svgW = pad * 2 + labelW + trackW;
  const svgH = 56 + parsed.tasks.length * rowH + pad;
  const count = Math.max(1, parsed.tasks.length);

  return (
    <svg
      viewBox={`0 0 ${svgW} ${Math.max(180, svgH)}`}
      className="bnv-mermaid-svg"
      role="img"
      aria-label="Gantt chart"
    >
      <text x={pad} y={28} fill="#f8fafc" fontSize={14} fontWeight={700}>
        {parsed.title}
      </text>
      {parsed.tasks.map((task, idx) => {
        const y = 48 + idx * rowH;
        const segW = Math.max(54, Math.round(trackW / Math.min(4, count)));
        const barX = pad + labelW + Math.round((idx / count) * (trackW - segW));
        const color =
          task.status === 'crit'
            ? '#f59e0b'
            : task.status === 'done'
              ? '#34d399'
              : task.status === 'active'
                ? '#22d3ee'
                : '#818cf8';
        return (
          <g key={`${task.label}-${idx}`}>
            <text x={pad} y={y + 16} fill="#cbd5e1" fontSize={11.5}>
              {task.label.slice(0, 26)}
            </text>
            <rect x={pad + labelW} y={y + 3} width={trackW} height={20} rx={6} fill="rgba(15, 23, 42, 0.75)" />
            <rect x={barX} y={y + 4} width={segW} height={18} rx={5} fill={color} opacity={0.9} />
          </g>
        );
      })}
    </svg>
  );
}

const MermaidDiagramBlock: React.FC<MermaidDiagramBlockProps> = ({ source }) => {
  const [copied, setCopied] = useState(false);
  const [showSource, setShowSource] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragStartRef = useRef<{ x: number; y: number; origX: number; origY: number } | null>(null);
  const svgContainerRef = useRef<HTMLDivElement>(null);

  const parsed = useMemo(() => parseMermaidDiagram(source), [source]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(source);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // ignore clipboard errors
    }
  };

  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleDownloadSvg = () => {
    const svgEl = svgContainerRef.current?.querySelector('svg');
    if (!svgEl) return;
    const serializer = new XMLSerializer();
    const svgStr = serializer.serializeToString(svgEl);
    const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `brainova-diagram-${parsed.valid ? parsed.kind : 'chart'}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadPng = () => {
    const svgEl = svgContainerRef.current?.querySelector('svg');
    if (!svgEl) return;
    const serializer = new XMLSerializer();
    const svgStr = serializer.serializeToString(svgEl);
    const img = new Image();
    const svgBlob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);
    img.onload = () => {
      const vb = svgEl.viewBox?.baseVal;
      const w = (vb && vb.width ? vb.width : svgEl.clientWidth || 720) * 2;
      const h = (vb && vb.height ? vb.height : svgEl.clientHeight || 420) * 2;
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#070c1b';
        ctx.fillRect(0, 0, w, h);
        ctx.drawImage(img, 0, 0, w, h);
        const pngUrl = canvas.toDataURL('image/png');
        const a = document.createElement('a');
        a.href = pngUrl;
        a.download = `brainova-diagram-${parsed.valid ? parsed.kind : 'chart'}.png`;
        a.click();
      }
      URL.revokeObjectURL(url);
    };
    img.src = url;
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    setDragging(true);
    dragStartRef.current = { x: e.clientX, y: e.clientY, origX: pan.x, origY: pan.y };
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging || !dragStartRef.current) return;
    setPan({
      x: dragStartRef.current.origX + (e.clientX - dragStartRef.current.x),
      y: dragStartRef.current.origY + (e.clientY - dragStartRef.current.y),
    });
  };

  const handlePointerUp = () => {
    setDragging(false);
    dragStartRef.current = null;
  };

  return (
    <>
      <div className="bnv-mermaid-card">
        <div className="bnv-mermaid-toolbar bnv-mermaid-toolbar--controls-only">
          <div className="bnv-mermaid-actions">
            {parsed.valid && !showSource && (
              <>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setZoom((z) => Math.max(0.6, Number((z - 0.2).toFixed(2))))}
                  aria-label="Zoom out diagram"
                  title="Zoom out"
                >
                  <ZoomOut size={14} />
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setZoom((z) => Math.min(2.4, Number((z + 0.2).toFixed(2))))}
                  aria-label="Zoom in diagram"
                  title="Zoom in"
                >
                  <ZoomIn size={14} />
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={handleResetView}
                  aria-label="Fit diagram to screen"
                  title="Fit to screen"
                >
                  <RotateCcw size={13} />
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={handleDownloadSvg}
                  aria-label="Download diagram SVG"
                  title="Download SVG"
                >
                  <Download size={13} />
                  <span>SVG</span>
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={handleDownloadPng}
                  aria-label="Download diagram PNG"
                  title="Download PNG"
                >
                  <Download size={13} />
                  <span>PNG</span>
                </button>
              </>
            )}
            {parsed.valid && (
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setShowSource((s) => !s)}
                aria-label="Toggle Mermaid source"
              >
                <Code2 size={14} />
                <span>{showSource ? 'Diagram' : 'Source'}</span>
              </button>
            )}
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={handleCopy}
              aria-label="Copy Mermaid source"
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
            {parsed.valid && (
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setExpanded(true)}
                aria-label="Expand diagram"
              >
                <Maximize2 size={14} />
                <span>Fullscreen</span>
              </button>
            )}
          </div>
        </div>

        {!parsed.valid ? (
          <div className="bnv-mermaid-fallback">
            <p className="bnv-mermaid-error">{parsed.error}</p>
            <pre className="bnv-code-pre">
              <code>{source}</code>
            </pre>
          </div>
        ) : showSource ? (
          <pre className="bnv-code-pre">
            <code>{source}</code>
          </pre>
        ) : (
          <div
            ref={svgContainerRef}
            className={`bnv-mermaid-canvas ${dragging ? 'is-dragging' : ''}`}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerUp}
            onPointerLeave={handlePointerUp}
          >
            <div
              className="bnv-mermaid-stage"
              style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
            >
              {renderSvgContent(parsed)}
            </div>
          </div>
        )}
      </div>

      {expanded && parsed.valid && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Expanded Mermaid Diagram"
          onClick={() => setExpanded(false)}
        >
          <div className="bnv-mermaid-modal" onClick={(e) => e.stopPropagation()}>
            <div className="bnv-mermaid-toolbar bnv-mermaid-toolbar--controls-only">
              <div className="bnv-mermaid-actions">
                <button type="button" className="btn btn-ghost btn-sm" onClick={handleDownloadSvg}>
                  <Download size={14} />
                  <span>SVG</span>
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={handleDownloadPng}>
                  <Download size={14} />
                  <span>PNG</span>
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setExpanded(false)}
                >
                  <X size={14} />
                  <span>Close</span>
                </button>
              </div>
            </div>
            <div className="bnv-mermaid-modal-body">{renderSvgContent(parsed)}</div>
          </div>
        </div>
      )}
    </>
  );
};

export default MermaidDiagramBlock;

