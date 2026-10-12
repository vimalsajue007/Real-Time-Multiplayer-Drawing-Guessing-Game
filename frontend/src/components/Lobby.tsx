import { useState } from 'react';
import { Box, Button, Chip, Paper, Stack, Tooltip, Typography } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import LogoutIcon from '@mui/icons-material/Logout';
import type { GameState } from '../gameReducer';
import PlayerList from './PlayerList';
import { colors } from '../theme';

interface Props {
  state: GameState;
  send: (type: string, payload?: object) => boolean;
  onLeave: () => void;
}

export default function Lobby({ state, send, onLeave }: Props) {
  const [copied, setCopied] = useState(false);
  const me = state.players.find((p) => p.id === state.youId);
  const isHost = state.youId === state.hostId;
  const connected = state.players.filter((p) => p.connected && !p.left);
  const enoughPlayers = connected.length >= state.minPlayers;
  const waitingOn = connected.filter((p) => !p.is_host && !p.ready);
  const canStart = isHost && enoughPlayers && waitingOn.length === 0;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/?room=${state.roomCode}`);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard unavailable */
    }
  };

  let hint = '';
  if (!enoughPlayers) hint = `Need at least ${state.minPlayers} players (${connected.length} connected).`;
  else if (waitingOn.length) hint = `Waiting for ${waitingOn.map((p) => p.name).join(', ')} to get ready.`;
  else hint = isHost ? 'Everyone is ready — start when you like!' : 'Waiting for the host to start…';

  return (
    <Box sx={{ maxWidth: 900, mx: 'auto', p: { xs: 2, md: 4 } }}>
      <Stack spacing={3}>
        <Paper
          sx={{
            p: { xs: 3, md: 4 },
            textAlign: 'center',
            background: `linear-gradient(135deg, ${colors.violet} 0%, #8A7FFF 60%, ${colors.coral} 130%)`,
            color: '#fff',
            border: 'none',
          }}
        >
          <Typography variant="overline" sx={{ opacity: 0.85, letterSpacing: 2 }}>
            Room code
          </Typography>
          <Typography variant="h2" sx={{ letterSpacing: 8, fontSize: { xs: 44, md: 64 } }}>
            {state.roomCode}
          </Typography>
          <Stack direction="row" spacing={1} justifyContent="center" mt={1} flexWrap="wrap" useFlexGap>
            <Chip label={`${connected.length} / ${state.maxPlayers} players`} sx={{ bgcolor: 'rgba(255,255,255,.2)', color: '#fff' }} />
            <Chip label={`${state.totalRounds} rounds`} sx={{ bgcolor: 'rgba(255,255,255,.2)', color: '#fff' }} />
            <Tooltip title={copied ? 'Copied!' : 'Copy invite link'}>
              <Chip
                icon={<ContentCopyIcon sx={{ color: '#fff !important' }} />}
                label={copied ? 'Copied!' : 'Invite link'}
                onClick={copy}
                sx={{ bgcolor: 'rgba(255,255,255,.2)', color: '#fff', cursor: 'pointer' }}
              />
            </Tooltip>
          </Stack>
        </Paper>

        <PlayerList players={state.players} youId={state.youId} maxPlayers={state.maxPlayers} />

        <Paper sx={{ p: 2.5 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }} justifyContent="space-between">
            <Typography color="text.secondary">{hint}</Typography>
            <Stack direction="row" spacing={1.5}>
              <Button startIcon={<LogoutIcon />} onClick={onLeave} color="inherit">
                Leave
              </Button>
              {isHost ? (
                <Button variant="contained" color="secondary" size="large" disabled={!canStart} onClick={() => send('start_game')}>
                  🚀 Start game
                </Button>
              ) : (
                <Button
                  variant={me?.ready ? 'outlined' : 'contained'}
                  color="success"
                  size="large"
                  onClick={() => send('ready', { ready: !me?.ready })}
                  sx={me?.ready ? undefined : { color: '#fff' }}
                >
                  {me?.ready ? 'Not ready' : "I'm ready!"}
                </Button>
              )}
            </Stack>
          </Stack>
        </Paper>
      </Stack>
    </Box>
  );
}
