import { useCallback, useEffect, useRef, useState } from 'react';
import { Box, IconButton, Paper, Slider, Stack, ToggleButton, ToggleButtonGroup, Tooltip, Typography } from '@mui/material';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import type { CanvasStore, Stroke } from '../canvasStore';
import { colors } from '../theme';

const W = 800;
const H = 600;
const SWATCHES = ['#1E1B3A', '#FF6B4A', '#FFC83D', '#14B8A6', '#5B4BFF', '#EC4899', '#0EA5E9', '#84CC16', '#8B5E3C', '#9CA3AF'];

function drawSegments(ctx: CanvasRenderingContext2D, s: Stroke, from: number) {
  const color = s.tool === 'eraser' ? '#ffffff' : s.color;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = s.size;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  const pts = s.points;
  if (pts.length === 0) return;
  if (pts.length === 1) {
    ctx.beginPath();
    ctx.arc(pts[0][0] * W, pts[0][1] * H, s.size / 2, 0, Math.PI * 2);
    ctx.fill();
    return;
  }
  const start = Math.max(from - 1, 0);
  ctx.beginPath();
  ctx.moveTo(pts[start][0] * W, pts[start][1] * H);
  for (let i = start + 1; i < pts.length; i++) ctx.lineTo(pts[i][0] * W, pts[i][1] * H);
  ctx.stroke();
}

interface Props {
  store: CanvasStore;
  canDraw: boolean;
  youId: number | null;
  send: (type: string, payload?: object) => boolean;
}

interface ActiveStroke {
  id: string;
  tool: 'brush' | 'eraser';
  color: string;
  size: number;
  pending: [number, number][];
  last: [number, number];
}

/**
 * Canvas drawing system. Pointer events cover mouse, touch and pen. Strokes are
 * normalised (0..1) point lists streamed in small batches; remote clients
 * rebuild the same drawing from those operations — no images are ever sent.
 */
export default function DrawingCanvas({ store, canDraw, youId, send }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  const active = useRef<ActiveStroke | null>(null);
  const flushTimer = useRef<number | undefined>();
  const counter = useRef(0);
  const [tool, setTool] = useState<'brush' | 'eraser'>('brush');
  const [color, setColor] = useState(SWATCHES[0]);
  const [size, setSize] = useState(8);

  const paintAll = useCallback(() => {
    const ctx = ref.current?.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, W, H);
    store.strokes.forEach((s) => drawSegments(ctx, s, 0));
  }, [store]);

  useEffect(() => {
    paintAll();
    return store.subscribe((e) => {
      const ctx = ref.current?.getContext('2d');
      if (!ctx) return;
      if (e.kind === 'reset') paintAll();
      else drawSegments(ctx, e.stroke, e.from);
    });
  }, [store, paintAll]);

  const flush = useCallback(
    (end = false) => {
      const a = active.current;
      if (!a) return;
      if (a.pending.length === 0 && !end) return;
      const points = a.pending.length ? a.pending : [a.last];
      send('stroke', { stroke_id: a.id, tool: a.tool, color: a.color, size: a.size, points, end });
      a.pending = [];
    },
    [send],
  );

  const stop = useCallback(() => {
    window.clearInterval(flushTimer.current);
    flushTimer.current = undefined;
    active.current = null;
  }, []);

  // Round ended / drawer changed while a stroke was in progress.
  useEffect(() => {
    if (!canDraw) stop();
    return stop;
  }, [canDraw, stop]);

  const toPoint = (e: React.PointerEvent<HTMLCanvasElement>): [number, number] => {
    const r = ref.current!.getBoundingClientRect();
    const clamp = (v: number) => Math.max(0, Math.min(1, v));
    return [clamp((e.clientX - r.left) / r.width), clamp((e.clientY - r.top) / r.height)];
  };

  const onDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!canDraw || e.button > 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const p = toPoint(e);
    const id = `${youId ?? 0}-${Date.now().toString(36)}${counter.current++}`;
    active.current = { id, tool, color, size, pending: [p], last: p };
    store.applyChunk({ stroke_id: id, tool, color, size, points: [p] });
    window.clearInterval(flushTimer.current);
    flushTimer.current = window.setInterval(() => flush(), 40);
  };

  const onMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const a = active.current;
    if (!a || !canDraw) return;
    const p = toPoint(e);
    a.pending.push(p);
    a.last = p;
    store.applyChunk({ stroke_id: a.id, tool: a.tool, color: a.color, size: a.size, points: [p] });
    if (a.pending.length >= 100) flush();
  };

  const onUp = () => {
    if (!active.current) return;
    flush(true);
    stop();
  };

  const clear = () => {
    if (!canDraw) return;
    send('clear_canvas');
    store.reset();
  };

  return (
    <Box>
      <Box
        sx={{
          borderRadius: 4,
          overflow: 'hidden',
          border: `4px solid ${canDraw ? colors.coral : colors.violet}`,
          boxShadow: canDraw ? '0 10px 30px rgba(255,107,74,.25)' : '0 10px 30px rgba(91,75,255,.18)',
          bgcolor: '#fff',
          lineHeight: 0,
        }}
      >
        <canvas
          ref={ref}
          width={W}
          height={H}
          onPointerDown={onDown}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={onUp}
          style={{ width: '100%', aspectRatio: '4 / 3', touchAction: 'none', cursor: canDraw ? 'crosshair' : 'default' }}
        />
      </Box>

      {canDraw && (
        <Paper sx={{ mt: 1.5, p: 1.5 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }}>
            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
              {SWATCHES.map((c) => (
                <Box
                  key={c}
                  role="button"
                  aria-label={`color ${c}`}
                  onClick={() => {
                    setColor(c);
                    setTool('brush');
                  }}
                  sx={{
                    width: 28,
                    height: 28,
                    borderRadius: '50%',
                    bgcolor: c,
                    cursor: 'pointer',
                    border: color === c && tool === 'brush' ? '3px solid #fff' : '3px solid transparent',
                    outline: color === c && tool === 'brush' ? `2px solid ${colors.violet}` : 'none',
                    transition: 'transform .15s',
                    '&:hover': { transform: 'scale(1.15)' },
                  }}
                />
              ))}
            </Stack>
            <ToggleButtonGroup size="small" exclusive value={tool} onChange={(_, v) => v && setTool(v)}>
              <ToggleButton value="brush">🖌️ Brush</ToggleButton>
              <ToggleButton value="eraser">🧽 Eraser</ToggleButton>
            </ToggleButtonGroup>
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ flex: 1, minWidth: 140 }}>
              <Typography variant="caption" color="text.secondary">
                Size
              </Typography>
              <Slider value={size} min={2} max={40} onChange={(_, v) => setSize(v as number)} aria-label="brush size" />
              <Box
                sx={{
                  width: Math.max(6, size),
                  height: Math.max(6, size),
                  maxWidth: 40,
                  maxHeight: 40,
                  borderRadius: '50%',
                  bgcolor: tool === 'eraser' ? '#d1d5db' : color,
                  flexShrink: 0,
                }}
              />
            </Stack>
            <Tooltip title="Clear canvas">
              <IconButton color="secondary" onClick={clear} aria-label="clear canvas">
                <DeleteSweepIcon />
              </IconButton>
            </Tooltip>
          </Stack>
        </Paper>
      )}
    </Box>
  );
}
