import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import {
  CheckCircle2,
  ClipboardCopy,
  FileText,
  Github,
  ImageIcon,
  Info,
  Loader2,
  Lock,
  Plus,
  Send,
  Sparkles,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { api } from "../api/client";
import type { SubmissionResult } from "../api/types";
import { useAsync, usePrefs, useToast } from "../lib/prefs";
import { PageHeader, useCrumbs } from "../components/Shell";
import { ErrorState, PageSkeleton } from "../components/feedback";
import { DropZone } from "../components/controls";

const MAX_BYTES = 15 * 1024 * 1024;
const DOC_EXT = /\.(pdf|txt|md|markdown)$/i;
const IMG_TYPES = ["image/png", "image/jpeg", "image/webp"];

interface Item {
  title: string;
  description: string;
}
interface Img {
  file: File;
  caption: string;
  url: string;
}

function fmtSize(b: number): string {
  return b > 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;
}

export function ApplyPage() {
  const { id = "" } = useParams();
  const { t } = usePrefs();
  const toast = useToast();
  const job = useAsync(() => api.job(id), [id]);

  const [cv, setCv] = useState<File | null>(null);
  const [docs, setDocs] = useState<File[]>([]);
  const [github, setGithub] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const [images, setImages] = useState<Img[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [retention, setRetention] = useState(180);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);
  const [result, setResult] = useState<SubmissionResult | null>(null);

  useCrumbs([
    { label: t.nav.overview, to: "/" },
    { label: job.data?.title ?? "…", to: `/jobs/${id}` },
    { label: t.apply.title },
  ]);

  // free object URLs of image previews when leaving the page
  const imagesRef = useRef(images);
  imagesRef.current = images;
  useEffect(() => () => imagesRef.current.forEach((i) => URL.revokeObjectURL(i.url)), []);

  const acceptDocs = (files: File[]): File[] =>
    files.filter((f) => {
      if (f.size > MAX_BYTES) return toast.push("warning", t.apply.tooBig(f.name)), false;
      if (!DOC_EXT.test(f.name)) return toast.push("warning", t.apply.badType(f.name)), false;
      return true;
    });

  const urls = github
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
  const cleanItems = items.filter((i) => i.description.trim());
  const hasContent = Boolean(cv) || docs.length > 0 || urls.length > 0 || cleanItems.length > 0 || images.length > 0;
  const problems = useMemo(() => {
    const p: string[] = [];
    if (!hasContent) p.push(t.apply.needContent);
    if (!consent) p.push(t.apply.consentRequired);
    return p;
  }, [hasContent, consent, t]);

  const reset = () => {
    setCv(null);
    setDocs([]);
    setGithub("");
    setItems([]);
    setImages([]);
    setName("");
    setEmail("");
    setRetention(180);
    setConsent(false);
    setTried(false);
    setResult(null);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    try {
      const r = await api.submit(id, {
        consent,
        identity_name: name.trim(),
        identity_email: email.trim(),
        github_urls: urls,
        portfolio: cleanItems.map((i) => ({ title: i.title.trim(), description: i.description.trim() })),
        retention_days: retention,
        cv,
        documents: docs,
        images: images.map((i) => ({ file: i.file, caption: i.caption.trim() })),
      });
      setResult(r);
      window.scrollTo(0, 0);
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };

  if (job.loading && !job.data) return <PageSkeleton />;
  if (job.error) return <ErrorState error={job.error} onRetry={job.reload} />;

  if (result) {
    return (
      <div className="page">
        <section className="hero" aria-live="polite">
          <div className="empty" style={{ padding: "32px 8px" }}>
            <div className="empty-icon" style={{ color: "var(--ok-text)", background: "var(--ok-soft)" }}>
              <CheckCircle2 size={28} aria-hidden="true" />
            </div>
            <h1>{t.apply.successTitle}</h1>
            <div className="report-ref" style={{ color: "var(--accent-text)" }}>
              {result.candidate_ref}
            </div>
            <p>{t.apply.successBody}</p>
            <div className="row wrap" style={{ justifyContent: "center" }}>
              <button
                className="btn"
                onClick={() => void navigator.clipboard?.writeText(result.candidate_ref).then(() => toast.push("info", t.common.copied))}
              >
                <ClipboardCopy size={16} aria-hidden="true" />
                {t.common.copy}
              </button>
              <Link to={`/jobs/${id}`} className="btn btn-primary">
                {t.apply.toPipeline}
              </Link>
              <button className="btn btn-ghost" onClick={reset}>
                <Plus size={16} aria-hidden="true" />
                {t.apply.another}
              </button>
            </div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <form className="page" onSubmit={submit} noValidate>
      <section className="hero">
        <PageHeader eyebrow={`${t.apply.forJob} · ${job.data?.title ?? ""}`} title={t.apply.title} sub={t.apply.subtitle} />
      </section>

      <div className="grid-2" style={{ alignItems: "start" }}>
        {/* ------------------------------------------------ documents */}
        <section className="panel" aria-labelledby="ap-docs">
          <h2 id="ap-docs" className="panel-title">
            <FileText size={18} aria-hidden="true" />
            {t.apply.cv}
          </h2>
          {cv ? (
            <ul className="file-list">
              <FileRow file={cv} onRemove={() => setCv(null)} />
            </ul>
          ) : (
            <DropZone
              accept=".pdf,.txt,.md,.markdown,application/pdf,text/plain,text/markdown"
              label={t.apply.cv}
              hint={t.apply.cvHint}
              onFiles={(f) => setCv(acceptDocs(f)[0] ?? null)}
            />
          )}
          <div className="divider" />
          <h3 className="label">
            {t.apply.docs} <span className="opt">({t.common.optional})</span>
          </h3>
          <DropZone
            accept=".pdf,.txt,.md,.markdown,application/pdf,text/plain,text/markdown"
            multiple
            label={t.apply.docs}
            hint={t.apply.docsHint}
            onFiles={(f) => setDocs((d) => [...d, ...acceptDocs(f)].slice(0, 20))}
          />
          {docs.length > 0 && (
            <ul className="file-list">
              {docs.map((d, i) => (
                <FileRow key={`${d.name}-${i}`} file={d} onRemove={() => setDocs(docs.filter((_, j) => j !== i))} />
              ))}
            </ul>
          )}
        </section>

        <div className="stack-lg">
          {/* ------------------------------------------------ github */}
          <section className="panel" aria-labelledby="ap-gh">
            <h2 id="ap-gh" className="panel-title">
              <Github size={18} aria-hidden="true" />
              {t.apply.github}
            </h2>
            <div className="field">
              <label htmlFor="ap-gh-urls" className="sr-only">
                {t.apply.github}
              </label>
              <textarea
                id="ap-gh-urls"
                className="textarea mono"
                style={{ minHeight: 84, fontFamily: "var(--font-mono)" }}
                value={github}
                placeholder={t.apply.githubPh}
                spellCheck={false}
                onChange={(e) => setGithub(e.target.value)}
              />
              <p className="hint">{t.apply.githubHint}</p>
            </div>
          </section>

          {/* ------------------------------------------------ identity */}
          <section className="panel" aria-labelledby="ap-id">
            <h2 id="ap-id" className="panel-title">
              <UserRound size={18} aria-hidden="true" />
              {t.apply.identity}
            </h2>
            <p className="callout callout-neutral">
              <Lock size={16} aria-hidden="true" />
              <span>{t.apply.identityHint}</span>
            </p>
            <div className="grid-2">
              <div className="field">
                <label htmlFor="ap-name">{t.apply.name}</label>
                <input
                  id="ap-name"
                  className="input"
                  autoComplete="name"
                  maxLength={200}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="ap-email">{t.apply.email}</label>
                <input
                  id="ap-email"
                  className="input"
                  type="email"
                  autoComplete="email"
                  maxLength={200}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>
          </section>
        </div>
      </div>

      {/* ------------------------------------------------ portfolio */}
      <section className="panel" aria-labelledby="ap-pf">
        <div className="panel-head">
          <div>
            <h2 id="ap-pf" className="panel-title">
              <Sparkles size={18} aria-hidden="true" />
              {t.apply.portfolio}
            </h2>
            <p className="panel-hint">{t.apply.portfolioHint}</p>
          </div>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setItems([...items, { title: "", description: "" }])}
            disabled={items.length >= 30}
          >
            <Plus size={14} aria-hidden="true" />
            {t.apply.addItem}
          </button>
        </div>
        {items.length > 0 && (
          <ol className="crit-list">
            {items.map((it, i) => (
              <li key={i} className="crit" style={{ gap: 12 }}>
                <div className="crit-head" style={{ alignItems: "center" }}>
                  <span className="crit-num">{i + 1}</span>
                  <input
                    className="input"
                    style={{ flex: 1 }}
                    aria-label={`${t.apply.itemTitle} ${i + 1}`}
                    placeholder={t.apply.itemTitle}
                    maxLength={200}
                    value={it.title}
                    onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))}
                  />
                  <button
                    type="button"
                    className="btn btn-ghost btn-icon btn-sm"
                    aria-label={`${t.common.remove} ${it.title || `${t.apply.itemTitle} ${i + 1}`}`}
                    onClick={() => setItems(items.filter((_, j) => j !== i))}
                  >
                    <Trash2 size={15} aria-hidden="true" />
                  </button>
                </div>
                <textarea
                  className="textarea"
                  aria-label={`${t.apply.itemDesc} ${i + 1}`}
                  placeholder={t.apply.itemDesc}
                  maxLength={8000}
                  value={it.description}
                  onChange={(e) => setItems(items.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))}
                />
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* ------------------------------------------------ images */}
      <section className="panel" aria-labelledby="ap-img">
        <div>
          <h2 id="ap-img" className="panel-title">
            <ImageIcon size={18} aria-hidden="true" />
            {t.apply.images}
          </h2>
          <p className="panel-hint">{t.apply.imagesHint}</p>
        </div>
        <DropZone
          accept="image/png,image/jpeg,image/webp"
          multiple
          label={t.apply.images}
          onFiles={(files) => {
            const ok = files.filter((f) => {
              if (!IMG_TYPES.includes(f.type)) return toast.push("warning", t.apply.badType(f.name)), false;
              if (f.size > MAX_BYTES) return toast.push("warning", t.apply.tooBig(f.name)), false;
              return true;
            });
            setImages((imgs) => [...imgs, ...ok.map((file) => ({ file, caption: "", url: URL.createObjectURL(file) }))]);
          }}
        />
        {images.length > 0 && (
          <ul className="file-list">
            {images.map((img, i) => (
              <li key={img.url} className="file-item" style={{ flexWrap: "wrap" }}>
                <img className="thumb" src={img.url} alt="" />
                <div style={{ flex: "1 1 200px", minWidth: 0 }} className="stack-sm">
                  <span className="truncate small">{img.file.name}</span>
                  <input
                    className="input"
                    aria-label={`${t.apply.caption} — ${img.file.name}`}
                    placeholder={t.apply.caption}
                    maxLength={2000}
                    value={img.caption}
                    onChange={(e) =>
                      setImages(images.map((x, j) => (j === i ? { ...x, caption: e.target.value } : x)))
                    }
                  />
                </div>
                <button
                  type="button"
                  className="btn btn-ghost btn-icon btn-sm"
                  aria-label={t.apply.fileRemove(img.file.name)}
                  onClick={() => {
                    URL.revokeObjectURL(img.url);
                    setImages(images.filter((_, j) => j !== i));
                  }}
                >
                  <X size={15} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ------------------------------------------------ consent */}
      <section className="panel" aria-labelledby="ap-consent">
        <h2 id="ap-consent" className="panel-title">
          <Lock size={18} aria-hidden="true" />
          RGPD · GDPR
        </h2>
        <div className="field" style={{ maxWidth: 320 }}>
          <label htmlFor="ap-ret">{t.apply.retention}</label>
          <div className="row">
            <input
              id="ap-ret"
              className="input num"
              type="number"
              min={1}
              max={730}
              value={retention}
              onChange={(e) => setRetention(Math.min(730, Math.max(1, Number(e.target.value) || 1)))}
              aria-describedby="ap-ret-h"
            />
            <span className="small muted">{t.apply.days}</span>
          </div>
          <p id="ap-ret-h" className="hint">
            {t.apply.retentionHint(retention)}
          </p>
        </div>
        <label className="check" style={{ fontSize: 14 }}>
          <input
            type="checkbox"
            checked={consent}
            required
            aria-invalid={tried && !consent}
            onChange={(e) => setConsent(e.target.checked)}
          />
          <span>{t.apply.consent}</span>
        </label>
        {tried && problems.length > 0 && (
          <div className="callout callout-warn" role="alert">
            <Info size={16} aria-hidden="true" />
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="row wrap">
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Send size={16} aria-hidden="true" />}
            {busy ? t.apply.submitting : t.apply.submit}
          </button>
        </div>
      </section>
    </form>
  );
}

function FileRow({ file, onRemove }: { file: File; onRemove: () => void }) {
  const { t } = usePrefs();
  return (
    <li className="file-item">
      <FileText size={18} aria-hidden="true" style={{ color: "var(--accent-text)", flex: "none" }} />
      <span className="truncate" style={{ flex: 1 }}>
        {file.name}
      </span>
      <span className="xs faint num">{fmtSize(file.size)}</span>
      <button type="button" className="btn btn-ghost btn-icon btn-sm" aria-label={t.apply.fileRemove(file.name)} onClick={onRemove}>
        <X size={15} aria-hidden="true" />
      </button>
    </li>
  );
}
