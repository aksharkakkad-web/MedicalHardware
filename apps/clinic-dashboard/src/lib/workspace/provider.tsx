"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import type { MonitoringClient } from "@/lib/monitoring";
import type { WorkspaceClient } from "./client";
import { DemoWorkspaceClient } from "./demo-client";
import type { WorkspaceStorage } from "./demo-client";
import type { WorkspaceSnapshot } from "./types";
interface WorkspaceState {
  snapshot: WorkspaceSnapshot | null;
  status: "loading" | "ready" | "error";
  error: string | null;
  client: WorkspaceClient;
  refresh: () => Promise<void>;
}
const Context = createContext<WorkspaceState | null>(null);
export function WorkspaceProvider({
  children,
  client,
  monitoringClient,
  storage,
}: Readonly<{
  children: ReactNode;
  client?: WorkspaceClient;
  monitoringClient?: MonitoringClient;
  storage?: WorkspaceStorage;
}>) {
  const [source] = useState(
    () =>
      client ??
      new DemoWorkspaceClient({
        monitoringClient,
        storage,
      }),
  );
  const [state, setState] = useState<
    Pick<WorkspaceState, "snapshot" | "status" | "error">
  >({
    snapshot: null,
    status: "loading",
    error: null,
  });
  const generation = useRef(0);
  const refresh = useCallback(async () => {
    const current = ++generation.current;
    try {
      const snapshot = await source.snapshot();
      if (current === generation.current)
        setState({
          snapshot,
          status: "ready",
          error: null,
        });
    } catch (error) {
      if (current === generation.current)
        setState({
          snapshot: null,
          status: "error",
          error:
            error instanceof Error
              ? error.message
              : "The workspace could not be loaded.",
        });
    }
  }, [source]);
  useEffect(() => {
    let active = true;
    const reload = () => {
      if (active) void refresh();
    };
    const unsubscribe = source.subscribe(reload);
    reload();
    const onFocus = () => reload();
    window.addEventListener("focus", onFocus);
    return () => {
      active = false;
      unsubscribe();
      window.removeEventListener("focus", onFocus);
    };
  }, [source, refresh]);
  return (
    <Context.Provider
      value={{
        ...state,
        client: source,
        refresh,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw new Error("WorkspaceProvider is missing.");
  return value;
}
export function useWorkspaceClient() {
  return useWorkspace().client;
}
