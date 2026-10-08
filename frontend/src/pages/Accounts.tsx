// /settings/accounts — named accounts and roles (admin only).
import { useState, type FormEvent } from "react";
import { AlertTriangle, ClipboardCopy, KeyRound, Loader2, ShieldAlert, Trash2, UserPlus, Users } from "lucide-react";
import { api } from "../api/client";
import { ROLES, type CreatedUser, type Role } from "../api/types";
import { useAccess, useAsync, usePrefs, useSystem, useToast } from "../lib/prefs";
import { cx, dateTime } from "../lib/format";
import { PageHeader, useCrumbs } from "../components/Shell";
import { EmptyState, ErrorState, Modal, Skeleton } from "../components/feedback";

export function AccountsPage() {
  const { t, lang } = usePrefs();
  const toast = useToast();
  const system = useSystem();
  const access = useAccess();
  const allowed = access.can("admin");
  const users = useAsync(() => (allowed ? api.users() : Promise.resolve([])), [allowed]);
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("recruiter");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<CreatedUser | null>(null);
  const [toDelete, setToDelete] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  useCrumbs([{ label: t.nav.settings, to: "/settings" }, { label: t.accounts.nav }]);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (name.trim().length < 2) return;
    setBusy(true);
    try {
      const u = await api.createUser(name.trim(), role);
      setCreated(u);
      setName("");
      users.reload();
      system.refresh();
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await api.deleteUser(toDelete);
      toast.push("success", t.accounts.deleted(toDelete));
      setToDelete(null);
      users.reload();
      system.refresh();
    } catch (err) {
      toast.error(err);
    } finally {
      setDeleting(false);
    }
  };

  if (access.mode === "loading") return <Skeleton h={300} r={14} />;
  if (!allowed) {
    return (
      <div className="card">
        <EmptyState icon={ShieldAlert} title={t.accounts.title}>
          {t.accounts.adminOnly}
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="page">
      <section className="hero">
        <PageHeader title={t.accounts.title} sub={t.accounts.subtitle} />
      </section>

      <div className="grid-2" style={{ alignItems: "start" }}>
        <section className="panel" aria-labelledby="acc-list">
          <h2 id="acc-list" className="panel-title">
            <Users size={18} aria-hidden="true" />
            {t.accounts.list}
          </h2>
          {users.loading && !users.data ? (
            <Skeleton h={160} />
          ) : users.error ? (
            <ErrorState error={users.error} onRetry={users.reload} />
          ) : (users.data ?? []).length === 0 ? (
            <p className="small muted">{t.accounts.empty}</p>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t.accounts.name}</th>
                    <th scope="col">{t.accounts.role}</th>
                    <th scope="col">{t.accounts.createdAt}</th>
                    <th scope="col">
                      <span className="sr-only">{t.accounts.deleteDo}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(users.data ?? []).map((u) => (
                    <tr key={u.name}>
                      <td>
                        <b className="small">{u.name}</b>
                        {access.signedName === u.name && <span className="xs faint"> ({t.accounts.you})</span>}
                      </td>
                      <td>
                        <span className={cx("chip", u.role === "admin" ? "chip-violet" : u.role === "dpo" ? "chip-ok" : "chip-accent")}>
                          <span>{t.access.roles[u.role] ?? u.role}</span>
                        </span>
                      </td>
                      <td className="xs muted" style={{ whiteSpace: "nowrap" }}>
                        {dateTime(u.created_at, lang)}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button className="btn btn-ghost btn-icon btn-sm" aria-label={t.accounts.delete(u.name)} title={t.accounts.delete(u.name)} onClick={() => setToDelete(u.name)}>
                          <Trash2 size={15} aria-hidden="true" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div className="stack-lg">
          <form className="panel" aria-labelledby="acc-new" onSubmit={create}>
            <h2 id="acc-new" className="panel-title">
              <UserPlus size={18} aria-hidden="true" />
              {t.accounts.create}
            </h2>
            <div className="field">
              <label htmlFor="acc-name">{t.accounts.name}</label>
              <input id="acc-name" className="input" maxLength={120} value={name} placeholder={t.accounts.namePh} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="acc-role">{t.accounts.role}</label>
              <select id="acc-role" className="select" value={role} onChange={(e) => setRole(e.target.value as Role)} aria-describedby="acc-role-h">
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {t.access.roles[r]}
                  </option>
                ))}
              </select>
              <p id="acc-role-h" className="hint">
                {t.access.roleDesc[role]}
              </p>
            </div>
            <div>
              <button className="btn btn-primary" type="submit" disabled={busy || name.trim().length < 2}>
                {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : <KeyRound size={16} aria-hidden="true" />}
                {t.accounts.createDo}
              </button>
            </div>
          </form>

          <section className="panel is-secondary" aria-labelledby="acc-roles">
            <h2 id="acc-roles" className="panel-title">
              <ShieldAlert size={16} aria-hidden="true" />
              {t.accounts.rolesTitle}
            </h2>
            <dl className="kv">
              {ROLES.map((r) => (
                <div key={r} style={{ display: "contents" }}>
                  <dt>{t.access.roles[r]}</dt>
                  <dd>{t.access.roleDesc[r]}</dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      </div>

      {created && <KeyModal user={created} onClose={() => setCreated(null)} />}

      {toDelete && (
        <Modal
          title={t.accounts.deleteTitle}
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
          <p className="small">{t.accounts.deleteBody(toDelete)}</p>
          {access.signedName === toDelete && (
            <p className="callout callout-warn">
              <AlertTriangle size={16} aria-hidden="true" />
              <span>{t.accounts.deleteSelf}</span>
            </p>
          )}
        </Modal>
      )}
    </div>
  );
}

function KeyModal({ user, onClose }: { user: CreatedUser; onClose: () => void }) {
  const { t } = usePrefs();
  const toast = useToast();
  const copy = () =>
    void navigator.clipboard
      ?.writeText(user.api_key)
      .then(() => toast.push("success", t.common.copied))
      .catch(() => undefined);
  return (
    <Modal
      title={t.accounts.keyTitle(user.name)}
      onClose={onClose}
      footer={
        <button className="btn btn-primary" onClick={onClose}>
          {t.accounts.keyDone}
        </button>
      }
    >
      <p className="callout callout-warn" role="alert">
        <AlertTriangle size={16} aria-hidden="true" />
        <span>
          <b>{t.accounts.keyWarn}</b>
        </span>
      </p>
      <div className="field">
        <label htmlFor="new-key">{t.accounts.keyLabel}</label>
        <div className="row" style={{ gap: 6 }}>
          <input id="new-key" className="input mono" readOnly value={user.api_key} onFocus={(e) => e.target.select()} />
          <button type="button" className="btn" onClick={copy}>
            <ClipboardCopy size={16} aria-hidden="true" />
            {t.common.copy}
          </button>
        </div>
        <p className="hint">
          {t.access.roles[user.role]} — {t.access.roleDesc[user.role]}
        </p>
      </div>
    </Modal>
  );
}
