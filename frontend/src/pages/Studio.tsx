import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowDown,
  ArrowUp,
  Braces,
  Check,
  ClipboardCopy,
  Coins,
  Download,
  FilePlus2,
  GraduationCap,
  Info,
  ListChecks,
  Loader2,
  Lock,
  Plus,
  Radar as RadarIcon,
  Save,
  Search,
  SlidersHorizontal,
  Trash2,
  Upload,
} from "lucide-react";
import { api } from "../api/client";
import { AXES, FAMILIES } from "../api/types";
import type { CatalogSkill, Criterion, Family, Importance, JobProfile, Locale, Preset } from "../api/types";
import { useAsync, usePrefs, useSystem, useToast } from "../lib/prefs";
import { cx, levelIndex } from "../lib/format";
import { PageHeader, useCrumbs } from "../components/Shell";
import { ErrorState, Gate, PageSkeleton, Skeleton } from "../components/feedback";
import { DpiaButton } from "../components/DpiaButton";
import { PresetPicker } from "../components/PresetPicker";
import { RangeField, Segmented, SwitchRow, TagInput } from "../components/controls";
import { Radar } from "../components/charts";

const MAX_CRITERIA = 40;

function blankProfile(locale: Locale): JobProfile {
  return {
    id: "",
    title: "",
    summary: "",
    family: "transversal",
    locale,
    criteria: [],
    axis_weights: { autonomy: 1, complexity: 1, reliability: 1 },
    credentials: { mode: "secondary", weight: 0.1, accepted: [] },
    funnel: {
      allow_cloud_llm: false,
      escalation_top_percent: 5,
      min_density_for_escalation: 0.35,
      max_input_tokens_per_candidate: 6000,
      max_output_tokens_per_candidate: 2000,
      job_budget_usd: 5,
    },
    privacy: { neutralize_gendered_terms: true, mask_school_names: true, quarantine_images_without_detector: true },
    version: 1,
  };
}

/** Fills any missing field with defaults (for presets and imported JSON). */
function normalize(raw: Partial<JobProfile>, locale: Locale): JobProfile {
  const b = blankProfile(locale);
  const criteria = (Array.isArray(raw.criteria) ? raw.criteria : []).map(
    (c): Criterion => ({
      skill_id: String(c.skill_id ?? ""),
      importance: (["essential", "important", "bonus"] as const).includes(c.importance) ? c.importance : "important",
      weight: typeof c.weight === "number" ? c.weight : 1,
      min_level: typeof c.min_level === "number" ? c.min_level : 2,
      axis_focus: c.axis_focus ? { ...b.axis_weights, ...c.axis_focus } : null,
      note: typeof c.note === "string" ? c.note : "",
    }),
  );
  return {
    ...b,
    ...raw,
    family: FAMILIES.includes(raw.family as Family) ? (raw.family as Family) : b.family,
    locale: raw.locale === "en" || raw.locale === "fr" ? raw.locale : locale,
    criteria,
    axis_weights: { ...b.axis_weights, ...(raw.axis_weights ?? {}) },
    credentials: { ...b.credentials, ...(raw.credentials ?? {}) },
    funnel: { ...b.funnel, ...(raw.funnel ?? {}) },
    privacy: { ...b.privacy, ...(raw.privacy ?? {}) },
  };
}

