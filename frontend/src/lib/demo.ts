// Public read-only demo (fictional data, served by a separate engine at /demo/api). Kept per tab.
const KEY = "te.demo";

export function isDemo(): boolean {
  try {
    return sessionStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function storeDemo(on: boolean): void {
  try {
    if (on) sessionStorage.setItem(KEY, "1");
    else sessionStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: the demo lasts until the page is reloaded */
  }
}
