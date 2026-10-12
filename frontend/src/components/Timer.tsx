import { Box, CircularProgress, Typography } from '@mui/material';
import { colors } from '../theme';

interface Props {
  remaining: number;
  total: number;
}

export default function Timer({ remaining, total }: Props) {
  const frac = total > 0 ? Math.max(0, Math.min(1, remaining / total)) : 0;
  const color = frac > 0.5 ? colors.teal : frac > 0.2 ? colors.sun : colors.coral;
  const urgent = remaining <= 10 && remaining > 0;
  return (
    <Box
      aria-label={`${remaining} seconds left`}
      sx={{
        position: 'relative',
        display: 'inline-flex',
        animation: urgent ? 'pulse 1s ease-in-out infinite' : 'none',
        '@keyframes pulse': { '0%,100%': { transform: 'scale(1)' }, '50%': { transform: 'scale(1.08)' } },
      }}
    >
      <CircularProgress variant="determinate" value={100} size={64} thickness={5} sx={{ color: 'rgba(30,27,58,.08)' }} />
      <CircularProgress
        variant="determinate"
        value={frac * 100}
        size={64}
        thickness={5}
        sx={{ color, position: 'absolute', left: 0, '& .MuiCircularProgress-circle': { strokeLinecap: 'round' } }}
      />
      <Box sx={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
        <Typography variant="h6" sx={{ color, lineHeight: 1 }}>
          {Math.max(0, Math.ceil(remaining))}
        </Typography>
      </Box>
    </Box>
  );
}
