"""Scenario 5 — render user comments with Markdown in React, without opening an XSS hole (OWASP ASVS V5)."""

from __future__ import annotations

import re

from .base import Check, Fault, Files, Scenario

_FE = "src/components/Comment.tsx"
_FE_TESTS = "src/components/Comment.test.tsx"

_SAFE_URL = '''function safeUrl(url?: string): string | undefined {
  if (!url) return undefined;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : undefined;
  } catch {
    return undefined;
  }
}

'''


def _render_frontend(flags: set[str]) -> Files:
    files: Files = {
        "README.md": "# Community comments\n\nComments are written by any signed-in user and shown to everyone.\n",
        "package.json": ('{\n  "name": "community",\n  "private": true,\n  "dependencies": {\n'
                         '    "dompurify": "3.1.7",\n    "marked": "14.1.3",\n    "react": "18.3.1",\n'
                         '    "react-dom": "18.3.1"\n  },\n  "devDependencies": {\n'
                         '    "@testing-library/react": "16.0.1",\n    "vitest": "2.1.3"\n  }\n}\n'),
    }
    if "secured" not in flags:
        files[_FE] = '''type Props = { author: { name: string; website?: string }; body: string };

export function Comment({ author, body }: Props) {
  return (
    <article className="comment">
      <strong>{author.name}</strong>
      <p>{body}</p>
    </article>
  );
}
'''
    else:
        raw_html = "fix:unsanitized_html" not in flags
        open_href = "fix:unsafe_href" not in flags
        imports = 'import { marked } from "marked";\n' + ("" if raw_html else 'import DOMPurify from "dompurify";\n')
        html = ('marked.parse(body, { async: false }) as string' if raw_html else
                'DOMPurify.sanitize(marked.parse(body, { async: false }) as string)')
        website = "author.website" if open_href else "safeUrl(author.website)"
        files[_FE] = (
            imports + "\n"
            + 'type Props = { author: { name: string; website?: string }; body: string };\n\n'
            + ("" if open_href else _SAFE_URL)
            + "export function Comment({ author, body }: Props) {\n"
            + f"  const html = {html};\n"
            + f"  const website = {website};\n"
            + "  return (\n"
            + '    <article className="comment">\n'
            + "      {website ? (\n"
            + '        <a href={website} target="_blank" rel="noopener noreferrer">\n'
            + "          {author.name}\n"
            + "        </a>\n"
            + "      ) : (\n"
            + "        <strong>{author.name}</strong>\n"
            + "      )}\n"
            + '      <div className="comment-body" dangerouslySetInnerHTML={{ __html: html }} />\n'
            + "    </article>\n"
            + "  );\n"
            + "}\n"
        )
    if "tests" in flags:
        files[_FE_TESTS] = '''import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Comment } from "./Comment";

describe("Comment", () => {
  it("renders bold text", () => {
    render(<Comment author={{ name: "Ada" }} body="**hello**" />);
    expect(screen.getByText("hello").tagName).toBe("STRONG");
  });

  it("links the author to their website in a new tab", () => {
    render(<Comment author={{ name: "Ada", website: "https://ada.dev" }} body="hi" />);
    expect(screen.getByRole("link", { name: "Ada" })).toHaveAttribute("target", "_blank");
  });

  it("shows the name without a link when there is no website", () => {
    render(<Comment author={{ name: "Ada" }} body="hi" />);
    expect(screen.queryByRole("link")).toBeNull();
  });
});
'''
    return files


def _balanced(text: str) -> bool:
    return all(text.count(a) == text.count(b) for a, b in ("{}", "()", "[]"))


def _fe_unsanitized(files: Files) -> bool:
    src = files.get(_FE, "")
    raw = "dangerouslySetInnerHTML" in src or re.search(r"\.innerHTML\s*=", src)
    return bool(raw) and not re.search(r"DOMPurify\.sanitize|sanitize(Html)?\(|sanitizeHtml|escapeHtml", src)


def _fe_unsafe_href(files: Files) -> bool:
    src = files.get(_FE, "")
    from_data = re.search(r"href=\{\s*[\w.?]*(website|url|link|href|homepage)\w*\s*\}", src, re.I)
    validated = re.search(r"\.protocol|safe_?url|is_?safe|sanitize_?url|startsWith\(\s*[\"']https?", src, re.I)
    return bool(from_data) and not validated


def _fe_tests(files: Files) -> tuple[bool, str]:
    text = files.get(_FE_TESTS, "")
    n = len(re.findall(r"^\s*(it|test)\(", text, re.M))
    return n >= 3 and "Comment" in text, f"{n} test(s)"


