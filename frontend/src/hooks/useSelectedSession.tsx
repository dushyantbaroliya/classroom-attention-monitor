import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/**
 * Which session the analytics pages display.
 * `undefined` means "let the backend pick" (active session, else latest).
 */
const SelectedSessionContext = createContext<{
  sessionId: number | undefined;
  setSessionId: (id: number | undefined) => void;
}>({ sessionId: undefined, setSessionId: () => {} });

export function SelectedSessionProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<number | undefined>(undefined);
  const value = useMemo(() => ({ sessionId, setSessionId }), [sessionId]);
  return (
    <SelectedSessionContext.Provider value={value}>
      {children}
    </SelectedSessionContext.Provider>
  );
}

export function useSelectedSession() {
  return useContext(SelectedSessionContext);
}
