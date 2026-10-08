// Hand-drawn SVG data visualisations: score ring, 3-axis radar, level meter, skill graph.
import { useEffect, useId, useMemo, useState } from "react";
import type { AxisWeights, SkillEdge } from "../api/types";
import { AXES } from "../api/types";
import { useT } from "../lib/prefs";
import { cx } from "../lib/format";

// ------------------------------------------------------------------ score ring

interface RingProps {
  value: number | null; // 0..100
  size?: number;
  stroke?: number;
  caption?: string;
  glow?: boolean;
  color?: string;
  label?: string; // accessible label
}

export function ScoreRing({ value, size = 64, stroke, caption, glow, color, label }: RingProps) {
  const sw = stroke ?? Math.max(4, Math.round(size / 13));
  const r = (size - sw) / 2;
  const c = 2 * Math.PI * r;
  const target = value === null ? 0 : Math.max(0, Math.min(100, value));
  // Animate from 0 on mount (CSS transition; disabled under prefers-reduced-motion).
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(target));
    return () => cancelAnimationFrame(id);
  }, [target]);
  const display = value === null ? "—" : Math.round(value).toString();
  return (
    <div
      className={cx("score-ring", glow && "glow")}
      style={{ width: size, height: size, ["--ring-color" as string]: color }}
      role="img"
      aria-label={label ?? (value === null ? "—" : `${value.toFixed(1)} %`)}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle className="ring-track" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={sw} />
        <circle
          className="ring-fill"
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          strokeWidth={sw}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - shown / 100)}
        />
      </svg>
      <div className="ring-label" aria-hidden="true">
        <span className="ring-value" style={{ fontSize: size * 0.3 }}>
          {display}
          {value !== null && <span className="ring-unit">%</span>}
        </span>
        {caption && <span className="ring-caption">{caption}</span>}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ radar (3 axes)

interface RadarProps {
  values: AxisWeights;
  max: number;
  size?: number;
  compare?: AxisWeights | null;
  showLabels?: boolean;
  label?: string;
}

export function Radar({ values, max, size = 120, compare, showLabels = true, label }: RadarProps) {
  const t = useT();
  const pad = showLabels ? 26 : 6;
  const cx0 = size / 2;
  const cy0 = size / 2 + (showLabels ? 4 : 0);
  const R = size / 2 - pad;
  // axis angles: top, bottom-right, bottom-left
  const angles = [-90, 30, 150].map((d) => (d * Math.PI) / 180);
  const pt = (i: number, v: number) => {
    const a = angles[i] ?? 0;
    const k = Math.max(0, Math.min(1, max > 0 ? v / max : 0));
    return [cx0 + Math.cos(a) * R * k, cy0 + Math.sin(a) * R * k] as const;
  };
  const poly = (v: AxisWeights) => AXES.map((ax, i) => pt(i, v[ax]).join(",")).join(" ");
  const ring = (k: number) => AXES.map((_, i) => pt(i, max * k).join(",")).join(" ");
  const desc = AXES.map((ax) => `${t.axes[ax]} ${values[ax].toFixed(2)}`).join(", ");
  return (
    <svg
      className="radar"
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={`${label ? `${label} — ` : ""}${desc}`}
    >
      {[0.25, 0.5, 0.75, 1].map((k) => (
        <polygon key={k} className="radar-grid" points={ring(k)} opacity={k === 1 ? 1 : 0.55} />
      ))}
      {AXES.map((_, i) => {
        const [x, y] = pt(i, max);
        return <line key={i} className="radar-axis" x1={cx0} y1={cy0} x2={x} y2={y} />;
      })}
      {compare && <polygon className="radar-shape alt" points={poly(compare)} />}
      <polygon className="radar-shape" points={poly(values)} />
      {AXES.map((ax, i) => {
        const [x, y] = pt(i, values[ax]);
        return <circle key={ax} className="radar-dot" cx={x} cy={y} r={2.5} />;
      })}
      {showLabels &&
        AXES.map((ax, i) => {
          const a = angles[i] ?? 0;
          const x = cx0 + Math.cos(a) * (R + 12);
          const y = cy0 + Math.sin(a) * (R + 12);
          const anchor = Math.abs(Math.cos(a)) < 0.2 ? "middle" : Math.cos(a) > 0 ? "end" : "start";
          return (
            <text
              key={ax}
              x={i === 0 ? x : Math.cos(a) > 0 ? size - 2 : 2}
              y={i === 0 ? y - 2 : y + 12}
              textAnchor={i === 0 ? "middle" : anchor}
            >
              {t.axes[ax]}
            </text>
          );
        })}
    </svg>
  );
}

// ------------------------------------------------------------------ level meter

interface MeterProps {
  value: number; // observed
  max: number;
  mark?: number; // required
  color?: string;
  label: string;
  scale?: boolean;
}

