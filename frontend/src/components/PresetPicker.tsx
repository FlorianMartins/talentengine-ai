// Searchable gallery of reference roles (47 presets): instant client-side search + family chips + count.
import { useMemo, useState, type ReactNode } from "react";
import { Check, SearchX, Search } from "lucide-react";
import { FAMILIES, type Family } from "../api/types";
import { usePrefs } from "../lib/prefs";
import { cx } from "../lib/format";
import { searchPresets } from "../lib/presetSearch";
import { FamilyIcon } from "./feedback";

export interface PickerItem {
  id: string;
  family: Family;
  title: string;
  summary: string;
  keywords?: string;
  /** criterion labels (shown as chips and searched) */
  criteria?: string[];
}

export function PresetPicker({
  items,
  selected,
  onSelect,
  lead,
  empty,
  idPrefix = "pp",
}: {
  items: PickerItem[];
  selected: string;
  onSelect: (id: string) => void;
  /** optional first card (e.g. "blank profile"), shown only without an active search */
  lead?: ReactNode;
  /** what to show when nothing matches */
  empty: ReactNode;
  idPrefix?: string;
}) {
  const { t } = usePrefs();
  const u = t.presetsUi;
  const [q, setQ] = useState("");
  const [family, setFamily] = useState<Family | "">("");
  const found = useMemo(() => searchPresets(items, q), [items, q]);
  const visible = family ? found.filter((p) => p.family === family) : found;
  const counts = useMemo(() => {
    const m = new Map<Family, number>();
    for (const p of found) m.set(p.family, (m.get(p.family) ?? 0) + 1);
    return m;
  }, [found]);
  const families = FAMILIES.filter((f) => items.some((p) => p.family === f));

  return (
    <div className="stack">
      <div className="preset-search">
        <div className="input-icon">
          <Search size={18} aria-hidden="true" />
          <input
            id={`${idPrefix}-q`}
            className="input"
            type="search"
            value={q}
            placeholder={u.searchPh}
            aria-label={u.searchLabel}
            aria-controls={`${idPrefix}-list`}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <span className="small muted num" role="status" aria-live="polite">
          {u.count(visible.length, items.length)}
        </span>
      </div>
      <div className="family-chips" role="group" aria-label={u.familiesLabel}>
        <button type="button" className={cx("fchip", !family && "on")} aria-pressed={!family} onClick={() => setFamily("")}>
          {u.all} <span className="num">{found.length}</span>
        </button>
        {families.map((f) => (
          <button
            key={f}
            type="button"
            className={cx("fchip", family === f && "on")}
            aria-pressed={family === f}
            disabled={!counts.get(f)}
            onClick={() => setFamily(family === f ? "" : f)}
          >
            {t.families[f]} <span className="num">{counts.get(f) ?? 0}</span>
          </button>
        ))}
      </div>
      {visible.length === 0 ? (
        <div className="card">
          <div className="empty" style={{ padding: "32px 16px" }}>
            <div className="empty-icon">
              <SearchX size={24} aria-hidden="true" />
            </div>
            {empty}
          </div>
        </div>
      ) : (
        <div id={`${idPrefix}-list`} className="preset-grid try-presets">
          {!q && !family && lead}
          {visible.map((p) => (
            <button key={p.id} type="button" className="preset" aria-pressed={selected === p.id} onClick={() => onSelect(p.id)}>
              <div className="row" style={{ gap: 10 }}>
                <FamilyIcon family={p.family} size={16} />
                <b style={{ flex: 1 }}>{p.title}</b>
                {selected === p.id && <Check size={16} aria-hidden="true" style={{ color: "var(--accent-text)" }} />}
              </div>
              <p>{p.summary}</p>
              {p.criteria && p.criteria.length > 0 && (
                <span className="chips">
                  {p.criteria.map((c) => (
                    <span key={c} className="chip chip-plain">
                      <span>{c}</span>
                    </span>
                  ))}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
