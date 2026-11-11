import type { ResultRow } from "../components/ResultsTable";

function cell(value: string | number): string {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(rows: ResultRow[]): string {
  const lines = [
    ["Question", "Answer", "Responses"],
    ...rows.map((row) => [row.question, row.answer, row.responses]),
  ];
  return lines.map((line) => line.map(cell).join(",")).join("\n");
}
