export interface ResultRow {
  question: string;
  answer: string;
  responses: number;
}

export function ResultsTable({ rows }: { rows: ResultRow[] }) {
  return (
    <table className="results-table">
      <thead>
        <tr>
          <th>Question</th>
          <th>Answer</th>
          <th>Responses</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={`${row.question}-${row.answer}`}>
            <td>{row.question}</td>
            <td>{row.answer}</td>
            <td>{row.responses}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
