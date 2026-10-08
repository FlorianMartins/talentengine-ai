// /settings/integrations — ATS connectors (Greenhouse, Lever, Ashby, generic webhook). Admin only.
import { useState, type FormEvent } from "react";
import { AlertTriangle, BookOpen, ClipboardCopy, Loader2, Plug, Plus, ShieldAlert, Trash2, Webhook, X } from "lucide-react";
import { api, BASE_PATH } from "../api/client";
import type { AtsProvider, Integration } from "../api/types";
import { useAccess, useAsync, usePrefs, useToast } from "../lib/prefs";
import { dateTime } from "../lib/format";
import { PageHeader, useCrumbs } from "../components/Shell";
import { EmptyState, ErrorState, Modal, Skeleton } from "../components/feedback";
import { Segmented, SwitchRow } from "../components/controls";
import { REPO_URL } from "../components/PublicLayout";

const PROVIDERS: AtsProvider[] = ["greenhouse", "lever", "ashby", "generic"];
const PROVIDER_NAMES: Record<AtsProvider, string> = { greenhouse: "Greenhouse", lever: "Lever", ashby: "Ashby", generic: "Webhook" };
/** Secrets each provider needs (optional ones are marked in the labels). */
const SECRET_FIELDS: Record<AtsProvider, string[]> = {
  greenhouse: ["webhook_secret", "client_id", "client_secret", "user_id"],
  lever: ["webhook_secret", "api_key", "perform_as"],
  ashby: ["webhook_secret", "api_key"],
  generic: [],
};
const OPTIONAL = new Set(["user_id", "perform_as"]);

const webhookUrl = (path: string) => `${window.location.origin}${BASE_PATH}${path}`;

