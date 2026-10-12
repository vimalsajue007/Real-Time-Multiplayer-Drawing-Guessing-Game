import { useState } from 'react';
import { Alert, Box, Button, Divider, MenuItem, Paper, Stack, TextField, Typography } from '@mui/material';
import { createRoom, errorMessage, joinRoom } from '../api';
import type { Session } from '../types';
import HallOfFame from './HallOfFame';
import { colors } from '../theme';

interface Props {
  onEnter: (s: Session) => void;
  flash: string | null;
}

export default function JoinCreate({ onEnter, flash }: Props) {
  const initialCode = new URLSearchParams(window.location.search).get('room')?.toUpperCase() ?? '';
  const [name, setName] = useState('');
  const [code, setCode] = useState(initialCode);
  const [rounds, setRounds] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nameOk = name.trim().length >= 2;

  const run = async (fn: () => Promise<{ room_code: string; player_id: number; token: string; display_name: string }>) => {
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      window.history.replaceState({}, '', window.location.pathname);
      onEnter({ roomCode: r.room_code, playerId: r.player_id, token: r.token, name: r.display_name });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box sx={{ maxWidth: 1000, mx: 'auto', p: { xs: 2, md: 4 } }}>
      <Box textAlign="center" mb={4}>
        <Typography variant="h2" sx={{ fontSize: { xs: 44, md: 64 }, lineHeight: 1.05 }}>
          <Box component="span" sx={{ color: colors.violet }}>
            Doodle
          </Box>{' '}
          <Box component="span" sx={{ color: colors.coral }}>
            Duel
          </Box>{' '}
          🎨
        </Typography>
        <Typography color="text.secondary" mt={1} fontSize={18}>
          Draw it. Guess it. Outscore your friends — live.
        </Typography>
      </Box>

      {flash && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {flash}
        </Alert>
      )}

      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, alignItems: 'start' }}>
        <Paper sx={{ p: { xs: 2.5, md: 3.5 } }}>
          <Stack spacing={2.5}>
            <TextField
              label="Your display name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              inputProps={{ maxLength: 20 }}
              helperText="2–20 characters"
              autoFocus
            />

            <Divider textAlign="left">
              <Typography variant="overline" color="primary">
                Start a new game
              </Typography>
            </Divider>
            <TextField select label="Rounds" value={rounds} onChange={(e) => setRounds(Number(e.target.value))}>
              {[1, 2, 3, 4, 5, 6, 8, 10].map((n) => (
                <MenuItem key={n} value={n}>
                  {n} {n === 1 ? 'round' : 'rounds'}
                </MenuItem>
              ))}
            </TextField>
            <Button
              variant="contained"
              color="secondary"
              size="large"
              disabled={!nameOk || busy}
              onClick={() => run(() => createRoom(name.trim(), rounds))}
            >
              ✨ Create room
            </Button>

            <Divider textAlign="left">
              <Typography variant="overline" color="primary">
                …or join friends
              </Typography>
            </Divider>
            <TextField
              label="Room code"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))}
              inputProps={{ maxLength: 8, style: { letterSpacing: 6, fontWeight: 700, textAlign: 'center' } }}
            />
            <Button
              variant="contained"
              size="large"
              disabled={!nameOk || code.length < 4 || busy}
              onClick={() => run(() => joinRoom(code, name.trim()))}
            >
              Join room
            </Button>
            {error && <Alert severity="error">{error}</Alert>}
          </Stack>
        </Paper>

        <HallOfFame />
      </Box>
    </Box>
  );
}
