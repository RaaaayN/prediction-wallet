import Prism from "prismjs";
import "prismjs/components/prism-python";

/**
 * Returns HTML with Prism Python token spans for use with `react-simple-code-editor`.
 *
 * @example
 * highlightPythonCode("import os\nprint(1)")
 */
export function highlightPythonCode(code: string): string {
  return Prism.highlight(code, Prism.languages.python, "python");
}

/** Vertical padding matching `py-12` (48px × 2) plus comfortable line height for wrapped code. */
const PAD_Y_PX = 96;
const LINE_PX = 26;
const MIN_PX = 150;

/**
 * Minimum editor height so all lines are visible without an inner scrollbar.
 */
export function codeCellMinHeightPx(content: string): number {
  const lines = Math.max(1, content.split("\n").length);
  return Math.max(MIN_PX, lines * LINE_PX + PAD_Y_PX);
}
