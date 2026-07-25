import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Container, Typography, TextField, Button, Paper, Alert, Chip, Stack,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import { startWorkflow } from '../api/client';
import { BRAND } from '../theme';

const EXAMPLES = [
  'I want a password reset feature with email verification',
  'Add rate limiting to the payments API — 100 req/min per user',
  'Fix the session expiry bug where users get logged out after 5 minutes',
  'Add OAuth2 login support with Google and GitHub providers',
];

export default function WorkflowStartPage() {
  const [request, setRequest] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!request.trim() || request.trim().length < 5) return;

    setLoading(true);
    setError('');
    try {
      const { workflow_id } = await startWorkflow(request.trim());
      navigate(`/workflow/${workflow_id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to start workflow');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Hero */}
      <Box
        sx={{
          background: BRAND.gradient,
          color: '#fff',
          pt: { xs: 6, md: 8 },
          pb: { xs: 10, md: 12 },
          textAlign: 'center',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <Container maxWidth="md">
          <Chip
            icon={<AutoAwesomeIcon sx={{ color: '#fff !important' }} />}
            label="AI proposes · humans approve"
            sx={{ bgcolor: 'rgba(255,255,255,0.16)', color: '#fff', mb: 2, fontWeight: 600 }}
          />
          <Typography variant="h3" sx={{ fontWeight: 900, letterSpacing: '-0.03em', mb: 1.5 }}>
            Turn a sentence into shipped software
          </Typography>
          <Typography sx={{ opacity: 0.92, fontSize: 18, maxWidth: 620, mx: 'auto' }}>
            {BRAND.tagline} Describe what you need — {BRAND.short} writes the spec, generates the
            code, runs the tests, and pauses for your sign-off at every gate.
          </Typography>
        </Container>
      </Box>

      <Container maxWidth="md" sx={{ mt: { xs: -6, md: -7 } }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Paper sx={{ p: { xs: 2.5, md: 3.5 } }} elevation={3}>
          <Typography variant="h6" gutterBottom>
            New specification
          </Typography>
          <form onSubmit={handleSubmit}>
            <TextField
              fullWidth
              multiline
              rows={4}
              label="What do you need?"
              placeholder="e.g. I want a password reset feature with email verification and rate limiting"
              value={request}
              onChange={(e) => setRequest(e.target.value)}
              sx={{ mb: 2 }}
              autoFocus
            />
            <Stack direction="row" alignItems="center" spacing={2} flexWrap="wrap" useFlexGap>
              <Button
                type="submit"
                variant="contained"
                size="large"
                startIcon={<PlayArrowIcon />}
                disabled={loading || request.trim().length < 5}
              >
                {loading ? 'Starting…' : 'Start Workflow'}
              </Button>
              <Stack direction="row" alignItems="center" spacing={0.5} sx={{ color: 'text.secondary' }}>
                <VerifiedUserIcon fontSize="small" />
                <Typography variant="caption">
                  Two human approval gates · tests must pass to merge
                </Typography>
              </Stack>
            </Stack>
          </form>
        </Paper>

        <Paper sx={{ p: 3, mt: 3, background: BRAND.gradientSoft }} variant="outlined">
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Try an example
          </Typography>
          <Stack spacing={0.5}>
            {EXAMPLES.map((example) => (
              <Typography
                key={example}
                variant="body2"
                sx={{
                  cursor: 'pointer',
                  py: 0.5,
                  color: 'text.primary',
                  '&:hover': { color: 'primary.main', textDecoration: 'underline' },
                }}
                onClick={() => setRequest(example)}
              >
                → {example}
              </Typography>
            ))}
          </Stack>
        </Paper>
      </Container>
    </>
  );
}
