import type { StrokeChunk } from './types';

export interface Stroke {
  id: string;
  tool: 'brush' | 'eraser';
  color: string;
  size: number;
  points: [number, number][];
}

export type CanvasEvent = { kind: 'reset' } | { kind: 'segment'; stroke: Stroke; from: number };
type Listener = (e: CanvasEvent) => void;

/**
 * Holds the shared drawing as a list of stroke operations (never as an image).
 * Both local drawing and remote strokes go through applyChunk, so the canvas
 * has a single rendering path and can be fully rebuilt from `strokes` at any time.
 */
export class CanvasStore {
  strokes: Stroke[] = [];
  private index = new Map<string, Stroke>();
  private listeners = new Set<Listener>();

  subscribe(l: Listener): () => void {
    this.listeners.add(l);
    return () => {
      this.listeners.delete(l);
    };
  }

  private emit(e: CanvasEvent) {
    this.listeners.forEach((l) => l(e));
  }

  reset(strokes: Stroke[] = []) {
    this.strokes = strokes.map((s) => ({ ...s, points: [...s.points] }));
    this.index = new Map(this.strokes.map((s) => [s.id, s]));
    this.emit({ kind: 'reset' });
  }

  applyChunk(c: Pick<StrokeChunk, 'stroke_id' | 'tool' | 'color' | 'size' | 'points'>) {
    let s = this.index.get(c.stroke_id);
    if (!s) {
      s = { id: c.stroke_id, tool: c.tool, color: c.color, size: c.size, points: [] };
      this.strokes.push(s);
      this.index.set(s.id, s);
    }
    const from = s.points.length;
    for (const p of c.points) s.points.push(p);
    this.emit({ kind: 'segment', stroke: s, from });
  }
}
