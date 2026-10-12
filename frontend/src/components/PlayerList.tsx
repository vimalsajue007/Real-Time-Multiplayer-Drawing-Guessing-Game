import { Avatar, Box, Chip, Paper, Stack, Typography } from '@mui/material';
import type { PlayerView } from '../types';
import { avatarColor, initials } from '../utils';

interface Props {
  players: PlayerView[];
  youId: number | null;
  maxPlayers: number;
}

/** Lobby list: shows ready status and connection state. */
export default function PlayerList({ players, youId, maxPlayers }: Props) {
  return (
    <Paper sx={{ p: 2.5 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5}>
        <Typography variant="h6">Players</Typography>
        <Chip size="small" color="primary" variant="outlined" label={`${players.length} / ${maxPlayers}`} />
      </Stack>
      <Stack spacing={1}>
        {players.map((p) => (
          <Box
            key={p.id}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
              p: 1.25,
              borderRadius: 3,
              bgcolor: p.id === youId ? 'rgba(91,75,255,.07)' : 'rgba(30,27,58,.03)',
              opacity: p.connected ? 1 : 0.55,
            }}
          >
            <Avatar sx={{ bgcolor: avatarColor(p.name), fontWeight: 700 }}>{initials(p.name)}</Avatar>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography fontWeight={700} noWrap>
                {p.name} {p.is_host && '👑'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {p.connected ? 'Online' : 'Reconnecting…'}
                {p.id === youId && ' · You'}
              </Typography>
            </Box>
            <Chip
              size="small"
              color={p.ready ? 'success' : 'default'}
              label={p.ready ? '✓ Ready' : 'Not ready'}
              sx={p.ready ? { color: '#fff' } : undefined}
            />
          </Box>
        ))}
      </Stack>
    </Paper>
  );
}
