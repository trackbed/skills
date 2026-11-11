export interface Report {
  id: string;
  accountId: string;
  createdAt: string;
}

export interface ReportFilter {
  accountIds: string[];
  createdAfter?: string;
}

export interface ReportStore {
  list(filter: ReportFilter): Promise<Report[]>;
}
