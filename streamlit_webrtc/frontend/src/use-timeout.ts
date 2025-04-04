import { useState, useRef, useCallback, useEffect } from "react";

export function useTimer() {
  const [isTimedOut, setIsTimedOut] = useState(false);

  const timeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

  const start = useCallback((delay: number) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      setIsTimedOut(true);
    }, delay);
  }, []);

  const clear = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setIsTimedOut(false);
  }, []);

  useEffect(() => {
    return () => {
      clear();
    };
  }, [clear]);

  return { start, clear, isTimedOut };
}
