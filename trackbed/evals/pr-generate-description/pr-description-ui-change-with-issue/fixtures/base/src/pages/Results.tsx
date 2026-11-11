import { ResultsTable, type ResultRow } from "../components/ResultsTable";

export function Results({ title, rows }: { title: string; rows: ResultRow[] }) {
  return (
    <main className="results-page">
      <header className="results-header">
        <h1>{title}</h1>
      </header>
      <ResultsTable rows={rows} />
    </main>
  );
}