export function Meter({ value, max, mark, color, label, scale }: MeterProps) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(value));
    return () => cancelAnimationFrame(id);
  }, [value]);
  const pctOf = (v: number) => `${Math.max(0, Math.min(100, (v / max) * 100))}%`;
  return (
    <div>
      <div
        className="meter"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={Number(value.toFixed(2))}
      >
        <div className="meter-fill" style={{ width: pctOf(shown), ["--meter-color" as string]: color }} />
        {mark !== undefined && <div className="meter-mark" style={{ left: `calc(${pctOf(mark)} - 1px)` }} />}
      </div>
      {scale && (
        <div className="meter-scale" aria-hidden="true">
          {Array.from({ length: max + 1 }, (_, i) => (
            <span key={i}>{i}</span>
          ))}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ skill graph

export interface GraphNode {
  id: string;
  label: string;
  level: number; // 0..4
  source: "heuristic" | "llm" | "declared";
}

interface GraphProps {
  nodes: GraphNode[];
  edges: SkillEdge[];
  label: string;
}

/** Deterministic circle layout: nodes sorted by level, evenly spaced; labels outside the circle. */
export function SkillGraphView({ nodes, edges, label }: GraphProps) {
  const titleId = useId();
  const [hot, setHot] = useState<string | null>(null);
  const W = 880;
  const H = 440;
  const R = Math.min(160, 90 + nodes.length * 6);
  const cxm = W / 2;
  const cym = H / 2;
  const placed = useMemo(() => {
    const sorted = [...nodes].sort((a, b) => b.level - a.level || a.id.localeCompare(b.id));
    const n = Math.max(1, sorted.length);
    return new Map(
      sorted.map((node, i) => {
        const a = -Math.PI / 2 + (i / n) * Math.PI * 2;
        return [node.id, { node, a, x: cxm + Math.cos(a) * R, y: cym + Math.sin(a) * R }] as const;
      }),
    );
  }, [nodes, R, cxm, cym]);
  const neighbours = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const e of edges) {
      if (!m.has(e.source)) m.set(e.source, new Set());
      if (!m.has(e.target)) m.set(e.target, new Set());
      m.get(e.source)?.add(e.target);
      m.get(e.target)?.add(e.source);
    }
    return m;
  }, [edges]);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby={titleId}>
      <title id={titleId}>{label}</title>
      <circle cx={cxm} cy={cym} r={R} fill="none" stroke="var(--border)" strokeDasharray="2 6" />
      <g>
        {edges.map((e) => {
          const s = placed.get(e.source);
          const d = placed.get(e.target);
          if (!s || !d) return null;
          const isHot = hot !== null && (e.source === hot || e.target === hot);
          // gentle curve towards the centre
          const mx = (s.x + d.x) / 2 + (cxm - (s.x + d.x) / 2) * 0.35;
          const my = (s.y + d.y) / 2 + (cym - (s.y + d.y) / 2) * 0.35;
          return (
            <path
              key={`${e.source}-${e.target}`}
              className={cx("graph-edge", isHot && "is-hot")}
              d={`M${s.x},${s.y} Q${mx},${my} ${d.x},${d.y}`}
              fill="none"
              strokeWidth={Math.min(3, 0.8 + e.shared_artifacts.length * 0.6)}
              opacity={hot !== null && !isHot ? 0.25 : 1}
            />
          );
        })}
      </g>
      {[...placed.values()].map(({ node, a, x, y }) => {
        const r = 7 + Math.max(0, Math.min(4, node.level)) * 3.2;
        const cos = Math.cos(a);
        const lx = x + cos * (r + 8);
        const ly = y + Math.sin(a) * (r + 8) + 4;
        const anchor = Math.abs(cos) < 0.25 ? "middle" : cos > 0 ? "start" : "end";
        const dim = hot !== null && hot !== node.id && !neighbours.get(hot)?.has(node.id);
        const text = node.label.length > 34 ? `${node.label.slice(0, 33)}…` : node.label;
        return (
          <g
            key={node.id}
            className={cx(
              "graph-node",
              node.source === "llm" && "is-llm",
              node.source === "declared" && "is-declared",
              hot === node.id && "is-hot",
            )}
            tabIndex={0}
            opacity={dim ? 0.35 : 1}
            onMouseEnter={() => setHot(node.id)}
            onMouseLeave={() => setHot(null)}
            onFocus={() => setHot(node.id)}
            onBlur={() => setHot(null)}
            aria-label={`${node.label} — ${node.level.toFixed(2)} / 4`}
          >
            <title>{`${node.label} — ${node.level.toFixed(2)} / 4`}</title>
            <circle cx={x} cy={y} r={r} />
            <circle className="core" cx={x} cy={y} r={Math.max(2, r * 0.28)} />
            <text
              x={lx}
              y={Math.abs(cos) < 0.25 ? (Math.sin(a) < 0 ? y - r - 8 : y + r + 16) : ly}
              textAnchor={anchor}
            >
              {text}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
