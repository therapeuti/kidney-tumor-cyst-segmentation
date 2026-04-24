import { useCallback } from "react";

import { fetchCases } from "../../api/cases";
import { useSessionStore } from "../../stores/sessionStore";

export function useSessionBootstrap() {
  const setCases = useSessionStore((state) => state.setCases);
  const setStatus = useSessionStore((state) => state.setStatus);

  const loadCases = useCallback(async () => {
    setStatus("Loading cases...");
    try {
      const cases = await fetchCases();
      setCases(cases);
      setStatus(cases.length > 0 ? "Cases loaded" : "No cases discovered");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load cases");
    }
  }, [setCases, setStatus]);

  return { loadCases };
}
