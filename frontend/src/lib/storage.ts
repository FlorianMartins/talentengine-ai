// Tiny localStorage wrapper: every access is guarded (private mode, blocked storage…).

export type StoredKey = "theme" | "lang" | "reviewer" | "apiKey" | "sidebar";

const PREFIX = "te.";

export function getStored(key: StoredKey, fallback = ""): string {
  try {
    return localStorage.getItem(PREFIX + key) ?? fallback;
  } catch {
    return fallback;
  }
}

export function setStored(key: StoredKey, value: string): void {
  try {
    if (value === "") localStorage.removeItem(PREFIX + key);
    else localStorage.setItem(PREFIX + key, value);
  } catch {
    /* storage unavailable: the setting simply won't persist */
  }
}
