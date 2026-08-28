"use client";

import type { ReactNode } from "react";

import { MonitoringClientProvider } from "@/lib/monitoring/provider";
import {
  MockMonitoringClient,
  type MonitoringEventStorage,
} from "@/mocks/mock-monitoring-client";

const browserStorage: MonitoringEventStorage = {
  getItem(key) {
    return typeof window === "undefined" ? null : window.localStorage.getItem(key);
  },
  setItem(key, value) {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(key, value);
    }
  },
};

const monitoringClient = new MockMonitoringClient(undefined, browserStorage);

export function Providers({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <MonitoringClientProvider client={monitoringClient}>
      {children}
    </MonitoringClientProvider>
  );
}
