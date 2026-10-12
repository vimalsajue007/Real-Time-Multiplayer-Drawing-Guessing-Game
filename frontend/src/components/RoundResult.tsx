import { useEffect, useState } from 'react';
import { Box, Dialog, DialogContent, LinearProgress, Stack, Typography } from '@mui/material';
import type { RoundResult } from '../types';
import { colors } from '../theme';

const REASONS: Record<string, string> = {
  time_up: "⏰ Time's up!",
  all_guessed: '🎉 Everyone guessed it!',
  drawer_disconnected: '📡 The drawer lost connection',
  drawer_left: '🚪 The drawer left',
};

interface Props {
  result: RoundResult | null;
  youId: number | null;
}

export default function RoundResultDialog({ result, youId }: Props) {
  const [left, setLeft] = useState(0);

  useEffect(() => {
    if (!result) return;
    const end = Date.now() + result.next_in * 1000;
    setLeft(result.next_in);
    const t = window.setInterval(() => setLeft(Math.max(0, (end - Date.now()) / 1000)), 100);
    return () => window.clearInterval(t);
  }, [result]);

  if (!result) return null;
  const rows = [...result.results].sort((a, b) => b.points_gained - a.points_gained);

  return (
    <Dialog open maxWidth="xs" fullWidth PaperProps={{ sx: { borderRadius: 5, overflow: 'hidden' } }}>
      <Box sx={{ p: 3, textAlign: 'center', color: '#fff', background: `linear-gradient(120deg, ${colors.violet}, ${colors.coral})` }}>
        <Typography variant="body2" sx={{ opacity: 0.9 }}>
          {REASONS[result.reason] ?? 'Round over'}
        </Typography>
        <Typography variant="caption" sx={{ opacity: 0.85 }}>
          The word was
        </Typography>
        <Typography variant="h3" sx={{ textTransform: 'uppercase', letterSpacing: 3 }}>
          {result.word}
        </Typography>
      </Box>
      <DialogContent>
        <Typography variant="subtitle2" color="text.secondary" mb={1}>
          Round {result.round_number} of {result.total_rounds} results
        </Typography>
        <Stack spacing={0.75}>
          {rows.map((r) => (
            <Stack
              key={r.player_id}
              direction="row"
              justifyContent="space-between"
              sx={{ p: 1, borderRadius: 2, bgcolor: r.player_id === youId ? 'rgba(91,75,255,.08)' : 'rgba(30,27,58,.03)' }}
            >
              <Typography fontWeight={600}>
                {r.name} {r.is_drawer ? '✏️' : r.guessed ? '✅' : '❌'}
              </Typography>
              <Typography fontWeight={800} color={r.points_gained > 0 ? 'success.main' : 'text.secondary'}>
                {r.points_gained > 0 ? `+${r.points_gained}` : '0'}
              </Typography>
            </Stack>
          ))}
        </Stack>
        <Box mt={2.5}>
          <Typography variant="caption" color="text.secondary">
            {result.is_last ? 'Final leaderboard coming up…' : `Next round in ${Math.ceil(left)}s…`}
          </Typography>
          <LinearProgress variant="determinate" value={result.next_in ? (left / result.next_in) * 100 : 0} sx={{ mt: 0.5, height: 8, borderRadius: 4 }} />
        </Box>
      </DialogContent>
    </Dialog>
  );
}
