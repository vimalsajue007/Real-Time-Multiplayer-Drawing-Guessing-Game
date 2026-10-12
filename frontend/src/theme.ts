import { createTheme } from '@mui/material/styles';

export const colors = {
  violet: '#5B4BFF',
  coral: '#FF6B4A',
  sun: '#FFC83D',
  teal: '#14B8A6',
  ink: '#1E1B3A',
  bg: '#F7F5FF',
};

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: colors.violet, light: '#8A7FFF', dark: '#3F32C9', contrastText: '#fff' },
    secondary: { main: colors.coral, contrastText: '#fff' },
    success: { main: colors.teal },
    warning: { main: colors.sun },
    background: { default: colors.bg, paper: '#FFFFFF' },
    text: { primary: colors.ink, secondary: '#5E5A80' },
  },
  shape: { borderRadius: 16 },
  typography: {
    fontFamily: '"Inter", "Helvetica", "Arial", sans-serif',
    h1: { fontFamily: '"Fredoka", sans-serif', fontWeight: 700 },
    h2: { fontFamily: '"Fredoka", sans-serif', fontWeight: 700 },
    h3: { fontFamily: '"Fredoka", sans-serif', fontWeight: 600 },
    h4: { fontFamily: '"Fredoka", sans-serif', fontWeight: 600 },
    h5: { fontFamily: '"Fredoka", sans-serif', fontWeight: 600 },
    h6: { fontFamily: '"Fredoka", sans-serif', fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 700 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          minHeight: '100vh',
          background:
            'radial-gradient(circle at 8% 0%, #FFE7C2 0, transparent 32%), radial-gradient(circle at 100% 8%, #DAD5FF 0, transparent 38%), radial-gradient(circle at 50% 100%, #CFF5EE 0, transparent 30%), #F7F5FF',
          backgroundAttachment: 'fixed',
        },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 14, paddingInline: 20 },
        containedPrimary: { boxShadow: '0 6px 16px rgba(91,75,255,.28)' },
        containedSecondary: { boxShadow: '0 6px 16px rgba(255,107,74,.28)' },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: 'none' },
        rounded: { boxShadow: '0 8px 28px rgba(60,48,160,.08)', border: '1px solid rgba(91,75,255,.08)' },
      },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
    MuiTextField: { defaultProps: { size: 'medium' } },
  },
});
