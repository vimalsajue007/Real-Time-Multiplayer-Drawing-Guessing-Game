import { useEffect, useState } from 'react';
import { Alert, Box, Button, Paper, Stack, Tab, Table, TableBody, TableCell, TableHead, TableRow, Tabs, TextField, Typography } from '@mui/material';
import { errorMessage, getHistory, getLeaderboard, getPlayerStats } from '../api';
import type { GameSummary, LeaderboardRow, PlayerStats } from '../types';
import { medal } from '../utils';

export default function HallOfFame() {
  const [tab, setTab] = useState(0);
  const [board, setBoard] = useState<LeaderboardRow[]>([]);
  const [history, setHistory] = useState<GameSummary[]>([]);
  const [query, setQuery] = useState('');
  const [stats, setStats] = useState<PlayerStats | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    getLeaderboard().then(setBoard).catch(() => undefined);
    getHistory().then(setHistory).catch(() => undefined);
  }, []);

  const lookup = async (e: React.FormEvent) => {
    e.preventDefault();
    setStats(null);
    setMsg(null);
    if (!query.trim()) return;
    try {
      setStats(await getPlayerStats(query.trim()));
    } catch (err: any) {
      setMsg(err?.response?.status === 404 ? 'No completed games found for that name.' : errorMessage(err));
    }
  };

  return (
    <Paper sx={{ p: { xs: 2, md: 3 } }}>
      <Typography variant="h5" mb={1}>
        🌟 Hall of fame
      </Typography>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="fullWidth" sx={{ mb: 2 }}>
        <Tab label="Leaderboard" />
        <Tab label="Recent games" />
        <Tab label="Player stats" />
      </Tabs>

      {tab === 0 &&
        (board.length === 0 ? (
          <Typography color="text.secondary">No finished games yet — be the first on the board!</Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>#</TableCell>
                <TableCell>Player</TableCell>
                <TableCell align="right">Points</TableCell>
                <TableCell align="right">Wins</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {board.map((r) => (
                <TableRow key={r.display_name}>
                  <TableCell>{medal(r.rank)}</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>{r.display_name}</TableCell>
                  <TableCell align="right">{r.total_score}</TableCell>
                  <TableCell align="right">{r.wins}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ))}

      {tab === 1 &&
        (history.length === 0 ? (
          <Typography color="text.secondary">Completed games will show up here.</Typography>
        ) : (
          <Stack spacing={1}>
            {history.map((g) => (
              <Box key={g.room_code} sx={{ p: 1.5, borderRadius: 3, bgcolor: 'rgba(30,27,58,.03)' }}>
                <Typography variant="caption" color="text.secondary">
                  {g.room_code} · {g.total_rounds} rounds · {g.ended_at ? new Date(g.ended_at + 'Z').toLocaleString() : ''}
                </Typography>
                <Typography fontSize={14}>
                  {g.players.map((p) => `${p.is_winner ? '🏆 ' : ''}${p.display_name} ${p.score}`).join('  ·  ')}
                </Typography>
              </Box>
            ))}
          </Stack>
        ))}

      {tab === 2 && (
        <Box>
          <form onSubmit={lookup}>
            <Stack direction="row" spacing={1} mb={2}>
              <TextField size="small" fullWidth placeholder="Display name" value={query} onChange={(e) => setQuery(e.target.value)} />
              <Button type="submit" variant="contained">
                Look up
              </Button>
            </Stack>
          </form>
          {msg && <Alert severity="info">{msg}</Alert>}
          {stats && (
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1.5 }}>
              {[
                ['Games', stats.games_played],
                ['Wins', stats.wins],
                ['Win rate', `${Math.round(stats.win_rate * 100)}%`],
                ['Total points', stats.total_score],
                ['Avg score', stats.average_score],
                ['Best score', stats.best_score],
                ['Correct guesses', stats.correct_guesses],
                ['Rounds drawn', stats.rounds_drawn],
              ].map(([k, v]) => (
                <Box key={k as string} sx={{ p: 1.5, borderRadius: 3, bgcolor: 'rgba(91,75,255,.07)', textAlign: 'center' }}>
                  <Typography variant="h5" color="primary">
                    {v}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {k}
                  </Typography>
                </Box>
              ))}
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
}
