import client from "./client";

export const runBacktest = (params) =>
  client.post("/api/v1/backtest/", params).then((r) => r.data);
