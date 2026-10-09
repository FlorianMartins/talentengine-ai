import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { dictionaries, type Dict, type Lang } from "../i18n";
import { getStored, setStored } from "./storage";
import { api, ApiError } from "../api/client";
import type { ChainVerification, Health, Me, Permission, Role, Runtime } from "../api/types";

export type Theme = "dark" | "light";

interface Prefs {
  theme: Theme;
  lang: Lang;
  reviewer: string;
  apiKey: string;
  t: Dict;
  setTheme: (t: Theme) => void;
  setLang: (l: Lang) => void;
  setReviewer: (r: string) => void;
  setApiKey: (k: string) => void;
}

const PrefsContext = createContext<Prefs | null>(null);

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => (getStored("theme") === "dark" ? "dark" : "light"));
  const [lang, setLangState] = useState<Lang>(() => (getStored("lang") === "en" ? "en" : "fr"));
  const [reviewer, setReviewerState] = useState(() => getStored("reviewer"));
  const [apiKey, setApiKeyState] = useState(() => getStored("apiKey"));

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const value = useMemo<Prefs>(
    () => ({
      theme,
      lang,
      reviewer,
      apiKey,
      t: dictionaries[lang],
      setTheme: (v) => {
        setStored("theme", v);
        setThemeState(v);
      },
      setLang: (v) => {
        setStored("lang", v);
        setLangState(v);
      },
      setReviewer: (v) => {
        setStored("reviewer", v.trim());
        setReviewerState(v.trim());
      },
      setApiKey: (v) => {
        setStored("apiKey", v.trim());
        setApiKeyState(v.trim());
      },
    }),
    [theme, lang, reviewer, apiKey],
  );
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs(): Prefs {
  const ctx = useContext(PrefsContext);
  if (!ctx) throw new Error("usePrefs outside PrefsProvider");
  return ctx;
}

export function useT(): Dict {
  return usePrefs().t;
}

// ------------------------------------------------------------------ toasts

export type ToastTone = "info" | "success" | "warning" | "error";
interface Toast {
  id: number;
  tone: ToastTone;
  title?: string;
  message: string;
}
interface Toasts {
  toasts: Toast[];
  push: (tone: ToastTone, message: string, title?: string) => void;
  dismiss: (id: number) => void;
  /** Turns any thrown value into a human message toast. */
  error: (err: unknown) => void;
}

const ToastContext = createContext<Toasts | null>(null);
let toastSeq = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = usePrefs();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dismiss = useCallback((id: number) => setToasts((all) => all.filter((x) => x.id !== id)), []);
  const push = useCallback(
    (tone: ToastTone, message: string, title?: string) => {
      const id = ++toastSeq;
      setToasts((all) => [...all.slice(-3), { id, tone, message, title }]);
      window.setTimeout(() => dismiss(id), tone === "error" ? 9000 : 5500);
    },
    [dismiss],
  );
  const error = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError) {
        if (err.status === 0) return push("error", t.common.network, t.common.errorTitle);
        if (err.status === 401) return push("error", t.common.unauthorized, "401");
        if (err.status === 403) {
          const perm = err.permission || /needs:\s*(\w+)/.exec(err.message)?.[1] || "";
          return push("error", t.access.forbidden(t.access.perms[perm] ?? (perm || "?")), t.access.forbiddenTitle);
        }
        return push("error", err.message, `${t.common.errorTitle} (${err.status})`);
      }
      push("error", err instanceof Error ? err.message : String(err), t.common.errorTitle);
    },
    [push, t],
  );
  const value = useMemo(() => ({ toasts, push, dismiss, error }), [toasts, push, dismiss, error]);
  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

export function useToast(): Toasts {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast outside ToastProvider");
  return ctx;
}

// ------------------------------------------------------------------ runtime / ledger status (shared)

export type AccessMode = "loading" | "named" | "shared" | "open" | "anonymous";

interface SystemState {
  runtime: Runtime | null;
  chain: ChainVerification | null;
  runtimeError: unknown;
  health: Health | null;
  me: Me | null;
  meError: unknown;
  refresh: () => void;
}

const SystemContext = createContext<SystemState | null>(null);

export function SystemProvider({ children }: { children: ReactNode }) {
  const { apiKey } = usePrefs();
  const [runtime, setRuntime] = useState<Runtime | null>(null);
  const [chain, setChain] = useState<ChainVerification | null>(null);
  const [runtimeError, setRuntimeError] = useState<unknown>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [meError, setMeError] = useState<unknown>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((h) => alive && setHealth(h))
      .catch(() => undefined);
    api
      .me()
      .then((m) => alive && (setMe(m), setMeError(null)))
      .catch((e) => alive && (setMe(null), setMeError(e)));
    api
      .runtime()
      .then((r) => alive && (setRuntime(r), setRuntimeError(null)))
      .catch((e) => alive && setRuntimeError(e));
    api
      .verify()
      .then((c) => alive && setChain(c))
      .catch(() => alive && setChain(null));
    return () => {
      alive = false;
    };
  }, [apiKey, tick]);

  const value = useMemo(
    () => ({ runtime, chain, runtimeError, health, me, meError, refresh: () => setTick((n) => n + 1) }),
    [runtime, chain, runtimeError, health, me, meError],
  );
  return <SystemContext.Provider value={value}>{children}</SystemContext.Provider>;
}

export function useSystem(): SystemState {
  const ctx = useContext(SystemContext);
  if (!ctx) throw new Error("useSystem outside SystemProvider");
  return ctx;
}

// ------------------------------------------------------------------ data hook

export interface Async<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
  reload: () => void;
  setData: (d: T) => void;
}

/** Loads data with `fn` whenever `deps` change. Errors are kept (not toasted) so pages can render them. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): Async<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    fn()
      .then((d) => {
        if (!alive) return;
        setData(d);
        setError(null);
      })
      .catch((e) => alive && setError(e))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, loading, reload: () => setTick((n) => n + 1), setData };
}

// ------------------------------------------------------------------ access (accounts & roles)

/** Which roles hold each permission (mirrors the backend; used for "restricted to …" hints). */
export const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  recruiter: ["read", "write", "decide"],
  dpo: ["read", "privacy"],
  admin: ["read", "write", "decide", "privacy", "admin"],
};

export interface Access {
  me: Me | null;
  mode: AccessMode;
  can: (p: Permission) => boolean;
  /** tooltip text when the permission is missing, undefined otherwise */
  denied: (p: Permission) => string | undefined;
  /** name that signs actions server-side, when the account is named */
  signedName: string | null;
}

export function useAccess(): Access {
  const { me, meError } = useSystem();
  const { t } = usePrefs();
  return useMemo(() => {
    const legacy = meError instanceof ApiError && meError.status === 404; // backend < 0.4: no roles
    const mode: AccessMode = me
      ? !me.authenticated
        ? "open"
        : me.shared_key
          ? "shared"
          : "named"
      : meError instanceof ApiError && meError.status === 401
        ? "anonymous"
        : legacy
          ? "open"
          : "loading";
    const can = (p: Permission) => (legacy ? true : Boolean(me?.permissions.includes(p)));
    const denied = (p: Permission) => {
      if (can(p)) return undefined;
      if (mode === "anonymous") return t.access.loginRequired;
      const roles = (Object.keys(ROLE_PERMISSIONS) as Role[])
        .filter((r) => ROLE_PERMISSIONS[r].includes(p))
        .map((r) => t.access.roles[r])
        .join(", ");
      return t.access.reservedTo(roles);
    };
    return { me, mode, can, denied, signedName: mode === "named" && me ? me.name : null };
  }, [me, meError, t]);
}