export function StudioPage() {
  const { id } = useParams();
  const editing = Boolean(id);
  const { t, lang } = usePrefs();
  const toast = useToast();
  const navigate = useNavigate();
  const { runtime } = useSystem();
  const maxCred = runtime?.max_credential_weight ?? 0.25;

  const skills = useAsync(() => api.skills(lang), [lang]);
  const presets = useAsync(() => (editing ? Promise.resolve([] as Preset[]) : api.presets(lang)), [lang, editing]);
  const existing = useAsync(() => (id ? api.job(id) : Promise.resolve(null)), [id]);

  const [draft, setDraft] = useState<JobProfile>(() => blankProfile(lang));
  const [presetId, setPresetId] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [triedSave, setTriedSave] = useState(false);

  useEffect(() => {
    if (existing.data) setDraft(normalize(existing.data, lang));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existing.data]);

  useCrumbs(
    editing
      ? [
          { label: t.nav.overview, to: "/" },
          { label: existing.data?.title ?? "…", to: `/jobs/${id}` },
          { label: t.studio.titleEdit },
        ]
      : [{ label: t.nav.overview, to: "/" }, { label: t.studio.titleNew }],
  );

  const catalog = useMemo(() => new Map((skills.data ?? []).map((s) => [s.id, s])), [skills.data]);

  const update = <K extends keyof JobProfile>(key: K, value: JobProfile[K]) => setDraft((d) => ({ ...d, [key]: value }));
  const updateCriterion = (i: number, patch: Partial<Criterion>) =>
    setDraft((d) => ({ ...d, criteria: d.criteria.map((c, j) => (j === i ? { ...c, ...patch } : c)) }));
  const moveCriterion = (i: number, dir: -1 | 1) =>
    setDraft((d) => {
      const next = [...d.criteria];
      const j = i + dir;
      if (j < 0 || j >= next.length) return d;
      const a = next[i];
      const b = next[j];
      if (!a || !b) return d;
      next[i] = b;
      next[j] = a;
      return { ...d, criteria: next };
    });
  const addCriterion = (skillId: string) =>
    setDraft((d) =>
      d.criteria.length >= MAX_CRITERIA || d.criteria.some((c) => c.skill_id === skillId)
        ? d
        : {
            ...d,
            criteria: [
              ...d.criteria,
              { skill_id: skillId, importance: "important", weight: 1, min_level: 2, axis_focus: null, note: "" },
            ],
          },
    );

  const errors = useMemo(() => {
    const out: string[] = [];
    if (draft.title.trim().length < 2) out.push(t.studio.vTitle);
    if (draft.criteria.length === 0) out.push(t.studio.vCriteria);
    if (draft.criteria.length > MAX_CRITERIA) out.push(t.studio.vTooMany);
    const ids = draft.criteria.map((c) => c.skill_id);
    if (new Set(ids).size !== ids.length) out.push(t.studio.vDuplicate);
    if (catalog.size) for (const sid of ids) if (!catalog.has(sid)) out.push(t.studio.vUnknown(sid));
    return out;
  }, [draft, catalog, t]);

  const save = async () => {
    setTriedSave(true);
    if (errors.length) return;
    setSaving(true);
    try {
      const body: JobProfile = {
        ...draft,
        title: draft.title.trim(),
        summary: draft.summary.trim(),
        credentials: { ...draft.credentials, weight: Math.min(draft.credentials.weight, maxCred) },
      };
      const saved = editing && id ? await api.updateJob(id, body) : await api.createJob({ ...body, id: "", version: 1 });
      toast.push("success", t.studio.saved, `${saved.title} · ${t.common.version(saved.version)}`);
      navigate(`/jobs/${saved.id}`);
    } catch (e) {
      toast.error(e);
    } finally {
      setSaving(false);
    }
  };

  if (editing && existing.loading && !existing.data) return <PageSkeleton />;
  if (editing && existing.error) return <ErrorState error={existing.error} onRetry={existing.reload} />;

  const sections = [
    { id: "basics", label: t.studio.sections.basics, icon: FilePlus2 },
    { id: "criteria", label: t.studio.sections.criteria, icon: ListChecks },
    { id: "axes", label: t.studio.sections.axes, icon: RadarIcon },
    { id: "credentials", label: t.studio.sections.credentials, icon: GraduationCap },
    { id: "funnel", label: t.studio.sections.funnel, icon: Coins },
    { id: "privacy", label: t.studio.sections.privacy, icon: Lock },
    { id: "json", label: t.studio.sections.json, icon: Braces },
  ];
  const escalated = Math.ceil((200 * draft.funnel.escalation_top_percent) / 100);
  const levelTicks = t.levels;

  return (
    <div className="page">
      <section className="hero">
        <PageHeader
          eyebrow={editing ? `${existing.data?.id ?? ""} · ${t.common.version(existing.data?.version ?? 1)}` : undefined}
          title={editing ? t.studio.titleEdit : t.studio.titleNew}
          sub={t.studio.subtitle}
        />
      </section>

      {!editing && (
        <section className="panel" aria-labelledby="presets-h">
          <div className="panel-head">
            <div>
              <h2 id="presets-h" className="panel-title">
                <SlidersHorizontal size={18} aria-hidden="true" />
                {t.studio.startFrom}
              </h2>
              <p className="panel-hint">{t.studio.startHint}</p>
            </div>
          </div>
          {presets.loading && !presets.data ? (
            <div className="preset-grid">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} h={110} r={12} />
              ))}
            </div>
          ) : presets.error ? (
            <ErrorState error={presets.error} onRetry={presets.reload} />
          ) : (
            <PresetPicker
              idPrefix="studio-presets"
              items={(presets.data ?? []).map((p) => ({
                ...p,
                criteria: p.job.criteria.map((c) => catalog.get(c.skill_id)?.label ?? c.skill_id),
              }))}
              selected={presetId}
              onSelect={(pid) => {
                const p = presets.data?.find((x) => x.id === pid);
                if (!p) return;
                setPresetId(pid);
                setDraft(normalize({ ...p.job, id: "" }, lang));
              }}
              lead={
                <button
                  type="button"
                  className="preset"
                  aria-pressed={presetId === "blank"}
                  onClick={() => {
                    setPresetId("blank");
                    setDraft(blankProfile(lang));
                  }}
                >
                  <span className="family-icon">
                    <Plus size={16} aria-hidden="true" />
                  </span>
                  <b>{t.studio.blank}</b>
                  <p>{t.studio.blankDesc}</p>
                </button>
              }
              empty={
                <>
                  <p>{t.presetsUi.noneStudio}</p>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => {
                      setPresetId("blank");
                      setDraft(blankProfile(lang));
                    }}
                  >
                    <Plus size={16} aria-hidden="true" />
                    {t.studio.blank}
                  </button>
                </>
              }
            />
          )}
        </section>
      )}

      <div className="studio">
        <nav className="studio-toc" aria-label={t.studio.jump}>
          {sections.map((s, i) => (
            <a key={s.id} href={`#sec-${s.id}`}>
              <span className="toc-num">{String(i + 1).padStart(2, "0")}</span>
              {s.label}
            </a>
          ))}
        </nav>

        <div className="stack-lg" style={{ minWidth: 0 }}>
          {/* ---------------------------------------------------------- basics */}
          <section id="sec-basics" className="panel" aria-labelledby="h-basics">
            <h2 id="h-basics" className="panel-title">
              <FilePlus2 size={18} aria-hidden="true" />
              {t.studio.sections.basics}
            </h2>
            <div className="grid-2">
              <div className="field">
                <label htmlFor="f-title">{t.studio.title}</label>
                <input
                  id="f-title"
                  className="input"
                  value={draft.title}
                  maxLength={160}
                  placeholder={t.studio.titlePh}
                  aria-invalid={triedSave && draft.title.trim().length < 2}
                  onChange={(e) => update("title", e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="f-family">{t.studio.family}</label>
                <select
                  id="f-family"
                  className="select"
                  value={draft.family}
                  onChange={(e) => update("family", e.target.value as Family)}
                >
                  {FAMILIES.map((f) => (
                    <option key={f} value={f}>
                      {t.families[f]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="field">
              <label htmlFor="f-summary">{t.studio.summary}</label>
              <textarea
                id="f-summary"
                className="textarea"
                style={{ minHeight: 72 }}
                maxLength={4000}
                value={draft.summary}
                placeholder={t.studio.summaryPh}
                onChange={(e) => update("summary", e.target.value)}
              />
            </div>
            <div className="field">
              <span className="label" id="f-locale">
                {t.studio.reportLang}
              </span>
              <Segmented<Locale>
                label={t.studio.reportLang}
                value={draft.locale}
                onChange={(v) => update("locale", v)}
                options={[
                  { value: "fr", label: "Français" },
                  { value: "en", label: "English" },
                ]}
              />
              <p className="hint">{t.studio.reportLangHint}</p>
            </div>
          </section>

          {/* ---------------------------------------------------------- criteria */}
          <section id="sec-criteria" className="panel" aria-labelledby="h-criteria">
            <div className="panel-head">
              <div>
                <h2 id="h-criteria" className="panel-title">
                  <ListChecks size={18} aria-hidden="true" />
                  {t.studio.sections.criteria}
                </h2>
                <p className="panel-hint">{t.studio.criteriaHint}</p>
              </div>
              <span className="hash">{t.studio.criteriaCount(draft.criteria.length, MAX_CRITERIA)}</span>
            </div>

            <SkillPicker
              skills={skills.data}
              loading={skills.loading}
              selected={new Set(draft.criteria.map((c) => c.skill_id))}
              full={draft.criteria.length >= MAX_CRITERIA}
              onAdd={addCriterion}
            />

            {draft.criteria.length === 0 ? (
              <p className="callout callout-neutral">
                <Info size={16} aria-hidden="true" />
                <span>{t.studio.noCriteria}</span>
              </p>
            ) : (
              <ol className="crit-list">
                {draft.criteria.map((c, i) => {
                  const skill = catalog.get(c.skill_id);
                  const label = skill?.label ?? c.skill_id;
                  return (
                    <li key={c.skill_id} className="crit">
                      <div className="crit-head">
                        <span className="crit-num">{i + 1}</span>
                        <div className="crit-title">
                          <b>{label}</b>
                          <span>{skill?.statement ?? (skills.data ? t.studio.unknownSkill : "")}</span>
                        </div>
                        <div className="crit-tools">
                          <button
                            type="button"
                            className="btn btn-ghost btn-icon btn-sm"
                            aria-label={`${t.common.moveUp} — ${label}`}
                            disabled={i === 0}
                            onClick={() => moveCriterion(i, -1)}
                          >
                            <ArrowUp size={15} aria-hidden="true" />
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost btn-icon btn-sm"
                            aria-label={`${t.common.moveDown} — ${label}`}
                            disabled={i === draft.criteria.length - 1}
                            onClick={() => moveCriterion(i, 1)}
                          >
                            <ArrowDown size={15} aria-hidden="true" />
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost btn-icon btn-sm"
                            aria-label={t.studio.removeCriterion(label)}
                            onClick={() => setDraft((d) => ({ ...d, criteria: d.criteria.filter((_, j) => j !== i) }))}
                          >
                            <Trash2 size={15} aria-hidden="true" />
                          </button>
                        </div>
                      </div>
                      <div className="crit-body">
                        <div className="field">
                          <span className="label">{t.studio.importance}</span>
                          <Segmented<Importance>
                            className="tone-importance"
                            label={`${t.studio.importance} — ${label}`}
                            value={c.importance}
                            onChange={(v) => updateCriterion(i, { importance: v })}
                            options={(["essential", "important", "bonus"] as const).map((v) => ({
                              value: v,
                              label: t.importance[v],
                            }))}
                          />
                        </div>
                        <RangeField
                          label={t.studio.weight}
                          ariaLabel={`${t.studio.weight} — ${label}`}
                          value={c.weight}
                          min={0}
                          max={5}
                          step={0.25}
                          format={(v) => `×${v.toFixed(2)}`}
                          onChange={(v) => updateCriterion(i, { weight: v })}
                          hint={t.studio.weightHint}
                        />
                        <RangeField
                          label={t.studio.minLevel}
                          ariaLabel={`${t.studio.minLevel} — ${label}`}
                          value={c.min_level}
                          min={0}
                          max={4}
                          step={0.25}
                          format={(v) => `${v.toFixed(2)} · ${levelTicks[levelIndex(v)] ?? ""}`}
                          ticks={levelTicks}
                          activeTick={levelIndex(c.min_level)}
                          onChange={(v) => updateCriterion(i, { min_level: v })}
                        />
                      </div>
                      <div className="crit-extra">
                        <div className="field">
                          <label htmlFor={`note-${c.skill_id}`}>
                            {t.studio.note} <span className="opt">({t.common.optional})</span>
                          </label>
                          <input
                            id={`note-${c.skill_id}`}
                            className="input"
                            maxLength={500}
                            value={c.note}
                            placeholder={t.studio.notePh}
                            onChange={(e) => updateCriterion(i, { note: e.target.value })}
                          />
                        </div>
                        <div className="stack-sm">
                          <SwitchRow
                            checked={c.axis_focus !== null}
                            onChange={(on) => updateCriterion(i, { axis_focus: on ? { ...draft.axis_weights } : null })}
                            label={t.studio.axisFocus}
                            hint={t.studio.axisFocusHint}
                          />
                          {c.axis_focus && (
                            <div className="axis-focus">
                              {AXES.map((ax) => (
                                <RangeField
                                  key={ax}
                                  label={<span className="small">{t.axes[ax]}</span>}
                                  ariaLabel={`${t.axes[ax]} — ${label}`}
                                  value={c.axis_focus?.[ax] ?? 1}
                                  min={0}
                                  max={Math.max(5, c.axis_focus?.[ax] ?? 0)}
                                  step={0.25}
                                  format={(v) => v.toFixed(2)}
                                  onChange={(v) =>
                                    updateCriterion(i, {
                                      axis_focus: { ...(c.axis_focus ?? draft.axis_weights), [ax]: v },
                                    })
                                  }
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>

          {/* ---------------------------------------------------------- axes */}
          <section id="sec-axes" className="panel" aria-labelledby="h-axes">
            <div>
              <h2 id="h-axes" className="panel-title">
                <RadarIcon size={18} aria-hidden="true" />
                {t.studio.sections.axes}
              </h2>
              <p className="panel-hint">{t.studio.axesHint}</p>
            </div>
            <div className="axes-layout">
              <div className="stack">
                {AXES.map((ax) => (
                  <div key={ax} className="axis-row">
                    <RangeField
                      label={t.axes[ax]}
                      value={draft.axis_weights[ax]}
                      min={0}
                      max={Math.max(5, draft.axis_weights[ax])}
                      step={0.25}
                      format={(v) => v.toFixed(2)}
                      onChange={(v) => update("axis_weights", { ...draft.axis_weights, [ax]: v })}
                      hint={t.axes[`${ax}Desc` as const]}
                    />
                  </div>
                ))}
              </div>
              <div className="radar-wrap">
                <Radar
                  values={draft.axis_weights}
                  max={Math.max(1, ...AXES.map((a) => draft.axis_weights[a]))}
                  size={230}
                  label={t.studio.radarLabel}
                />
              </div>
            </div>
          </section>

          {/* ---------------------------------------------------------- credentials */}
          <section id="sec-credentials" className="panel" aria-labelledby="h-cred">
            <h2 id="h-cred" className="panel-title">
              <GraduationCap size={18} aria-hidden="true" />
              {t.studio.sections.credentials}
            </h2>
            <div className="field">
              <span className="label">{t.studio.credMode}</span>
              <Segmented<"ignore" | "secondary">
                label={t.studio.credMode}
                value={draft.credentials.mode}
                onChange={(v) => update("credentials", { ...draft.credentials, mode: v })}
                options={[
                  { value: "secondary", label: t.studio.credSecondary },
                  { value: "ignore", label: t.studio.credIgnore },
                ]}
              />
            </div>
            <p className="callout callout-neutral">
              <Info size={16} aria-hidden="true" />
              <span>
                {draft.credentials.mode === "ignore"
                  ? t.studio.credIgnoredCopy
                  : t.studio.credCopy(`${Math.round(maxCred * 100)} %`)}
              </span>
            </p>
            <RangeField
              label={t.studio.credWeight}
              value={Math.min(draft.credentials.weight, maxCred)}
              min={0}
              max={maxCred}
              step={0.01}
              disabled={draft.credentials.mode === "ignore"}
              format={(v) => `${Math.round(v * 100)} % / ${Math.round(maxCred * 100)} % max`}
              onChange={(v) => update("credentials", { ...draft.credentials, weight: Math.min(v, maxCred) })}
            />
            <div className="field">
              <label htmlFor="f-accepted">{t.studio.credAccepted}</label>
              <TagInput
                id="f-accepted"
                label={t.studio.credAccepted}
                value={draft.credentials.accepted}
                placeholder={t.studio.credAcceptedPh}
                onChange={(v) => update("credentials", { ...draft.credentials, accepted: v })}
              />
              <p className="hint">{t.studio.credAcceptedHint}</p>
            </div>
          </section>

          {/* ---------------------------------------------------------- funnel */}
          <section id="sec-funnel" className="panel" aria-labelledby="h-funnel">
            <h2 id="h-funnel" className="panel-title">
              <Coins size={18} aria-hidden="true" />
              {t.studio.sections.funnel}
            </h2>
            <SwitchRow
              checked={draft.funnel.allow_cloud_llm}
              onChange={(v) => update("funnel", { ...draft.funnel, allow_cloud_llm: v })}
              label={t.studio.allowCloud}
              hint={t.studio.allowCloudHint}
            />
            <div className={cx("callout", draft.funnel.allow_cloud_llm ? "" : "callout-ok")}>
              <Info size={16} aria-hidden="true" />
              <span>
                {draft.funnel.allow_cloud_llm ? t.studio.funnelHint(escalated, 200) : t.studio.funnelOff}
              </span>
            </div>
            <fieldset disabled={!draft.funnel.allow_cloud_llm} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }} className="stack">
              <div className="grid-2">
                <RangeField
                  label={t.studio.topPct}
                  value={draft.funnel.escalation_top_percent}
                  min={1}
                  max={50}
                  step={1}
                  disabled={!draft.funnel.allow_cloud_llm}
                  format={(v) => `${v} %`}
                  onChange={(v) => update("funnel", { ...draft.funnel, escalation_top_percent: v })}
                />
                <RangeField
                  label={t.studio.minDensity}
                  value={draft.funnel.min_density_for_escalation}
                  min={0}
                  max={1}
                  step={0.05}
                  disabled={!draft.funnel.allow_cloud_llm}
                  format={(v) => v.toFixed(2)}
                  hint={t.studio.minDensityHint}
                  onChange={(v) => update("funnel", { ...draft.funnel, min_density_for_escalation: v })}
                />
              </div>
              <div className="grid-3">
                <NumberField
                  id="f-maxin"
                  label={t.studio.maxIn}
                  value={draft.funnel.max_input_tokens_per_candidate}
                  min={500}
                  max={200000}
                  step={500}
                  onChange={(v) => update("funnel", { ...draft.funnel, max_input_tokens_per_candidate: v })}
                />
                <NumberField
                  id="f-maxout"
                  label={t.studio.maxOut}
                  value={draft.funnel.max_output_tokens_per_candidate}
                  min={256}
                  max={32000}
                  step={256}
                  onChange={(v) => update("funnel", { ...draft.funnel, max_output_tokens_per_candidate: v })}
                />
                <NumberField
                  id="f-budget"
                  label={t.studio.budget}
                  value={draft.funnel.job_budget_usd}
                  min={0}
                  max={10000}
                  step={0.5}
                  onChange={(v) => update("funnel", { ...draft.funnel, job_budget_usd: v })}
                />
              </div>
            </fieldset>
          </section>

          {/* ---------------------------------------------------------- privacy */}
          <section id="sec-privacy" className="panel" aria-labelledby="h-privacy">
            <h2 id="h-privacy" className="panel-title">
              <Lock size={18} aria-hidden="true" />
              {t.studio.sections.privacy}
            </h2>
            <SwitchRow
              checked={draft.privacy.neutralize_gendered_terms}
              onChange={(v) => update("privacy", { ...draft.privacy, neutralize_gendered_terms: v })}
              label={t.studio.neutralize}
              hint={t.studio.neutralizeHint}
            />
            <SwitchRow
              checked={draft.privacy.mask_school_names}
              onChange={(v) => update("privacy", { ...draft.privacy, mask_school_names: v })}
              label={t.studio.maskSchools}
              hint={t.studio.maskSchoolsHint}
            />
            <SwitchRow
              checked={draft.privacy.quarantine_images_without_detector}
              onChange={(v) => update("privacy", { ...draft.privacy, quarantine_images_without_detector: v })}
              label={t.studio.quarantine}
              hint={t.studio.quarantineHint}
            />
          </section>

          {/* ---------------------------------------------------------- json */}
          <JsonPanel draft={draft} onApply={(d) => setDraft(normalize(d, lang))} />

          {editing && existing.data && (
            <p className="callout callout-neutral">
              <Info size={16} aria-hidden="true" />
              <span>{t.studio.versionNote(existing.data.version)}</span>
            </p>
          )}

          <div className="validation" role="region" aria-label={t.studio.validation}>
            {triedSave && errors.length > 0 ? (
              <div style={{ flex: 1, minWidth: 0 }} role="alert">
                <b className="small">{t.studio.validation}</b>
                <ul>
                  {errors.map((e) => (
                    <li key={e}>{e}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="small muted" style={{ flex: 1, minWidth: 0 }}>
                <b style={{ color: "var(--text)" }}>{draft.title || "—"}</b>
                {" · "}
                {t.studio.criteriaCount(draft.criteria.length, MAX_CRITERIA)}
              </div>
            )}
            {editing && id && existing.data && <DpiaButton jobId={id} locale={existing.data.locale} />}
            <Gate perm="write">
              {(ok) => (
                <button className="btn btn-primary" onClick={save} disabled={saving || !ok}>
                  {saving ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Save size={16} aria-hidden="true" />}
                  {editing ? t.studio.saveEdit : t.studio.saveNew}
                </button>
              )}
            </Gate>
          </div>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ number field

function NumberField({
  id,
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        className="input num"
        type="number"
        inputMode="decimal"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => {
          const v = Number(e.target.value);
          if (!Number.isNaN(v)) onChange(Math.min(max, Math.max(min, v)));
        }}
      />
    </div>
  );
}

// ------------------------------------------------------------------ skill picker

function SkillPicker({
  skills,
  loading,
  selected,
  full,
  onAdd,
}: {
  skills: CatalogSkill[] | null;
  loading: boolean;
  selected: Set<string>;
  full: boolean;
  onAdd: (id: string) => void;
}) {
  const { t } = usePrefs();
  const [q, setQ] = useState("");
  const [family, setFamily] = useState<Family | "">("");
  const groups = useMemo(() => {
    const needle = q
      .trim()
      .toLowerCase()
      .normalize("NFD")
      .replace(/\p{Diacritic}/gu, "");
    const norm = (s: string) =>
      s
        .toLowerCase()
        .normalize("NFD")
        .replace(/\p{Diacritic}/gu, "");
    const matches = (skills ?? []).filter(
      (s) =>
        (!family || s.family === family) &&
        (!needle || norm(`${s.label} ${s.statement} ${s.id}`).includes(needle)),
    );
    const byFamily = new Map<Family, CatalogSkill[]>();
    for (const s of matches) {
      const arr = byFamily.get(s.family) ?? [];
      arr.push(s);
      byFamily.set(s.family, arr);
    }
    return FAMILIES.filter((f) => byFamily.has(f)).map((f) => [f, byFamily.get(f) ?? []] as const);
  }, [skills, q, family]);

  return (
    <div className="picker">
      <div className="picker-bar">
        <div className="input-icon">
          <Search size={16} aria-hidden="true" />
          <input
            className="input"
            type="search"
            value={q}
            placeholder={t.studio.pickerPh}
            aria-label={t.studio.pickerPh}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <select
          className="select"
          value={family}
          aria-label={t.studio.family}
          onChange={(e) => setFamily(e.target.value as Family | "")}
        >
          <option value="">{t.studio.pickerAll}</option>
          {FAMILIES.map((f) => (
            <option key={f} value={f}>
              {t.families[f]}
            </option>
          ))}
        </select>
      </div>
      <div className="picker-list">
        {loading && !skills ? (
          <div className="stack-sm" style={{ padding: 8 }}>
            <Skeleton h={36} />
            <Skeleton h={36} />
            <Skeleton h={36} />
          </div>
        ) : groups.length === 0 ? (
          <p className="small muted" style={{ padding: 12 }}>
            {t.studio.pickerEmpty}
          </p>
        ) : (
          groups.map(([f, list]) => (
            <div key={f} role="group" aria-label={t.families[f]}>
              <div className="picker-group eyebrow">{t.families[f]}</div>
              {list.map((s) => {
                const added = selected.has(s.id);
                return (
                  <button
                    key={s.id}
                    type="button"
                    className="picker-item"
                    disabled={added || full}
                    onClick={() => onAdd(s.id)}
                    aria-label={added ? `${s.label} — ${t.studio.pickerAdded}` : t.studio.addSkill(s.label)}
                    title={full && !added ? t.studio.pickerMax : undefined}
                  >
                    {added ? <Check size={16} aria-hidden="true" /> : <Plus size={16} aria-hidden="true" />}
                    <span className="pi-text">
                      <b>{s.label}</b>
                      <span>{s.statement}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ JSON panel

function JsonPanel({ draft, onApply }: { draft: JobProfile; onApply: (d: Partial<JobProfile>) => void }) {
  const { t } = usePrefs();
  const toast = useToast();
  const pretty = useMemo(() => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { created_at: _c, updated_at: _u, ...rest } = draft;
    return JSON.stringify(rest, null, 2);
  }, [draft]);
  const [text, setText] = useState(pretty);
  const [dirty, setDirty] = useState(false);
  const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!dirty) setText(pretty);
  }, [pretty, dirty]);

  const apply = (raw: string) => {
    try {
      const parsed = JSON.parse(raw) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("object expected");
      onApply(parsed as Partial<JobProfile>);
      setDirty(false);
      setErr("");
      toast.push("success", t.studio.jsonApplied);
    } catch (e) {
      setErr(`${t.studio.jsonInvalid} — ${e instanceof Error ? e.message : String(e)}`);
    }
  };
  const exportFile = () => {
    const blob = new Blob([pretty], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    const slug = (draft.title || "job-profile").toLowerCase().replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "");
    a.download = `${slug || "job-profile"}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

  return (
    <section id="sec-json" className="panel" aria-labelledby="h-json">
      <div className="panel-head">
        <div>
          <h2 id="h-json" className="panel-title">
            <Braces size={18} aria-hidden="true" />
            {t.studio.sections.json}
          </h2>
          <p className="panel-hint">{t.studio.jsonHint}</p>
        </div>
        <div className="row wrap" style={{ gap: 6 }}>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => {
              void navigator.clipboard?.writeText(pretty).then(() => toast.push("info", t.common.copied));
            }}
          >
            <ClipboardCopy size={14} aria-hidden="true" />
            {t.common.copy}
          </button>
          <button type="button" className="btn btn-sm" onClick={exportFile}>
            <Download size={14} aria-hidden="true" />
            {t.studio.exportJson}
          </button>
          <button type="button" className="btn btn-sm" onClick={() => fileRef.current?.click()}>
            <Upload size={14} aria-hidden="true" />
            {t.studio.importJson}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="sr-only"
            tabIndex={-1}
            aria-label={t.studio.importJson}
            onChange={async (e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (!f) return;
              const raw = await f.text();
              setText(raw);
              setDirty(true);
              apply(raw);
            }}
          />
        </div>
      </div>
      <textarea
        className="textarea mono"
        style={{ minHeight: 280, fontFamily: "var(--font-mono)" }}
        spellCheck={false}
        value={text}
        aria-label={t.studio.sections.json}
        aria-invalid={Boolean(err)}
        onChange={(e) => {
          setText(e.target.value);
          setDirty(true);
        }}
      />
      {err && (
        <p className="callout callout-warn" role="alert">
          <Info size={16} aria-hidden="true" />
          <span>{err}</span>
        </p>
      )}
      {dirty && (
        <div className="row wrap">
          <button type="button" className="btn btn-primary btn-sm" onClick={() => apply(text)}>
            <Check size={14} aria-hidden="true" />
            {t.studio.applyJson}
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setDirty(false);
              setErr("");
            }}
          >
            {t.common.cancel}
          </button>
        </div>
      )}
    </section>
  );
}
