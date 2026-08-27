"use client";

import { createContext, useContext } from "react";
import type { ReactNode } from "react";

import type { MonitoringClient } from "./client";

const MonitoringClientContext = createContext<MonitoringClient | null>(null);

export function MonitoringClientProvider({
  children,
  client,
}: Readonly<{ children: ReactNode; client: MonitoringClient }>) {
  return (
    <MonitoringClientContext.Provider value={client}>
      {children}
    </MonitoringClientContext.Provider>
  );
}

export function useMonitoringClient(): MonitoringClient {
  const client = useContext(MonitoringClientContext);

  if (!client) {
    throw new Error("MonitoringClientProvider is missing");
  }

  return client;
}
