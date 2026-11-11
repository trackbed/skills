import type { ResultRow } from "./ResultsTable";
import { toCsv } from "../lib/csv";

export function ExportCsvButton({
  fileName,
  rows,
}: {
  fileName: string;
  rows: ResultRow[];
}) {
  function download() {
    const blob = new Blob([toCsv(rows)], { type: "text/csv" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${fileName}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return (
    <button
      type="button"
      className="button button-secondary"
      disabled={rows.length === 0}
      onClick={download}
    >
      Export CSV
    </button>
  );
}
