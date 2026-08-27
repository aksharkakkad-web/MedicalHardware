"use client";

import { useCallback, useEffect, useState } from "react";

import { useMonitoringClient } from "@/lib/monitoring/provider";
import type { ResidentOverviewItem } from "@/lib/monitoring/types";

type ResidentOverviewState =
  | { status: "loading"; items: [] }
  | { status: "success"; items: ResidentOverviewItem[] }
  | { status: "error"; items: []; message: string };

type ResidentOverviewResult = ResidentOverviewState & {
  retry: () => void;
};

const loadingState: ResidentOverviewState = {
  status: "loading",
  items: [],
};

export function useResidentOverview(): ResidentOverviewResult {
  const client = useMonitoringClient();
  const [requestVersion, setRequestVersion] = useState(0);
  const [state, setState] = useState<ResidentOverviewState>(loadingState);

  useEffect(() => {
    let isCurrent = true;

    async function loadResidentOverview() {
      setState(loadingState);

      try {
        const response = await client.listResidentOverview();
        if (isCurrent) {
          setState({ status: "success", items: response.items });
        }
      } catch {
        if (isCurrent) {
          setState({
            status: "error",
            items: [],
            message: "Current resident information could not be loaded.",
          });
        }
      }
    }

    void loadResidentOverview();

    return () => {
      isCurrent = false;
    };
  }, [client, requestVersion]);

  const retry = useCallback(() => {
    setState(loadingState);
    setRequestVersion((version) => version + 1);
  }, []);

  return { ...state, retry };
}
