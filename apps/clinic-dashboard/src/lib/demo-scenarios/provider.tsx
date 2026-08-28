"use client";

import { createContext, useContext } from "react";
import type { ReactNode } from "react";

import type { DemoScenarioController } from "./types";

const DemoScenarioContext = createContext<DemoScenarioController | null>(null);

export function DemoScenarioProvider({
  children,
  controller,
}: Readonly<{ children: ReactNode; controller: DemoScenarioController | null }>) {
  return <DemoScenarioContext.Provider value={controller}>{children}</DemoScenarioContext.Provider>;
}

export function useDemoScenarioController(): DemoScenarioController | null {
  return useContext(DemoScenarioContext);
}
