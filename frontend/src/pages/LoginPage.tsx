import { useState, type FormEvent } from 'react';
import {
  Box, Paper, TextField, Button, Typography, Stack, Alert, InputAdornment,
  IconButton, Chip,
} from '@mui/material';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import EmailOutlined from '@mui/icons-material/EmailOutlined';
import LockOutlined from '@mui/icons-material/LockOutlined';
import ArrowForward from '@mui/icons-material/ArrowForward';
import BrandMark from '../components/BrandMark';
import { BRAND } from '../theme';
import { login, DEMO_CREDENTIALS } from '../auth';

export default function LoginPage({ onSuccess }: { onSuccess: () => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    // Tiny delay so the button shows a real "signing in" beat.
    setTimeout(() => {
      if (login(email, password)) {
        onSuccess();
      } else {
        setError('Invalid credentials. Try the demo account below.');
        setLoading(false);
      }
    }, 350);
  };

  const fillDemo = () => {
    setEmail(DEMO_CREDENTIALS.email);
    setPassword(DEMO_CREDENTIALS.password);
    setError('');
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '1.05fr 1fr' },
      }}
    >
      {/* Left: brand panel (hidden on small screens) */}
      <Box
        sx={{
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          justifyContent: 'space-between',
          p: 6,
          color: '#fff',
          background: BRAND.gradient,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <Box sx={{ position: 'relative', zIndex: 1 }}>
          <Box sx={{ filter: 'brightness(0) invert(1)', width: 'fit-content' }}>
            <BrandMark />
          </Box>
        </Box>

        <Box sx={{ position: 'relative', zIndex: 1 }}>
          <Typography variant="h3" fontWeight={800} letterSpacing="-0.03em" gutterBottom>
            {BRAND.name}
          </Typography>
          <Typography variant="h6" fontWeight={500} sx={{ opacity: 0.92, maxWidth: 460 }}>
            {BRAND.tagline}
          </Typography>
          <Stack direction="row" spacing={1} sx={{ mt: 3, flexWrap: 'wrap', gap: 1 }}>
            {['Spec-driven', 'AI-built', 'Human-approved'].map((t) => (
              <Chip
                key={t}
                label={t}
                size="small"
                sx={{ bgcolor: 'rgba(255,255,255,0.16)', color: '#fff', fontWeight: 600 }}
              />
            ))}
          </Stack>
        </Box>

        <Typography variant="caption" sx={{ opacity: 0.7, position: 'relative', zIndex: 1 }}>
          © {BRAND.short} — Enterprise preview
        </Typography>

        {/* soft glow accents */}
        <Box sx={{
          position: 'absolute', width: 520, height: 520, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,255,255,0.18), transparent 70%)',
          top: -160, right: -160,
        }} />
        <Box sx={{
          position: 'absolute', width: 420, height: 420, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(245,158,11,0.30), transparent 70%)',
          bottom: -140, left: -120,
        }} />
      </Box>

      {/* Right: sign-in form */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', p: { xs: 3, sm: 6 } }}>
        <Paper elevation={3} sx={{ p: { xs: 3, sm: 5 }, width: '100%', maxWidth: 420, borderRadius: 4 }}>
          <Box sx={{ display: { xs: 'block', md: 'none' }, mb: 2 }}>
            <BrandMark />
          </Box>
          <Typography variant="h4" fontWeight={800} gutterBottom>Welcome back</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Sign in to continue to your workspace.
          </Typography>

          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          <Box component="form" onSubmit={submit}>
            <Stack spacing={2}>
              <TextField
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                fullWidth
                autoFocus
                autoComplete="username"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start"><EmailOutlined fontSize="small" /></InputAdornment>
                  ),
                }}
              />
              <TextField
                label="Password"
                type={show ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                fullWidth
                autoComplete="current-password"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start"><LockOutlined fontSize="small" /></InputAdornment>
                  ),
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton onClick={() => setShow((s) => !s)} edge="end" size="small">
                        {show ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
              <Button
                type="submit"
                variant="contained"
                size="large"
                fullWidth
                disabled={loading}
                endIcon={<ArrowForward />}
                sx={{ py: 1.3, fontSize: '1rem' }}
              >
                {loading ? 'Signing in…' : 'Sign in'}
              </Button>
            </Stack>
          </Box>

          {/* Demo helper */}
          <Box
            sx={{
              mt: 3, p: 2, borderRadius: 3,
              bgcolor: 'action.hover', border: '1px dashed', borderColor: 'divider',
            }}
          >
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              Demo account
            </Typography>
            <Typography variant="body2" fontFamily="monospace">
              {DEMO_CREDENTIALS.email} · {DEMO_CREDENTIALS.password}
            </Typography>
            <Button size="small" onClick={fillDemo} sx={{ mt: 1, px: 0 }}>
              Use demo credentials
            </Button>
          </Box>
        </Paper>
      </Box>
    </Box>
  );
}
