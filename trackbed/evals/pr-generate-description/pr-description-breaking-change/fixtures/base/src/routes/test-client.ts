import express from "express";
import type { AddressInfo } from "node:net";
import type { ReportStore } from "../store";
import { reportsRouter } from "./reports";

export async function listReports(
  store: ReportStore,
  query: Record<string, string>,
  visibleAccountIds: string[],
): Promise<Response> {
  const app = express();
  app.use((_request, response, next) => {
    response.locals.accountIds = visibleAccountIds;
    next();
  });
  app.use(reportsRouter(store));
  const server = app.listen(0);
  const { port } = server.address() as AddressInfo;
  try {
    const search = new URLSearchParams(query).toString();
    return await fetch(`http://127.0.0.1:${port}/v1/reports?${search}`);
  } finally {
    server.close();
  }
}
