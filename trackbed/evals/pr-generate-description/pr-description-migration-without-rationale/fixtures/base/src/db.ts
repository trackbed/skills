export interface Database {
  query<Row>(sql: string, values: unknown[]): Promise<Row[]>;
}
