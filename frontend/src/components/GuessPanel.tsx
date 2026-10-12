import { useEffect, useRef, useState } from 'react';
import { Box, IconButton, Paper, Stack, TextField, Typography } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import type { ChatItem } from '../types';

interface Props {
  chat: ChatItem[];
  isDrawer: boolean;
  hasGuessed: boolean;
  active: boolean; // round in progress
  onGuess: (text: string) => void;
}

export default function GuessPanel({ chat, isDrawer, hasGuessed, active, onGuess }: Props) {
  const [text, setText] = useState('');
  const endRef = useRef<HTMLDivElement>(null);
  const disabled = isDrawer || hasGuessed || !active;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'nearest' });
  }, [chat.length]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = text.trim();
    if (!t || disabled) return;
    onGuess(t);
    setText('');
  };

  const placeholder = isDrawer
    ? "You're drawing — no guessing!"
    : hasGuessed
      ? 'You got it! 🎉'
      : active
        ? 'Type your guess…'
        : 'Waiting for next round…';

  return (
    <Paper sx={{ p: 2, display: 'flex', flexDirection: 'column', height: { xs: 360, md: '100%' }, minHeight: 320 }}>
      <Typography variant="h6" mb={1}>
        Guesses
      </Typography>
      <Box sx={{ flex: 1, overflowY: 'auto', pr: 0.5, mb: 1.5 }}>
        <Stack spacing={0.75}>
          {chat.map((c) => (
            <Box
              key={c.id}
              sx={{
                px: 1.5,
                py: 0.75,
                borderRadius: 3,
                fontSize: 14,
                bgcolor:
                  c.kind === 'correct' ? 'rgba(20,184,166,.15)' : c.kind === 'system' ? 'transparent' : 'rgba(91,75,255,.07)',
                color: c.kind === 'system' ? 'text.secondary' : 'text.primary',
                fontStyle: c.kind === 'system' ? 'italic' : 'normal',
                fontWeight: c.kind === 'correct' ? 700 : 400,
              }}
            >
              {c.kind === 'guess' && <b>{c.name}: </b>}
              {c.text}
            </Box>
          ))}
          <div ref={endRef} />
        </Stack>
      </Box>
      <form onSubmit={submit}>
        <Stack direction="row" spacing={1}>
          <TextField
            fullWidth
            size="small"
            value={text}
            disabled={disabled}
            onChange={(e) => setText(e.target.value)}
            placeholder={placeholder}
            inputProps={{ maxLength: 64, 'aria-label': 'guess' }}
            autoComplete="off"
          />
          <IconButton type="submit" color="primary" disabled={disabled || !text.trim()} aria-label="send guess">
            <SendIcon />
          </IconButton>
        </Stack>
      </form>
    </Paper>
  );
}
