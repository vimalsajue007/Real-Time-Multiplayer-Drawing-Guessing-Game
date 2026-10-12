export type Phase = 'lobby' | 'drawing' | 'round_end' | 'finished';

export interface PlayerView {
  id: number;
  name: string;
  score: number;
  ready: boolean;
  connected: boolean;
  left: boolean;
  is_host: boolean;
  is_drawer: boolean;
  has_guessed: boolean;
}

export interface StrokeChunk {
  stroke_id: string;
  tool: 'brush' | 'eraser';
  color: string;
  size: number;
  points: [number, number][];
  end: boolean;
}

export interface RoundResultRow {
  player_id: number;
  name: string;
  points_gained: number;
  guessed: boolean;
  is_drawer: boolean;
}

export interface RoundResult {
  reason: string;
  word: string;
  round_number: number;
  total_rounds: number;
  results: RoundResultRow[];
  scores: { player_id: number; score: number }[];
  next_in: number;
  is_last: boolean;
}

export interface LeaderEntry {
  rank: number;
  player_id: number;
  name: string;
  score: number;
  is_winner: boolean;
}

export interface Session {
  roomCode: string;
  playerId: number;
  token: string;
  name: string;
}

export interface ServerEvent {
  type: string;
  payload: any;
}

export interface ChatItem {
  id: number;
  kind: 'guess' | 'correct' | 'system';
  name?: string;
  text: string;
}

// REST types
export interface RoomInfo {
  room_code: string;
  status: string;
  joinable: boolean;
  player_count: number;
  min_players?: number | null;
  max_players?: number | null;
  total_rounds: number;
  current_round: number;
  players: { display_name: string; score: number }[];
}

export interface JoinResponse {
  room_code: string;
  player_id: number;
  display_name: string;
  token: string;
  room: RoomInfo;
}

export interface LeaderboardRow {
  rank: number;
  display_name: string;
  total_score: number;
  games_played: number;
  wins: number;
  best_score: number;
}

export interface PlayerStats {
  display_name: string;
  games_played: number;
  wins: number;
  win_rate: number;
  total_score: number;
  average_score: number;
  best_score: number;
  correct_guesses: number;
  rounds_drawn: number;
}

export interface GameSummary {
  room_code: string;
  status: string;
  total_rounds: number;
  started_at: string | null;
  ended_at: string | null;
  players: { display_name: string; score: number; is_winner: boolean }[];
}
