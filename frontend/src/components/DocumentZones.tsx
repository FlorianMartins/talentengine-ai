// Upload zones by document category: CV, LinkedIn profile (PDF), diplomas, certifications, other documents.
// Files are appended incrementally and removed one by one. Used by the sandbox and the recruiter Apply page.
import { Award, FileText, FolderOpen, GraduationCap, Info, Linkedin, X } from "lucide-react";
import { usePrefs, useToast } from "../lib/prefs";
import { DropZone } from "./controls";

export interface DocSet {
  cv: File | null;
  linkedin: File | null;
  degrees: File[];
  certifications: File[];
  documents: File[];
}

export const EMPTY_DOCS: DocSet = { cv: null, linkedin: null, degrees: [], certifications: [], documents: [] };

export function hasAnyDoc(d: DocSet): boolean {
  return Boolean(d.cv || d.linkedin || d.degrees.length || d.certifications.length || d.documents.length);
}

interface Props {
  value: DocSet;
  onChange: (d: DocSet) => void;
  /** max files per multi-file category */
  maxPerCategory: number;
  maxMb: number;
  /** accepted extensions, e.g. /\.(pdf|docx|md|txt)$/i, and the matching `accept` attribute */
  ext: RegExp;
  accept: string;
}

function sizeLabel(b: number): string {
  return b > 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;
}

function FileRow({ file, onRemove }: { file: File; onRemove: () => void }) {
  const { t } = usePrefs();
  return (
    <li className="file-item">
      <FileText size={16} aria-hidden="true" style={{ color: "var(--accent-text)", flex: "none" }} />
      <span className="truncate small" style={{ flex: 1 }}>
        {file.name}
      </span>
      <span className="xs faint num">{sizeLabel(file.size)}</span>
      <button type="button" className="btn btn-ghost btn-icon btn-sm" aria-label={t.apply.fileRemove(file.name)} onClick={onRemove}>
        <X size={15} aria-hidden="true" />
      </button>
    </li>
  );
}

export function DocumentZones({ value, onChange, maxPerCategory, maxMb, ext, accept }: Props) {
  const { t } = usePrefs();
  const d = t.docs;
  const toast = useToast();
  const ok = (files: File[]) =>
    files.filter((f) => {
      if (!ext.test(f.name)) return toast.push("warning", t.pub.sandbox.profile.badType(f.name)), false;
      if (f.size > maxMb * 1024 * 1024) return toast.push("warning", t.pub.sandbox.profile.tooBig(f.name, maxMb)), false;
      return true;
    });
  const set = (patch: Partial<DocSet>) => onChange({ ...value, ...patch });

  const single = (key: "cv" | "linkedin", label: string, hint: string, acc: string) => {
    const file = value[key];
    return file ? (
      <ul className="file-list">
        <FileRow file={file} onRemove={() => set({ [key]: null } as Partial<DocSet>)} />
      </ul>
    ) : (
      <DropZone accept={acc} label={label} hint={hint} onFiles={(f) => set({ [key]: ok(f)[0] ?? null } as Partial<DocSet>)} />
    );
  };
  const multi = (key: "degrees" | "certifications" | "documents", label: string, hint: string) => {
    const files = value[key];
    return (
      <div className="stack-sm">
        {files.length > 0 && (
          <ul className="file-list">
            {files.map((f, i) => (
              <FileRow key={`${f.name}-${i}`} file={f} onRemove={() => set({ [key]: files.filter((_, j) => j !== i) } as Partial<DocSet>)} />
            ))}
          </ul>
        )}
        {files.length < maxPerCategory && (
          <DropZone
            accept={accept}
            multiple
            label={label}
            hint={hint}
            onFiles={(f) => set({ [key]: [...files, ...ok(f)].slice(0, maxPerCategory) } as Partial<DocSet>)}
          />
        )}
        <span className="xs faint num" aria-live="polite">
          {files.length} / {maxPerCategory}
        </span>
      </div>
    );
  };
  const limit = d.limit(maxPerCategory, maxMb);

  return (
    <>
      <div className="grid-2" style={{ alignItems: "start" }}>
        <section className="panel" aria-labelledby="dz-cv">
          <h3 id="dz-cv" className="panel-title" style={{ fontSize: 16 }}>
            <FileText size={18} aria-hidden="true" />
            {d.cv}
          </h3>
          {single("cv", d.cv, t.pub.sandbox.profile.cvHint(maxMb), accept)}
        </section>
        <section className="panel" aria-labelledby="dz-li">
          <h3 id="dz-li" className="panel-title" style={{ fontSize: 16 }}>
            <Linkedin size={18} aria-hidden="true" />
            {d.linkedin} <span className="opt label" style={{ fontWeight: 400 }}>({t.common.optional})</span>
          </h3>
          <p className="callout callout-neutral small" style={{ padding: "10px 12px" }}>
            <Info size={15} aria-hidden="true" />
            <span>{d.linkedinHow}</span>
          </p>
          {single("linkedin", d.linkedin, d.linkedinHint, ".pdf,.txt,application/pdf,text/plain")}
          <p className="hint">{d.linkedinNote}</p>
        </section>
      </div>
      <div className="grid-2" style={{ alignItems: "start" }}>
        <section className="panel" aria-labelledby="dz-cred">
          <div>
            <h3 id="dz-cred" className="panel-title" style={{ fontSize: 16 }}>
              <GraduationCap size={18} aria-hidden="true" />
              {d.degrees} · {d.certifications} <span className="opt label" style={{ fontWeight: 400 }}>({t.common.optional})</span>
            </h3>
            <p className="panel-hint">{d.credHint}</p>
          </div>
          <span className="label">
            <GraduationCap size={14} aria-hidden="true" /> {d.degrees}
          </span>
          {multi("degrees", d.degrees, limit)}
          <span className="label">
            <Award size={14} aria-hidden="true" /> {d.certifications}
          </span>
          {multi("certifications", d.certifications, limit)}
        </section>
        <section className="panel" aria-labelledby="dz-docs">
          <div>
            <h3 id="dz-docs" className="panel-title" style={{ fontSize: 16 }}>
              <FolderOpen size={18} aria-hidden="true" />
              {d.others} <span className="opt label" style={{ fontWeight: 400 }}>({t.common.optional})</span>
            </h3>
            <p className="panel-hint">{d.othersHint}</p>
          </div>
          {multi("documents", d.others, limit)}
        </section>
      </div>
    </>
  );
}
