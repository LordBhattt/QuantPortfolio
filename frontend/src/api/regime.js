import client from "./client";

export const getRegimeHistory = (days = 252) =>
  client.get(`/api/v1/risk/regime/history?days=${days}`).then((r) => r.data);
