// Sign-in screen of the recruiter area: shown instead of a page when the server needs an access key.
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { KeyRound, LogIn } from "lucide-react";
import { usePrefs, useSystem } from "../lib/prefs";

export function SignIn({ rejected }: { rejected: boolean }) {
  const { t, apiKey, setApiKey } = usePrefs();
  const { refresh } = useSystem();
  const s = t.signIn;
  const [key, setKey] = useState("");
  const [tried, setTried] = useState(false);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setApiKey(key.trim());
    setTried(true);
    refresh();
  };

  return (
    <div className="signin">
      <form className="panel stack" onSubmit={submit} aria-labelledby="signin-title">
        <h1 id="signin-title" className="panel-title">
          <KeyRound size={18} aria-hidden="true" />
          {s.title}
        </h1>
        <p className="small muted" style={{ lineHeight: 1.6 }}>
          {s.why}
        </p>
        <div className="field">
          <label className="label" htmlFor="signin-key">
            {s.label}
          </label>
          <input
            id="signin-key"
            className="input mono"
            type="password"
            autoComplete="current-password"
            placeholder="te_…"
            required
            value={key}
            onChange={(e) => setKey(e.target.value)}
            autoFocus
          />
          <p className="xs faint">{s.hint}</p>
        </div>
        {rejected && (tried || apiKey) && (
          <p className="callout callout-warn small" role="alert">
            <span>{s.rejected}</span>
          </p>
        )}
        <div>
          <button className="btn btn-primary" type="submit">
            <LogIn size={16} aria-hidden="true" />
            {s.submit}
          </button>
        </div>
        <p className="xs muted" style={{ lineHeight: 1.6 }}>
          {s.noAi} <Link to="/essai">{s.trial}</Link> · <Link to="/recruteurs">{s.recruiters}</Link>
        </p>
      </form>
    </div>
  );
}
