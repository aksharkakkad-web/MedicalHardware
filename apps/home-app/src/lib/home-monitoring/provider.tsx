"use client";

import { createContext, type ReactNode, useContext } from "react";
import type { HomeMonitoringClient } from "./client";

const HomeMonitoringClientContext = createContext<HomeMonitoringClient | null>(null);

export function HomeMonitoringClientProvider({ client, children }: { client: HomeMonitoringClient; children: ReactNode }) {
  return <HomeMonitoringClientContext.Provider value={client}>{children}</HomeMonitoringClientContext.Provider>;
}

export function useHomeMonitoringClient(): HomeMonitoringClient {
  const client = useContext(HomeMonitoringClientContext);
  if (!client) throw new Error("useHomeMonitoringClient must be used inside HomeMonitoringClientProvider");
  return client;
}
