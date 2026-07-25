import { createTheme, alpha } from '@mui/material/styles';

// ---------------------------------------------------------------------------
// Brand
// ---------------------------------------------------------------------------
export const BRAND = {
  name: 'AI-Driven Development',
  short: 'AIDD',
  tagline: 'Spec-driven delivery — AI-built, human-approved.',
  // Signature gradient used across the app shell, brand mark and CTAs.
  gradient: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 45%, #d946ef 100%)',
  gradientSoft: 'linear-gradient(135deg, #eef2ff 0%, #faf5ff 100%)',
};

const INDIGO = '#4f46e5';
const VIOLET = '#7c3aed';

// ---------------------------------------------------------------------------
// Theme — a clean, modern SaaS look with soft shadows and rounded surfaces.
// ---------------------------------------------------------------------------
export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: INDIGO, light: '#6366f1', dark: '#3730a3', contrastText: '#fff' },
    secondary: { main: VIOLET, light: '#a78bfa', dark: '#5b21b6' },
    success: { main: '#16a34a' },
    warning: { main: '#d97706' },
    error: { main: '#dc2626' },
    info: { main: '#2563eb' },
    background: { default: '#f6f7fb', paper: '#ffffff' },
    text: { primary: '#0f172a', secondary: '#64748b' },
    divider: alpha('#0f172a', 0.08),
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: '"Inter", "Segoe UI", "Roboto", "Helvetica", "Arial", sans-serif',
    h4: { fontWeight: 800, letterSpacing: '-0.02em' },
    h5: { fontWeight: 800, letterSpacing: '-0.02em' },
    h6: { fontWeight: 700, letterSpacing: '-0.01em' },
    subtitle1: { fontWeight: 600 },
    subtitle2: { fontWeight: 600 },
    button: { fontWeight: 600, textTransform: 'none', letterSpacing: 0 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: '#f6f7fb',
          backgroundImage:
            'radial-gradient(1200px 600px at 100% -10%, rgba(139,92,246,0.10), transparent 60%),' +
            'radial-gradient(900px 500px at -10% 0%, rgba(99,102,241,0.10), transparent 55%)',
          backgroundAttachment: 'fixed',
        },
        '::selection': { background: alpha(VIOLET, 0.18) },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: 'none' },
        elevation1: { boxShadow: '0 1px 2px rgba(16,24,40,0.05), 0 1px 3px rgba(16,24,40,0.06)' },
        elevation2: { boxShadow: '0 4px 12px rgba(16,24,40,0.06), 0 2px 6px rgba(16,24,40,0.05)' },
        elevation3: { boxShadow: '0 12px 32px rgba(16,24,40,0.10)' },
      },
    },
    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          border: `1px solid ${alpha('#0f172a', 0.08)}`,
          borderRadius: 16,
          transition: 'box-shadow .2s ease, transform .2s ease, border-color .2s ease',
        },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 10, paddingInline: 18, paddingBlock: 8 },
        containedPrimary: {
          background: BRAND.gradient,
          boxShadow: '0 6px 16px rgba(124,58,237,0.28)',
          '&:hover': { filter: 'brightness(1.05)', boxShadow: '0 8px 22px rgba(124,58,237,0.34)' },
        },
      },
    },
    MuiChip: {
      styleOverrides: { root: { fontWeight: 600, borderRadius: 8 } },
    },
    MuiTextField: {
      defaultProps: { variant: 'outlined' },
    },
    MuiOutlinedInput: {
      styleOverrides: { root: { borderRadius: 12 } },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          background: 'rgba(255,255,255,0.72)',
          backdropFilter: 'saturate(180%) blur(12px)',
          color: '#0f172a',
          borderBottom: `1px solid ${alpha('#0f172a', 0.08)}`,
          boxShadow: 'none',
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: { borderRadius: 8, fontSize: 12, background: '#0f172a' },
      },
    },
  },
});

export default theme;
