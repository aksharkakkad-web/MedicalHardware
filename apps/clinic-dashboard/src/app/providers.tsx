"use client";

import type { ReactNode } from "react";

import { MonitoringClientProvider } from "@/lib/monitoring/provider";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";

const monitoringClient = new MockMonitoringClient();

export function Providers({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <MonitoringClientProvider client={monitoringClient}>
      {children}
    </MonitoringClientProvider>
  );
}
