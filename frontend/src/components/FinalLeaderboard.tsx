import { Avatar, Box, Button, Paper, Stack, Typography } from '@mui/material';
import type { LeaderEntry } from '../types';
import { avatarColor, initials, medal } from '../utils';
import { colors } from '../theme';

interface Props {
  leaderboard: LeaderEntry[];
  youId: number | null;
  onExit: () => void;
}

export default function FinalLeaderboard({ leaderboard, youId, onExit }: Props) {
  const top = leaderboard.slice(0, 3);
  // podium order: 2nd, 1st, 3rd
  const podium = [top[1], top[0], top[2]].filter(Boolean) as LeaderEntry[];
  const heights: Record<number, number> = { 1: 150, 2: 110, 3: 80 };
  const winners = leaderboard.filter((e) => e.is_winner);

  return (
    <Box sx={{ maxWidth: 720, mx: 'auto', p: { xs: 2, md: 4 } }}>
      <Paper sx={{ p: { xs: 3, md: 4 }, textAlign: 'center' }}>
        <Typography variant="h3" mb={0.5}>
          🏆 Final leaderboard
        </Typography>
        <Typography color="text.secondary" mb={3}>
          {winners.length === 0 ? 'Nobody scored this time.' : winners.length > 1 ? `It's a tie: ${winners.map((w) => w.name).join(' & ')}!` : `${winners[0].name} wins!`}
        </Typography>

        <Stack direction="row" justifyContent="center" alignItems="flex-end" spacing={2} mb={4}>
          {podium.map((e) => (
            <Stack key={e.player_id} alignItems="center" sx={{ width: 120 }}>
              <Avatar sx={{ width: 56, height: 56, bgcolor: avatarColor(e.name), fontSize: 24, mb: 0.5 }}>{initials(e.name)}</Avatar>
              <Typography fontWeight={700} noWrap sx={{ maxWidth: '100%' }}>
                {e.name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {e.score} pts
              </Typography>
              <Box
                sx={{
                  mt: 1,
                  width: '100%',
                  height: heights[e.rank] ?? 70,
                  borderRadius: '16px 16px 0 0',
                  display: 'grid',
                  placeItems: 'center',
                  fontSize: 32,
                  background:
                    e.rank === 1
                      ? `linear-gradient(180deg, ${colors.sun}, #FFB020)`
                      : e.rank === 2
                        ? 'linear-gradient(180deg, #CBD5E1, #94A3B8)'
                        : 'linear-gradient(180deg, #F0B27A, #C98A4B)',
                }}
              >
                {medal(e.rank)}
              </Box>
            </Stack>
          ))}
        </Stack>

        <Stack spacing={0.75} textAlign="left">
          {leaderboard.map((e) => (
            <Stack
              key={e.player_id}
              direction="row"
              alignItems="center"
              spacing={1.5}
              sx={{ p: 1.25, borderRadius: 3, bgcolor: e.player_id === youId ? 'rgba(91,75,255,.1)' : 'rgba(30,27,58,.03)' }}
            >
              <Typography sx={{ width: 32, textAlign: 'center' }} fontWeight={700}>
                {medal(e.rank)}
              </Typography>
              <Typography sx={{ flex: 1 }} fontWeight={600}>
                {e.name} {e.player_id === youId && '(you)'}
              </Typography>
              <Typography fontWeight={800} color="primary">
                {e.score}
              </Typography>
            </Stack>
          ))}
        </Stack>

        <Button variant="contained" size="large" sx={{ mt: 3 }} onClick={onExit}>
          Play again
        </Button>
      </Paper>
    </Box>
  );
}
