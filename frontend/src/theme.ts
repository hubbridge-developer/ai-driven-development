import { createTheme, alpha } from '@mui/material/styles';

// ---------------------------------------------------------------------------
// Brand
// ---------------------------------------------------------------------------
export const BRAND = {
  name: 'AI-Driven Development',
  short: 'ADD',
  tagline: 'Spec-driven delivery — AI-built, human-approved.',
  // Signature gradient used across the app shell, brand mark and CTAs.
  // Enterprise deep-pine → teal → emerald (distinctive, not blue, not purple).
  gradient: 'linear-gradient(135deg, #0b3b3a 0%, #0d9488 52%, #10b981 100%)',
  gradientSoft: 'linear-gradient(135deg, #ecfdf5 0%, #f0fdfa 100%)',
};

const TEAL = '#0d9488'; // primary (brand)
const PINE = '#0f5f5c'; // deep accent (dark)
const AMBER = '#f59e0b'; // warm secondary accent
const INK = '#241d14';  // warm near-black text

// ---------------------------------------------------------------------------
// Theme — warm, approachable enterprise: emerald brand on soft cream neutrals
// with a warm amber accent. Warmth lowers perceived effort and feels inviting.
// ---------------------------------------------------------------------------
export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: TEAL, light: '#14b8a6', dark: PINE, contrastText: '#fff' },
    secondary: { main: AMBER, light: '#fbbf24', dark: '#b45309' },
    success: { main: '#15803d' },
    warning: { main: '#b45309' },
    error: { main: '#b91c1c' },
    info: { main: '#0369a1' },
    background: { default: '#faf6ef', paper: '#fffdf8' },
    text: { primary: INK, secondary: '#6b6153' },
    divider: alpha(INK, 0.09),
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
          backgroundColor: '#faf6ef',
          backgroundImage:
            'radial-gradient(1200px 600px at 100% -10%, rgba(245,158,11,0.10), transparent 60%),' +
            'radial-gradient(900px 500px at -10% 0%, rgba(13,148,136,0.09), transparent 55%)',
          backgroundAttachment: 'fixed',
        },
        '::selection': { background: alpha(AMBER, 0.22) },
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
          border: `1px solid ${alpha('#241d14', 0.08)}`,
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
          boxShadow: '0 6px 16px rgba(13,148,136,0.28)',
          '&:hover': { filter: 'brightness(1.05)', boxShadow: '0 8px 22px rgba(13,148,136,0.34)' },
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
          background: 'rgba(255,251,243,0.78)',
          backdropFilter: 'saturate(180%) blur(12px)',
          color: '#241d14',
          borderBottom: `1px solid ${alpha('#241d14', 0.08)}`,
          boxShadow: 'none',
        },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: { borderRadius: 8, fontSize: 12, background: '#241d14' },
      },
    },
  },
});

export default theme;
