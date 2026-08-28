"use client";

import { useCallback, useEffect, useState } from "react";

import type {
  EventAction,
  EventFeedbackInput,
  MonitoringEventDetail,
} from "@/lib/monitoring";
import { useMonitoringClient } from "@/lib/monitoring/provider";

type EventDetailState =
  | { status: "loading"; event: null; pendingAction: null; actionError: null }
  | { status: "error"; event: null; pendingAction: null; actionError: null; message: string }
  | {
      status: "success";
      event: MonitoringEventDetail;
      pendingAction: EventAction | "resolve" | null;
      actionError: string | null;
    };

const loadingState: EventDetailState = {
  status: "loading",
  event: null,
  pendingAction: null,
  actionError: null,
};

export function useEventDetail(eventId: string) {
  const client = useMonitoringClient();
  const [requestVersion, setRequestVersion] = useState(0);
  const [state, setState] = useState<EventDetailState>(loadingState);

  useEffect(() => {
    let isCurrent = true;

    async function loadEvent() {
      setState(loadingState);
      try {
        const event = await client.getEvent(eventId);
        if (isCurrent) {
          setState({
            status: "success",
            event,
            pendingAction: null,
            actionError: null,
          });
        }
      } catch {
        if (isCurrent) {
          setState({
            status: "error",
            event: null,
            pendingAction: null,
            actionError: null,
            message: "Current event information could not be loaded.",
          });
        }
      }
    }

    void loadEvent();
    return () => {
      isCurrent = false;
    };
  }, [client, eventId, requestVersion]);

  const retry = useCallback(() => {
    setRequestVersion((version) => version + 1);
  }, []);

  const performAction = useCallback(
    async (action: EventAction) => {
      setState((current) =>
        current.status === "success"
          ? { ...current, pendingAction: action, actionError: null }
          : current,
      );

      try {
        const event = await client.performEventAction(eventId, action);
        setState({
          status: "success",
          event,
          pendingAction: null,
          actionError: null,
        });
      } catch {
        setState((current) =>
          current.status === "success"
            ? {
                ...current,
                pendingAction: null,
                actionError: "That action could not be saved. Try again.",
              }
            : current,
        );
      }
    },
    [client, eventId],
  );

  const resolveWithFeedback = useCallback(
    async (feedback: EventFeedbackInput) => {
      setState((current) =>
        current.status === "success"
          ? { ...current, pendingAction: "resolve", actionError: null }
          : current,
      );

      try {
        const event = await client.resolveEventWithFeedback(eventId, feedback);
        setState({
          status: "success",
          event,
          pendingAction: null,
          actionError: null,
        });
        return true;
      } catch {
        setState((current) =>
          current.status === "success"
            ? {
                ...current,
                pendingAction: null,
                actionError: "The resolution and feedback could not be saved. Try again.",
              }
            : current,
        );
        return false;
      }
    },
    [client, eventId],
  );

  return { ...state, performAction, resolveWithFeedback, retry };
}
