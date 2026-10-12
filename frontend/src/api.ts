import axios from 'axios';
import type { GameSummary, JoinResponse, LeaderboardRow, PlayerStats, RoomInfo, Session } from './types';

const http = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api', timeout: 10000 });

export function errorMessage(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const d = e.response?.data?.detail;
    if (typeof d === 'string') return d;
    if (Array.isArray(d) && d[0]?.msg) return 'Please check your input (name: 2–20 characters).';
    if (!e.response) return 'Cannot reach the server. Is the backend running?';
  }
  return 'Something went wrong. Please try again.';
}

export const createRoom = (display_name: string, total_rounds: number) =>
  http.post<JoinResponse>('/rooms', { display_name, total_rounds }).then((r) => r.data);

export const joinRoom = (code: string, display_name: string) =>
  http.post<JoinResponse>(`/rooms/${code.trim().toUpperCase()}/join`, { display_name }).then((r) => r.data);

export const getRoom = (code: string) => http.get<RoomInfo>(`/rooms/${code}`).then((r) => r.data);

export const leaveRoom = (s: Session) =>
  http.post(`/rooms/${s.roomCode}/leave`, null, { headers: { Authorization: `Bearer ${s.token}` } });

export const getLeaderboard = () => http.get<LeaderboardRow[]>('/leaderboard', { params: { limit: 10 } }).then((r) => r.data);
export const getHistory = () => http.get<GameSummary[]>('/games/history', { params: { limit: 10 } }).then((r) => r.data);
export const getPlayerStats = (name: string) =>
  http.get<PlayerStats>(`/players/${encodeURIComponent(name)}/stats`).then((r) => r.data);

export function wsUrl(s: Session): string {
  const base =
    import.meta.env.VITE_WS_URL || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;
  return `${base}/ws/${s.roomCode}?token=${encodeURIComponent(s.token)}`;
}

const KEY = 'drawguess.session';
export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}
export function saveSession(s: Session) {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* storage unavailable */
  }
}
export function clearSession() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