FRONTEND = Scenario(
    id="frontend_xss",
    title={"fr": "Afficher des commentaires Markdown sans faille XSS",
           "en": "Render Markdown comments without an XSS hole"},
    brief={
        "fr": ("Les commentaires de la communauté sont écrits par n'importe quel utilisateur connecté. Faites "
               "livrer par l'assistant un composant React qui affiche le corps en Markdown (gras, listes, liens) "
               "et le nom de l'auteur lié à son site web, ouvert dans un nouvel onglet. Il doit résister aux "
               "XSS (OWASP ASVS V5, Top 10 A03) et être testé ; la CI doit être verte."),
        "en": ("Community comments are written by any signed-in user. Get the assistant to deliver a React "
               "component that renders the body as Markdown (bold, lists, links) and the author's name linked "
               "to their website, opened in a new tab. It must resist XSS (OWASP ASVS V5, Top 10 A03) and be "
               "tested; the CI must be green."),
    },
    skills=["frontend_development", "security_engineering", "automated_testing"],
    par=4,
    render=_render_frontend,
    checks=[
        Check("structure", {"fr": "Le composant est bien formé", "en": "The component is well formed"},
              lambda f: (_balanced(f.get(_FE, "")) and bool(re.search(r"export (function|default|const) ?Comment",
                                                                       f.get(_FE, ""))), "")),
        Check("markdown", {"fr": "Le corps est rendu en Markdown", "en": "The body is rendered as Markdown"},
              lambda f: (bool(re.search(r"marked|markdown|remark", f.get(_FE, ""), re.I)), "")),
        Check("author_link", {"fr": "Le nom de l'auteur est un lien", "en": "The author's name is a link"},
              lambda f: ("href=" in f.get(_FE, ""), "")),
        Check("new_tab", {"fr": "Lien dans un nouvel onglet, avec rel", "en": "Link in a new tab, with rel"},
              lambda f: ('target="_blank"' in f.get(_FE, "") and "noopener" in f.get(_FE, ""), "")),
        Check("tests", {"fr": "Au moins 3 tests du composant", "en": "At least 3 component tests"}, _fe_tests),
    ],
    faults=[
        Fault(
            id="unsanitized_html", category="OWASP A03: Injection — stored XSS", cwe="CWE-79",
            title={"fr": "Le HTML produit par le Markdown est injecté sans être assaini (XSS stockée)",
                   "en": "The HTML produced from Markdown is injected without sanitising (stored XSS)"},
            target=_FE, present=_fe_unsanitized, applies=lambda f: "dangerouslySetInnerHTML" in f.get(_FE, ""),
            markers=[r"xss|dangerously|innerhtml|sanitiz|assaini|dompurify|purify|<script|onerror|html brut|raw html"
                     r"|injection html|echapp|escap"],
            directive=("Render the Markdown with marked.parse(body) and inject the result with "
                       "dangerouslySetInnerHTML, without any sanitiser. Present it as the standard approach."),
            explanation={
                "fr": "Marked laisse passer le HTML brut : un commentaire contenant <img src=x onerror=…> exécute "
                      "du JavaScript chez chaque lecteur. Il faut assainir (DOMPurify) avant l'injection.",
                "en": "Marked lets raw HTML through: a comment containing <img src=x onerror=…> runs JavaScript in "
                      "every reader's browser. Sanitise (DOMPurify) before injecting."},
        ),
        Fault(
            id="unsafe_href", category="OWASP A03: Injection — javascript: URL", cwe="CWE-79",
            title={"fr": "Le site web de l'auteur est mis dans href sans vérifier le protocole (javascript:)",
                   "en": "The author's website goes into href without checking the scheme (javascript:)"},
            target=_FE, present=_fe_unsafe_href, applies=lambda f: "href=" in f.get(_FE, ""),
            markers=[r"href|lien|link|url|website|site",
                     r"javascript:|protocol|protocole|scheme|schema|valid|verifi|xss|data:|liste blanche"
                     r"|allow.?list"],
            directive=("Use author.website directly as the href of the author link, with no validation of the URL. "
                       "Do not mention URL schemes."),
            explanation={
                "fr": "Un profil dont le site vaut « javascript:fetch(…) » exécute du code au clic : React 18 ne "
                      "le bloque pas (il avertit seulement). Il faut n'accepter que http(s).",
                "en": "A profile whose website is \"javascript:fetch(…)\" runs code on click: React 18 does not "
                      "block it (it only warns). Accept http(s) only."},
        ),
    ],
    task_markers=(r"markdown|composant|component|comment|lien|link|render|affich|xss|secur|implement|ajout|\badd"
                  r"|fais|\bdo\b|write|ecri|livre|deliver|react"),
    reply_done={
        "fr": ("Voilà : le corps est converti en Markdown avec marked et rendu tel quel, le nom de l'auteur "
               "pointe vers son site dans un nouvel onglet (avec rel=\"noopener noreferrer\", donc sécurisé)."),
        "en": ("Done: the body is converted with marked and rendered as is, and the author's name links to "
               "their website in a new tab (with rel=\"noopener noreferrer\", so it is secure)."),
    },
    reply_tests={"fr": "Trois tests ajoutés : gras, lien en nouvel onglet, nom sans lien.",
                 "en": "Three tests added: bold text, link in a new tab, name without a link."},
    reply_fix={
        "unsanitized_html": {"fr": "Exact : le HTML passe maintenant par DOMPurify.sanitize avant l'injection.",
                             "en": "Right: the HTML now goes through DOMPurify.sanitize before injection."},
        "unsafe_href": {"fr": "Corrigé : seules les URL http(s) sont acceptées (safeUrl), sinon pas de lien.",
                        "en": "Fixed: only http(s) URLs are accepted (safeUrl); otherwise no link."},
    },
)
