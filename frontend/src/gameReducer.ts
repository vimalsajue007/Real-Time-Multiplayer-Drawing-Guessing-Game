import type { ChatItem, LeaderEntry, Phase, PlayerView, RoundResult, ServerEvent } from './types';

export type ConnStatus = 'idle' | 'connecting' | 'open' | 'reconnecting';

export interface GameState {
  conn: ConnStatus;
  ready: boolean; // first state_sync received
  roomCode: string;
  youId: number | null;
  phase: Phase;
  hostId: number | null;
  players: PlayerView[];
  totalRounds: number;
  roundNumber: number;
  minPlayers: number;
  maxPlayers: number;
  roundSeconds: number;
  drawerId: number | null;
  hint: string | null;
  word: string | null; // only ever set for the drawer
  remaining: number;
  chat: ChatItem[];
  result: RoundResult | null;
  leaderboard: LeaderEntry[] | null;
  waiting: boolean;
  lastError: { code: string; message: string; at: number } | null;
}

export const initialState: GameState = {
  conn: 'idle',
  ready: false,
  roomCode: '',
  youId: null,
  phase: 'lobby',
  hostId: null,
  players: [],
  totalRounds: 0,
  roundNumber: 0,
  minPlayers: 2,
  maxPlayers: 8,
  roundSeconds: 80,
  drawerId: null,
  hint: null,
  word: null,
  remaining: 0,
  chat: [],
  result: null,
  leaderboard: null,
  waiting: false,
  lastError: null,
};

export type Action = { type: 'event'; event: ServerEvent } | { type: 'conn'; status: ConnStatus };

let chatSeq = 0;
const sys = (text: string, kind: ChatItem['kind'] = 'system', name?: string): ChatItem => ({
  id: ++chatSeq,
  kind,
  text,
  name,
});
const addChat = (chat: ChatItem[], item: ChatItem) => [...chat, item].slice(-80);
const mapPlayer = (ps: PlayerView[], id: number, f: (p: PlayerView) => PlayerView) =>
  ps.map((p) => (p.id === id ? f(p) : p));

export function gameReducer(state: GameState, action: Action): GameState {
  if (action.type === 'conn') return { ...state, conn: action.status };
  const { type, payload: p } = action.event;
  switch (type) {
    case 'state_sync':
      return {
        ...state,
        ready: true,
        roomCode: p.room_code,
        youId: p.you,
        phase: p.phase,
        hostId: p.host_id,
        players: p.players,
        totalRounds: p.total_rounds,
        roundNumber: p.round_number,
        minPlayers: p.min_players,
        maxPlayers: p.max_players,
        roundSeconds: p.round_seconds,
        drawerId: p.drawer_id,
        hint: p.hint,
        word: p.word ?? null,
        remaining: p.remaining ?? 0,
        result: p.result,
        leaderboard: p.leaderboard,
        waiting: false,
      };
    case 'player_joined':
      return {
        ...state,
        players: state.players.some((x) => x.id === p.player.id) ? state.players : [...state.players, p.player],
        chat: addChat(state.chat, sys(`${p.player.name} joined`)),
      };
    case 'player_left':
      return {
        ...state,
        players:
          state.phase === 'lobby'
            ? state.players.filter((x) => x.id !== p.player_id)
            : mapPlayer(state.players, p.player_id, (x) => ({ ...x, left: true, connected: false })),
        chat: addChat(state.chat, sys(`${p.name} left${p.reason === 'timeout' ? ' (timed out)' : ''}`)),
      };
    case 'player_connected':
      return {
        ...state,
        players: mapPlayer(state.players, p.player_id, (x) => ({ ...x, connected: true })),
        chat: addChat(state.chat, sys(`${p.name} connected`)),
      };
    case 'player_disconnected':
      return {
        ...state,
        players: mapPlayer(state.players, p.player_id, (x) => ({ ...x, connected: false })),
        chat: addChat(state.chat, sys(`${p.name} lost connection`)),
      };
    case 'player_ready':
      return { ...state, players: mapPlayer(state.players, p.player_id, (x) => ({ ...x, ready: p.ready })) };
    case 'host_changed':
      return {
        ...state,
        hostId: p.host_id,
        players: state.players.map((x) => ({ ...x, is_host: x.id === p.host_id, ready: x.ready || x.id === p.host_id })),
      };
    case 'game_started':
      return { ...state, totalRounds: p.total_rounds, chat: addChat(state.chat, sys('Game started — good luck!')) };
    case 'round_started':
      return {
        ...state,
        phase: 'drawing',
        roundNumber: p.round_number,
        totalRounds: p.total_rounds,
        drawerId: p.drawer_id,
        hint: p.hint,
        word: p.word ?? null,
        remaining: p.remaining,
        roundSeconds: p.round_seconds,
        players: p.players,
        result: null,
        waiting: false,
        chat: addChat(state.chat, sys(`Round ${p.round_number}: ${p.drawer_name} is drawing`)),
      };
    case 'timer':
      return { ...state, remaining: p.remaining };
    case 'chat':
      return { ...state, chat: addChat(state.chat, sys(p.text, 'guess', p.name)) };
    case 'correct_guess':
      return {
        ...state,
        players: mapPlayer(state.players, p.player_id, (x) => ({ ...x, has_guessed: true })),
        chat: addChat(state.chat, sys(`${p.name} guessed it! +${p.points}`, 'correct')),
      };
    case 'scores_updated': {
      const m = new Map<number, number>(p.scores.map((s: any) => [s.player_id, s.score]));
      return { ...state, players: state.players.map((x) => (m.has(x.id) ? { ...x, score: m.get(x.id)! } : x)) };
    }
    case 'round_ended': {
      const m = new Map<number, number>(p.scores.map((s: any) => [s.player_id, s.score]));
      return {
        ...state,
        phase: 'round_end',
        result: p,
        word: null,
        players: state.players.map((x) => (m.has(x.id) ? { ...x, score: m.get(x.id)! } : x)),
      };
    }
    case 'waiting_for_players':
      return { ...state, waiting: true };
    case 'game_ended':
      return { ...state, phase: 'finished', leaderboard: p.leaderboard, waiting: false };
    case 'error':
      return { ...state, lastError: { code: p.code, message: p.message, at: Date.now() } };
    default:
      return state;
  }
}
