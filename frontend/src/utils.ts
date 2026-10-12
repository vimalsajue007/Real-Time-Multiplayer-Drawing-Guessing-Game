const PALETTE = ['#FF6B4A', '#5B4BFF', '#14B8A6', '#F59E0B', '#EC4899', '#0EA5E9', '#84CC16', '#8B5CF6'];

export function avatarColor(name: string): string {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export function initials(name: string): string {
  return (Array.from(name.trim())[0] ?? '?').toUpperCase();
}

export const medal = (rank: number) => (rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `${rank}`);
