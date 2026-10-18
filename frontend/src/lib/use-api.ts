"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

export type Loadable<T> = { data: T | undefined; error: Error | undefined; loading: boolean; reload: () => void };

export function useApi<T>(path: string | null): Loadable<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [loading, setLoading] = useState(path !== null);
  const [tick, setTick] = useState(0);
  const seq = useRef(0);
  useEffect(() => {
    if (path === null) return;
    const id = ++seq.current;
    setLoading(true);
    api<T>(path)
      .then((d) => { if (id === seq.current) { setData(d); setError(undefined); } })
      .catch((e) => { if (id === seq.current) setError(e); })
      .finally(() => { if (id === seq.current) setLoading(false); });
  }, [path, tick]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}
