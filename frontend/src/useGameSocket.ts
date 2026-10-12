import { useCallback, useEffect, useReducer, useRef } from 'react';
import { wsUrl } from './api';
import type { CanvasStore } from './canvasStore';
import { gameReducer, initialState } from './gameReducer';
import type { ServerEvent, Session } from './types';

const FATAL: Record<number, string> = {
  4401: 'Your session is no longer valid for this room.',
  4403: 'This room is no longer active.',
  4404: 'Room not found.',
  4409: 'You opened this room in another tab or window.',
};
const MAX_ATTEMPTS = 12;

/**
 * Owns the WebSocket: connects, heartbeats, reconnects with exponential backoff
 * (same token => same seat), and feeds events into the reducer / canvas store.
 */
export function useGameSocket(session: Session, store: CanvasStore, onFatal: (message: string) => void) {
  const [state, dispatch] = useReducer(gameReducer, initialState);
  const wsRef = useRef<WebSocket | null>(null);
  const fatalRef = useRef(onFatal);
  fatalRef.current = onFatal;

  useEffect(() => {
    let stopped = false; // local to this effect run (safe under React StrictMode)
    let attempts = 0;
    let retryTimer: number | undefined;
    let pingTimer: number | undefined;

    const connect = () => {
      dispatch({ type: 'conn', status: attempts === 0 ? 'connecting' : 'reconnecting' });
      const ws = new WebSocket(wsUrl(session));
      wsRef.current = ws;

      ws.onopen = () => {
        attempts = 0;
        dispatch({ type: 'conn', status: 'open' });
        pingTimer = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping', payload: {} }));
        }, 20000);
      };

      ws.onmessage = (e) => {
        let ev: ServerEvent;
        try {
          ev = JSON.parse(e.data);
        } catch {
          return;
        }
        const p = ev.payload;
        if (ev.type === 'state_sync') store.reset(p.strokes ?? []);
        else if (ev.type === 'round_started' || ev.type === 'canvas_cleared') store.reset();
        else if (ev.type === 'stroke') store.applyChunk(p);
        dispatch({ type: 'event', event: ev });
      };

      ws.onclose = (e) => {
        window.clearInterval(pingTimer);
        if (stopped) return;
        if (FATAL[e.code]) {
          fatalRef.current(FATAL[e.code]);
          return;
        }
        attempts += 1;
        if (attempts > MAX_ATTEMPTS) {
          fatalRef.current('Connection lost. Please rejoin the room.');
          return;
        }
        dispatch({ type: 'conn', status: 'reconnecting' });
        retryTimer = window.setTimeout(connect, Math.min(1000 * 2 ** (attempts - 1), 8000));
      };
    };

    connect();
    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      window.clearInterval(pingTimer);
      wsRef.current?.close();
    };
  }, [session.token, session.roomCode, store]);

  const send = useCallback((type: string, payload: object = {}): boolean => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify({ type, payload }));
    return true;
  }, []);

  return { state, send };
}
