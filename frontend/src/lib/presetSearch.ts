// Client-side preset search, same rule as the backend (dashboard/presets.py `search_presets`):
// accent- and case-insensitive; every query word must match; words of ≤ 2 letters must match a whole
// word ("ia", "ux" — a substring search would find "ia" in "fiabilité"), longer words match a word prefix.
// Searched: title, keywords (FR + EN synonyms), criterion labels. Title hits rank first.

export interface Searchable {
  title: string;
  keywords?: string;
  summary?: string;
  criteria?: string[];
}

export function fold(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

function words(text: string): Set<string> {
  return new Set(fold(text).split(/[^a-z0-9+#]+/).filter(Boolean));
}

function hit(word: string, vocabulary: Set<string>): boolean {
  if (word.length <= 2) return vocabulary.has(word);
  for (const v of vocabulary) if (v.startsWith(word)) return true;
  return false;
}

/** Returns the matching items, best first (stable for equal scores). Empty query → everything. */
export function searchPresets<T extends Searchable>(items: T[], query: string): T[] {
  const q = fold(query).split(/[^a-z0-9+#]+/).filter(Boolean);
  if (!q.length) return items;
  const scored: { item: T; score: number; i: number }[] = [];
  items.forEach((item, i) => {
    const hay = words([item.title, item.keywords ?? "", ...(item.criteria ?? [])].join(" "));
    const title = words(item.title);
    if (q.every((w) => hit(w, hay))) scored.push({ item, i, score: q.reduce((s, w) => s + (hit(w, title) ? 3 : 1), 0) });
  });
  return scored.sort((a, b) => b.score - a.score || a.i - b.i).map((x) => x.item);
}
