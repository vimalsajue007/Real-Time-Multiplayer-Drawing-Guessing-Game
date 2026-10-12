import { useCallback, useMemo, useState } from 'react';
import { Alert, Box, CircularProgress, Snackbar, Stack, Typography } from '@mui/material';
import { clearSession, leaveRoom, loadSession, saveSession } from './api';
import { CanvasStore } from './canvasStore';
import FinalLeaderboard from './components/FinalLeaderboard';
import GameRoom from './components/GameRoom';
import JoinCreate from './components/JoinCreate';
import Lobby from './components/Lobby';
import { useGameSocket } from './useGameSocket';
import type { Session } from './types';

function RoomView({ session, onExit }: { session: Session; onExit: (flash?: string) => void }) {
  const store = useMemo(() => new CanvasStore(), []);
  const { state, send } = useGameSocket(session, store, (m) => onExit(m));

  const leave = useCallback(() => {
    send('leave');
    leaveRoom(session).catch(() => undefined);
    onExit();
  }, [send, session, onExit]);

  const showBanner = state.conn !== 'open' && state.ready;

  return (
    <>
      {showBanner && (
        <Alert severity="warning" sx={{ position: 'sticky', top: 0, zIndex: 20, borderRadius: 0 }}>
          Connection lost — reconnecting… your seat is kept for a short while.
        </Alert>
      )}
      {!state.ready ? (
        <Stack alignItems="center" justifyContent="center" spacing={2} sx={{ minHeight: '70vh' }}>
          <CircularProgress />
          <Typography color="text.secondary">Connecting to room {session.roomCode}…</Typography>
        </Stack>
      ) : state.phase === 'lobby' ? (
        <Lobby state={state} send={send} onLeave={leave} />
      ) : state.phase === 'finished' ? (
        <FinalLeaderboard leaderboard={state.leaderboard ?? []} youId={state.youId} onExit={leave} />
      ) : (
        <GameRoom state={state} store={store} send={send} onLeave={leave} />
      )}
      <Snackbar
        open={!!state.lastError}
        autoHideDuration={3500}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        key={state.lastError?.at}
      >
        <Alert severity="error" variant="filled" sx={{ width: '100%' }}>
          {state.lastError?.message}
        </Alert>
      </Snackbar>
    </>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(() => loadSession());
  const [flash, setFlash] = useState<string | null>(null);

  const enter = useCallback((s: Session) => {
    saveSession(s);
    setFlash(null);
    setSession(s);
  }, []);

  const exit = useCallback((message?: string) => {
    clearSession();
    setSession(null);
    setFlash(message ?? null);
  }, []);

  return (
    <Box sx={{ minHeight: '100vh' }}>
      {session ? <RoomView key={session.token} session={session} onExit={exit} /> : <JoinCreate onEnter={enter} flash={flash} />}
    </Box>
  );
}
