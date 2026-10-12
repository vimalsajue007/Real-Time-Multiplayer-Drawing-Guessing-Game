import { Alert, Box, Button, Chip, Paper, Stack, Typography } from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import type { GameState } from '../gameReducer';
import type { CanvasStore } from '../canvasStore';
import DrawingCanvas from './DrawingCanvas';
import GuessPanel from './GuessPanel';
import Scoreboard from './Scoreboard';
import Timer from './Timer';
import RoundResultDialog from './RoundResult';
import { colors } from '../theme';

interface Props {
  state: GameState;
  store: CanvasStore;
  send: (type: string, payload?: object) => boolean;
  onLeave: () => void;
}

export default function GameRoom({ state, store, send, onLeave }: Props) {
  const isDrawer = state.youId === state.drawerId;
  const me = state.players.find((p) => p.id === state.youId);
  const drawer = state.players.find((p) => p.id === state.drawerId);
  const active = state.phase === 'drawing';

  return (
    <Box sx={{ maxWidth: 1400, mx: 'auto', p: { xs: 1.5, md: 3 } }}>
      <Box sx={{ display: 'grid', gap: 2.5, gridTemplateColumns: { xs: '1fr', md: '260px minmax(0,1fr) 320px' }, alignItems: 'start' }}>
        {/* left: live scoreboard */}
        <Box sx={{ order: { xs: 2, md: 1 } }}>
          <Scoreboard players={state.players} youId={state.youId} />
          <Button startIcon={<LogoutIcon />} color="inherit" onClick={onLeave} sx={{ mt: 1.5 }} fullWidth>
            Leave game
          </Button>
        </Box>

        {/* centre: status + canvas */}
        <Box sx={{ order: { xs: 1, md: 2 } }}>
          <Paper
            sx={{
              p: 2,
              mb: 2,
              color: '#fff',
              border: 'none',
              background: isDrawer
                ? `linear-gradient(120deg, ${colors.coral}, #FF9A5A)`
                : `linear-gradient(120deg, ${colors.violet}, #8A7FFF)`,
            }}
          >
            <Stack direction="row" alignItems="center" spacing={2}>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Stack direction="row" spacing={1} mb={0.5}>
                  <Chip size="small" label={`Round ${state.roundNumber} / ${state.totalRounds}`} sx={{ bgcolor: 'rgba(255,255,255,.25)', color: '#fff' }} />
                  <Chip
                    size="small"
                    label={isDrawer ? '✏️ You are drawing' : `👀 ${drawer?.name ?? 'Someone'} is drawing`}
                    sx={{ bgcolor: 'rgba(255,255,255,.25)', color: '#fff' }}
                  />
                </Stack>
                {isDrawer && state.word ? (
                  <>
                    <Typography variant="caption" sx={{ opacity: 0.9 }}>
                      Draw this word:
                    </Typography>
                    <Typography variant="h4" sx={{ textTransform: 'uppercase', letterSpacing: 2 }}>
                      {state.word}
                    </Typography>
                  </>
                ) : (
                  <>
                    <Typography variant="caption" sx={{ opacity: 0.9 }}>
                      {me?.has_guessed ? 'You guessed it! Waiting for the others…' : 'Guess the drawing'}
                    </Typography>
                    <Typography variant="h4" sx={{ fontFamily: 'monospace', letterSpacing: 3, whiteSpace: 'pre', overflow: 'hidden' }}>
                      {state.hint ?? ''}
                    </Typography>
                  </>
                )}
              </Box>
              <Box sx={{ bgcolor: '#fff', borderRadius: '50%', p: 0.5 }}>
                <Timer remaining={state.remaining} total={state.roundSeconds} />
              </Box>
            </Stack>
          </Paper>

          {state.waiting && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Waiting for players to reconnect before the next round…
            </Alert>
          )}

          <DrawingCanvas store={store} canDraw={isDrawer && active} youId={state.youId} send={send} />
        </Box>

        {/* right: guess panel */}
        <Box sx={{ order: 3, height: { md: 'calc(100vh - 48px)' }, position: { md: 'sticky' }, top: { md: 24 } }}>
          <GuessPanel
            chat={state.chat}
            isDrawer={isDrawer}
            hasGuessed={!!me?.has_guessed}
            active={active}
            onGuess={(text) => send('guess', { text })}
          />
        </Box>
      </Box>

      <RoundResultDialog result={state.phase === 'round_end' ? state.result : null} youId={state.youId} />
    </Box>
  );
}
