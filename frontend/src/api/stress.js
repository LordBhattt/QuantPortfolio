import client from "./client";

export const getStressTest = (portfolioId) =>
  client.get(`/api/v1/risk/${portfolioId}/stress`).then((r) => r.data);

export const runCustomStress = (portfolioId, shockParams) =>
  client.post(`/api/v1/risk/${portfolioId}/stress/custom`, shockParams).then((r) => r.data);
