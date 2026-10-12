import { Avatar, Box, Chip, Paper, Stack, Typography } from '@mui/material';
import type { PlayerView } from '../types';
import { avatarColor, initials, medal } from '../utils';

interface Props {
  players: PlayerView[];
  youId: number | null;
}

/** Live scoreboard: sorted by score, shows who is drawing and who already guessed. */
export default function Scoreboard({ players, youId }: Props) {
  const sorted = [...players].sort((a, b) => b.score - a.score || a.name.localeCompare(b.name));
  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="h6" mb={1.5}>
        Scoreboard
      </Typography>
      <Stack spacing={0.75}>
        {sorted.map((p, i) => (
          <Box
            key={p.id}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1.25,
              p: 1,
              borderRadius: 3,
              bgcolor: p.is_drawer ? 'rgba(255,107,74,.12)' : p.has_guessed ? 'rgba(20,184,166,.12)' : 'transparent',
              border: p.id === youId ? '2px solid rgba(91,75,255,.35)' : '2px solid transparent',
              opacity: p.left ? 0.4 : p.connected ? 1 : 0.6,
              transition: 'background .3s',
            }}
          >
            <Typography sx={{ width: 24, textAlign: 'center' }}>{medal(i + 1)}</Typography>
            <Avatar sx={{ width: 32, height: 32, fontSize: 14, bgcolor: avatarColor(p.name) }}>{initials(p.name)}</Avatar>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography fontWeight={700} fontSize={14} noWrap>
                {p.name}
                {p.id === youId && ' (you)'}
              </Typography>
              <Stack direction="row" spacing={0.5}>
                {p.is_drawer && <Chip size="small" color="secondary" label="✏️ Drawing" sx={{ height: 18, fontSize: 11 }} />}
                {p.has_guessed && <Chip size="small" color="success" label="✓ Guessed" sx={{ height: 18, fontSize: 11, color: '#fff' }} />}
                {!p.connected && !p.left && <Chip size="small" label="offline" sx={{ height: 18, fontSize: 11 }} />}
                {p.left && <Chip size="small" label="left" sx={{ height: 18, fontSize: 11 }} />}
              </Stack>
            </Box>
            <Typography fontWeight={800} color="primary">
              {p.score}
            </Typography>
          </Box>
        ))}
      </Stack>
    </Paper>
  );
}
