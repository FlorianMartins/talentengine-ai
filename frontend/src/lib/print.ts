// Print helpers. A page can render a dedicated print document (class "print-doc"); `printDoc()` flags the
// <html> element so the print stylesheet shows only that document, then clears the flag after printing.

export function printDoc(): void {
  const root = document.documentElement;
  root.dataset.print = "doc";
  const done = () => {
    delete root.dataset.print;
    window.removeEventListener("afterprint", done);
  };
  window.addEventListener("afterprint", done);
  window.print();
}

/** Plain print of the current page (public pages are their own document). */
export function printPage(): void {
  window.print();
}
