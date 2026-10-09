// "My AI model": the recruiter's own key (bring your own key) for the judge and the assistant of the tests they send.
import { useEffect, useState, type FormEvent } from "react";
import { Bot, ExternalLink, Loader2, PlugZap, Save, ShieldAlert, Trash2 } from "lucide-react";
import { api } from "../api/client";
import type { FreeModel, LlmProviderId, MyLlm } from "../api/types";
import { usePrefs, useToast } from "../lib/prefs";
import { Skeleton } from "./feedback";

export function ModelKeyPanel() {
  const { t } = usePrefs();
  const b = t.byok;
  const toast = useToast();
  const [data, setData] = useState<MyLlm | null>(null);
  const [provider, setProvider] = useState<LlmProviderId>("openrouter");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [key, setKey] = useState("");
  const [judge, setJudge] = useState(true);
  const [assistant, setAssistant] = useState(false);
  const [free, setFree] = useState<FreeModel[] | null>(null);
  const [freeError, setFreeError] = useState(false);
  const [busy, setBusy] = useState<"" | "save" | "test" | "delete">("");

  const load = async () => {
    try {
      const d = await api.myLlm();
      setData(d);
      if (d.settings) {
        setProvider(d.settings.provider);
        setModel(d.settings.model);
        setBaseUrl(d.settings.provider === "custom" ? d.settings.base_url : "");
        setJudge(d.settings.use_for_judge);
        setAssistant(d.settings.use_for_assistant);
      }
    } catch (e) {
      toast.push("error", e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (provider !== "openrouter" || free || freeError) return;
    api.freeModels().then(
      (m) => {
        setFree(m);
        const first = m[0]?.id;
        if (first) setModel((current) => current || first); // never replace a saved choice
      },
      () => setFreeError(true),
    );
  }, [provider, free, freeError]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy("save");
    try {
      await api.saveMyLlm({
        provider,
        model: model.trim(),
        base_url: provider === "custom" ? baseUrl.trim() : undefined,
        api_key: key.trim() || undefined,
        use_for_judge: judge,
        use_for_assistant: assistant,
      });
      setKey("");
      toast.push("success", b.saved);
      await load();
    } catch (err) {
      toast.push("error", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  };

  const test = async () => {
    setBusy("test");
    try {
      const r = await api.testMyLlm();
      toast.push("success", b.testOk(r.model));
    } catch (err) {
      toast.push("error", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  };

  const remove = async () => {
    setBusy("delete");
    try {
      await api.deleteMyLlm();
      toast.push("success", b.removed);
      setModel("");
      await load();
    } catch (err) {
      toast.push("error", err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  };

  const saved = data?.settings ?? null;
  const help = data?.providers.find((p) => p.id === provider)?.help;

  return (
    <form className="panel stack" aria-labelledby="s-llm" onSubmit={save}>
      <h2 id="s-llm" className="panel-title">
        <Bot size={18} aria-hidden="true" />
        {b.title}
      </h2>
      <p className="small muted" style={{ lineHeight: 1.6 }}>
        {b.lead}
      </p>
      {!data ? (
        <Skeleton h={120} />
      ) : (
        <>
          <p className={saved ? "callout callout-ok small" : "callout small"}>
            <span>
              {saved
                ? b.current(b.providers[saved.provider] ?? saved.provider, saved.model, saved.key_hint)
                : b.none}
            </span>
          </p>
          <div className="field">
            <label className="label" htmlFor="llm-provider">
              {b.provider}
            </label>
            <select id="llm-provider" className="input" value={provider} onChange={(e) => setProvider(e.target.value as LlmProviderId)}>
              {data.providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {b.providers[p.id] ?? p.label}
                </option>
              ))}
            </select>
          </div>
          {provider === "custom" && (
            <div className="field">
              <label className="label" htmlFor="llm-url">
                {b.baseUrl}
              </label>
              <input id="llm-url" className="input mono" type="url" required placeholder="https://…/v1" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
            </div>
          )}
          <div className="field">
            <label className="label" htmlFor="llm-model">
              {b.model}
            </label>
            {provider === "openrouter" && free && free.length > 0 ? (
              <select id="llm-model" className="input mono" value={model} onChange={(e) => setModel(e.target.value)}>
                {!free.some((m) => m.id === model) && model && <option value={model}>{model}</option>}
                <optgroup label={b.freeModels}>
                  {free.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                      {m.context_length ? ` · ${Math.round(m.context_length / 1000)}k` : ""}
                    </option>
                  ))}
                </optgroup>
              </select>
            ) : (
              <input id="llm-model" className="input mono" required value={model} onChange={(e) => setModel(e.target.value)} />
            )}
            <p className="xs faint">
              {provider === "openrouter" && !free && !freeError ? b.freeLoading : provider === "openrouter" && freeError ? b.freeUnavailable : b.modelHint}
            </p>
          </div>
          <div className="field">
            <label className="label" htmlFor="llm-key">
              {b.key}
            </label>
            <input
              id="llm-key"
              className="input mono"
              type="password"
              autoComplete="off"
              required={!saved}
              value={key}
              placeholder={saved ? saved.key_hint : ""}
              onChange={(e) => setKey(e.target.value)}
            />
            <p className="xs faint row" style={{ gap: 8, flexWrap: "wrap" }}>
              <span>{saved ? b.keyKeep(saved.key_hint) : b.stored}</span>
              {help && (
                <a href={help} target="_blank" rel="noopener noreferrer" className="row" style={{ gap: 4 }}>
                  {b.getKey} <ExternalLink size={12} aria-hidden="true" />
                </a>
              )}
            </p>
          </div>
          <label className="row small" style={{ gap: 8 }}>
            <input type="checkbox" checked={judge} onChange={(e) => setJudge(e.target.checked)} />
            {b.forJudge}
          </label>
          <label className="row small" style={{ gap: 8 }}>
            <input type="checkbox" checked={assistant} onChange={(e) => setAssistant(e.target.checked)} />
            {b.forAssistant}
          </label>
          <p className="callout callout-warn xs">
            <ShieldAlert size={14} aria-hidden="true" />
            <span>
              {b.privacy} {b.quota}
            </span>
          </p>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <button className="btn btn-primary" type="submit" disabled={busy !== ""}>
              {busy === "save" ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <Save size={16} aria-hidden="true" />}
              {b.save}
            </button>
            {saved && (
              <>
                <button className="btn" type="button" onClick={test} disabled={busy !== ""}>
                  {busy === "test" ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <PlugZap size={16} aria-hidden="true" />}
                  {b.test}
                </button>
                <button className="btn btn-danger" type="button" onClick={remove} disabled={busy !== ""}>
                  <Trash2 size={16} aria-hidden="true" />
                  {b.remove}
                </button>
              </>
            )}
          </div>
        </>
      )}
    </form>
  );
}
