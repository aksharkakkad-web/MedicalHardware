"use client";

import { useState, type ReactNode } from "react";
import { HomeMonitoringClientProvider } from "@/lib/home-monitoring";
import { MockHomeMonitoringClient } from "@/mocks/mock-home-monitoring-client";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => new MockHomeMonitoringClient());
  return <HomeMonitoringClientProvider client={client}>{children}</HomeMonitoringClientProvider>;
}