export function IntegrationsPage() {
  const { t, lang } = usePrefs();
  const it = t.integrations;
  const toast = useToast();
  const access = useAccess();
  const allowed = access.can("admin");
  const list = useAsync(() => (allowed ? api.integrations() : Promise.resolve([])), [allowed]);
  const jobs = useAsync(() => (allowed ? api.jobs() : Promise.resolve([])), [allowed]);
  const [created, setCreated] = useState<Integration | null>(null);
  const [toDelete, setToDelete] = useState<Integration | null>(null);
  const [deleting, setDeleting] = useState(false);
  useCrumbs([{ label: t.nav.settings, to: "/settings" }, { label: it.nav }]);

  if (access.mode === "loading") return <Skeleton h={300} r={14} />;
  if (!allowed) {
    return (
      <div className="card">
        <EmptyState icon={ShieldAlert} title={it.title}>
          {it.reserved}
        </EmptyState>
      </div>
    );
  }
  const remove = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await api.deleteIntegration(toDelete.id);
      toast.push("success", it.deleted);
      setToDelete(null);
      list.reload();
    } catch (e) {
      toast.error(e);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="page">
      <section className="hero">
        <PageHeader title={it.title} sub={it.subtitle} />
      </section>
      <div className="grid-2" style={{ alignItems: "start" }}>
        <div className="stack-lg">
          <section className="panel" aria-labelledby="int-list">
            <h2 id="int-list" className="panel-title">
              <Plug size={18} aria-hidden="true" />
              {it.list}
            </h2>
            {list.loading && !list.data ? (
              <Skeleton h={100} />
            ) : list.error ? (
              <ErrorState error={list.error} onRetry={list.reload} />
            ) : (list.data ?? []).length === 0 ? (
              <p className="small muted">{it.none}</p>
            ) : (
              <ul className="verif-list">
                {(list.data ?? []).map((c) => (
                  <li key={c.id} className="verif-item">
                    <div className="row wrap" style={{ gap: 8 }}>
                      <span className="chip chip-accent">
                        <span>{PROVIDER_NAMES[c.provider]}</span>
                      </span>
                      <b className="small">{c.name}</b>
                      <span className="hash">{c.id}</span>
                      <span className="spacer" />
                      <button className="btn btn-ghost btn-icon btn-sm" aria-label={it.delete(c.name)} title={it.delete(c.name)} onClick={() => setToDelete(c)}>
                        <Trash2 size={15} aria-hidden="true" />
                      </button>
                    </div>
                    <div className="field">
                      <span className="label xs">{it.webhookUrl}</span>
                      <CopyField value={webhookUrl(c.webhook_path)} id={`wh-${c.id}`} />
                    </div>
                    <p className="xs faint">
                      {Object.entries(c.job_mapping)
                        .map(([k, v]) => `${k} → ${v}`)
                        .join(" · ") || "—"}{" "}
                      · {c.created_by}, {dateTime(c.created_at, lang)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="panel is-secondary" aria-labelledby="int-how">
            <h2 id="int-how" className="panel-title">
              <BookOpen size={16} aria-hidden="true" />
              {it.howTo}
            </h2>
            <dl className="kv">
              {PROVIDERS.map((p) => (
                <div key={p} style={{ display: "contents" }}>
                  <dt>{PROVIDER_NAMES[p]}</dt>
                  <dd className="small">{it.howtos[p]}</dd>
                </div>
              ))}
            </dl>
            <a className="small" href={`${REPO_URL}/blob/main/docs/ATS_BRIDGE.md`} target="_blank" rel="noreferrer">
              {it.docLink}
            </a>
          </section>
        </div>
        <CreateForm
          jobs={(jobs.data ?? []).map((j) => ({ id: j.id, title: j.title }))}
          onCreated={(c) => {
            setCreated(c);
            list.reload();
          }}
        />
      </div>

      {created && (
        <Modal
          title={`${it.created} — ${created.name}`}
          onClose={() => setCreated(null)}
          footer={
            <button className="btn btn-primary" onClick={() => setCreated(null)}>
              {t.accounts.keyDone}
            </button>
          }
        >
          <div className="field">
            <span className="label">{it.webhookUrl}</span>
            <CopyField value={webhookUrl(created.webhook_path)} id="new-wh" />
          </div>
          {created.webhook_secret && (
            <>
              <p className="callout callout-warn" role="alert">
                <AlertTriangle size={16} aria-hidden="true" />
                <b>{it.secretOnce}</b>
              </p>
              <CopyField value={created.webhook_secret} id="new-secret" />
            </>
          )}
          <p className="hint">{it.howtos[created.provider]}</p>
        </Modal>
      )}
      {toDelete && (
        <Modal
          title={it.delete(toDelete.name)}
          onClose={() => setToDelete(null)}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setToDelete(null)}>
                {t.common.cancel}
              </button>
              <button className="btn btn-danger is-solid" onClick={remove} disabled={deleting}>
                {deleting ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Trash2 size={16} aria-hidden="true" />}
                {t.accounts.deleteDo}
              </button>
            </>
          }
        >
          <p className="small">{it.deleteConfirm(toDelete.name)}</p>
        </Modal>
      )}
    </div>
  );
}

function CopyField({ value, id }: { value: string; id: string }) {
  const { t } = usePrefs();
  const toast = useToast();
  return (
    <div className="row" style={{ gap: 6 }}>
      <input id={id} className="input mono" readOnly value={value} onFocus={(e) => e.target.select()} aria-label={value} />
      <button
        type="button"
        className="btn"
        onClick={() => void navigator.clipboard?.writeText(value).then(() => toast.push("success", t.common.copied)).catch(() => undefined)}
      >
        <ClipboardCopy size={16} aria-hidden="true" />
        {t.common.copy}
      </button>
    </div>
  );
}

function CreateForm({ jobs, onCreated }: { jobs: { id: string; title: string }[]; onCreated: (c: Integration) => void }) {
  const { t } = usePrefs();
  const it = t.integrations;
  const toast = useToast();
  const [provider, setProvider] = useState<AtsProvider>("greenhouse");
  const [name, setName] = useState("");
  const [rows, setRows] = useState<{ ats: string; job: string }[]>([{ ats: "", job: "" }]);
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState(false);
  const [notes, setNotes] = useState(true);
  const [days, setDays] = useState(30);
  const [busy, setBusy] = useState(false);
  const fields = SECRET_FIELDS[provider];
  const missing = fields.filter((f) => !OPTIONAL.has(f) && !secrets[f]?.trim());
  const valid = name.trim().length >= 2 && notice && missing.length === 0;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    setBusy(true);
    try {
      const job_mapping = Object.fromEntries(rows.filter((r) => r.ats.trim() && r.job).map((r) => [r.ats.trim(), r.job]));
      const secretsOut = Object.fromEntries(fields.filter((f) => secrets[f]?.trim()).map((f) => [f, secrets[f]!.trim()]));
      const c = await api.createIntegration({
        provider,
        name: name.trim(),
        job_mapping,
        secrets: secretsOut,
        candidate_notice_confirmed: notice,
        write_notes: notes,
        explanation_link_days: days,
      });
      onCreated(c);
      setName("");
      setSecrets({});
      setRows([{ ats: "", job: "" }]);
      setNotice(false);
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="panel" aria-labelledby="int-new" onSubmit={submit}>
      <h2 id="int-new" className="panel-title">
        <Webhook size={18} aria-hidden="true" />
        {it.create}
      </h2>
      <div className="field">
        <span className="label">{it.provider}</span>
        <Segmented<AtsProvider>
          label={it.provider}
          value={provider}
          onChange={(p) => {
            setProvider(p);
            setSecrets({});
          }}
          options={PROVIDERS.map((p) => ({ value: p, label: PROVIDER_NAMES[p] }))}
        />
      </div>
      <div className="field">
        <label htmlFor="int-name">{it.name}</label>
        <input id="int-name" className="input" maxLength={120} value={name} placeholder={it.namePh} onChange={(e) => setName(e.target.value)} />
      </div>
      <fieldset className="field" style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
        <legend className="label">{it.mapping}</legend>
        <p className="hint">{it.mappingHint}</p>
        {rows.map((r, i) => (
          <div key={i} className="map-row">
            <input
              className="input mono"
              aria-label={`${it.atsJob} ${i + 1}`}
              placeholder={it.atsJob}
              value={r.ats}
              onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, ats: e.target.value } : x)))}
            />
            <span aria-hidden="true">→</span>
            <select
              className="select"
              aria-label={`${t.compliance.colJob} ${i + 1}`}
              value={r.job}
              onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, job: e.target.value } : x)))}
            >
              <option value="">—</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title} · {j.id}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-ghost btn-icon btn-sm"
              aria-label={`${t.common.remove} ${i + 1}`}
              disabled={rows.length === 1}
              onClick={() => setRows(rows.filter((_, j) => j !== i))}
            >
              <X size={15} aria-hidden="true" />
            </button>
          </div>
        ))}
        <button type="button" className="btn btn-sm" style={{ alignSelf: "flex-start" }} onClick={() => setRows([...rows, { ats: "", job: "" }])}>
          <Plus size={14} aria-hidden="true" />
          {it.addRow}
        </button>
      </fieldset>
      <fieldset className="field" style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
        <legend className="label">{it.secrets}</legend>
        <p className="hint">{fields.length ? it.secretsHint : it.genericSecret}</p>
        {fields.map((f) => (
          <div key={f} className="field">
            <label htmlFor={`sec-${f}`} className="small">
              {it.secretLabels[f] ?? f}
            </label>
            <input
              id={`sec-${f}`}
              className="input mono"
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={secrets[f] ?? ""}
              onChange={(e) => setSecrets({ ...secrets, [f]: e.target.value })}
            />
          </div>
        ))}
      </fieldset>
      <SwitchRow checked={notes} onChange={setNotes} label={it.writeNotes} />
      <div className="field" style={{ maxWidth: 220 }}>
        <label htmlFor="int-days">{it.linkDays}</label>
        <input id="int-days" className="input num" type="number" min={1} max={90} value={days} onChange={(e) => setDays(Math.min(90, Math.max(1, Number(e.target.value) || 1)))} />
      </div>
      <label className="check">
        <input type="checkbox" checked={notice} onChange={(e) => setNotice(e.target.checked)} aria-describedby="int-notice-h" />
        <span>
          <b>{it.notice}</b>
          <span id="int-notice-h" className="hint" style={{ display: "block", marginTop: 2 }}>
            {it.noticeHint}
          </span>
        </span>
      </label>
      <div>
        <button className="btn btn-primary" type="submit" disabled={!valid || busy}>
          {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Plug size={16} aria-hidden="true" />}
          {it.save}
        </button>
      </div>
    </form>
  );
}
