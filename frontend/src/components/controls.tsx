// Form controls: segmented control, labelled range slider, switch, tag input, drop zone.
import { useId, useRef, useState, type DragEvent, type KeyboardEvent, type ReactNode } from "react";
import { UploadCloud, X } from "lucide-react";
import { cx } from "../lib/format";
import { useT } from "../lib/prefs";

// ------------------------------------------------------------------ segmented (radio group)

interface SegOption<V extends string> {
  value: V;
  label: string;
}

export function Segmented<V extends string>({
  options,
  value,
  onChange,
  label,
  className,
}: {
  options: SegOption<V>[];
  value: V;
  onChange: (v: V) => void;
  label: string;
  className?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: KeyboardEvent, i: number) => {
    const dir = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!dir) return;
    e.preventDefault();
    const next = (i + dir + options.length) % options.length;
    const opt = options[next];
    if (opt) {
      onChange(opt.value);
      refs.current[next]?.focus();
    }
  };
  return (
    <div className={cx("seg", className)} role="radiogroup" aria-label={label}>
      {options.map((o, i) => (
        <button
          key={o.value}
          ref={(el) => (refs.current[i] = el)}
          type="button"
          role="radio"
          data-v={o.value}
          aria-checked={o.value === value}
          tabIndex={o.value === value ? 0 : -1}
          onClick={() => onChange(o.value)}
          onKeyDown={(e) => onKey(e, i)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ range

interface RangeProps {
  label: ReactNode;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  format?: (v: number) => string;
  ticks?: string[];
  activeTick?: number;
  hint?: ReactNode;
  disabled?: boolean;
  ariaLabel?: string;
}

export function RangeField({
  label,
  value,
  min,
  max,
  step,
  onChange,
  format,
  ticks,
  activeTick,
  hint,
  disabled,
  ariaLabel,
}: RangeProps) {
  const id = useId();
  const fill = ((value - min) / (max - min)) * 100;
  const text = format ? format(value) : String(value);
  return (
    <div className="range">
      <div className="range-head">
        <label className="label" htmlFor={id}>
          {label}
        </label>
        <output className="range-value" htmlFor={id}>
          {text}
        </output>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-valuetext={text}
        style={{ ["--fill" as string]: `${fill}%` }}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {ticks && (
        <div className="range-ticks" aria-hidden="true">
          {ticks.map((tk, i) => (
            <span key={i} className={cx(i === activeTick && "on")}>
              {tk}
            </span>
          ))}
        </div>
      )}
      {hint && <p className="hint">{hint}</p>}
    </div>
  );
}

// ------------------------------------------------------------------ switch

export function SwitchRow({
  checked,
  onChange,
  label,
  hint,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: ReactNode;
  hint?: ReactNode;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className="switch-row">
      <button
        id={id}
        type="button"
        role="switch"
        className="switch"
        aria-checked={checked}
        aria-describedby={hint ? `${id}-h` : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
      >
        <span className="sr-only">{label}</span>
      </button>
      <label className="switch-text" htmlFor={id}>
        <span className="label">{label}</span>
        {hint && (
          <span id={`${id}-h`} className="hint" style={{ display: "block", marginTop: 2 }}>
            {hint}
          </span>
        )}
      </label>
    </div>
  );
}

// ------------------------------------------------------------------ tag input

export function TagInput({
  value,
  onChange,
  placeholder,
  label,
  id,
}: {
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  label: string;
  id?: string;
}) {
  const t = useT();
  const [draft, setDraft] = useState("");
  const commit = () => {
    const parts = draft
      .split(/[,;\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (!parts.length) return;
    const next = [...value];
    for (const p of parts) if (!next.some((x) => x.toLowerCase() === p.toLowerCase())) next.push(p);
    onChange(next);
    setDraft("");
  };
  return (
    <div className="tags">
      {value.map((tag) => (
        <span key={tag} className="tag">
          {tag}
          <button
            type="button"
            aria-label={`${t.common.remove} ${tag}`}
            onClick={() => onChange(value.filter((x) => x !== tag))}
          >
            <X size={12} aria-hidden="true" />
          </button>
        </span>
      ))}
      <input
        id={id}
        value={draft}
        aria-label={label}
        placeholder={value.length ? "" : placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            commit();
          } else if (e.key === "Backspace" && !draft && value.length) {
            onChange(value.slice(0, -1));
          }
        }}
      />
    </div>
  );
}

// ------------------------------------------------------------------ drop zone

export function DropZone({
  accept,
  multiple,
  onFiles,
  hint,
  label,
}: {
  accept: string;
  multiple?: boolean;
  onFiles: (files: File[]) => void;
  hint?: ReactNode;
  label: string;
}) {
  const t = useT();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length) onFiles(multiple ? files : files.slice(0, 1));
  };
  return (
    <div
      className={cx("dropzone", over && "is-over")}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
    >
      <UploadCloud size={24} aria-hidden="true" />
      <div>
        {t.apply.drop}{" "}
        <button type="button" className="link-btn" onClick={() => input.current?.click()}>
          {t.apply.browse}
        </button>
      </div>
      {hint && <div className="hint">{hint}</div>}
      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        aria-label={label}
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length) onFiles(files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
