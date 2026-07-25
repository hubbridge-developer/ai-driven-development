import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box } from '@mui/material';
import { keyframes } from '@mui/system';
import { startWorkflow } from '../api/client';

// ---- warm amber-phosphor palette -------------------------------------------
const AMBER = '#ffb84d';        // warm amber glow (primary)
const AMBER_DIM = '#d8a874';    // muted amber for secondary text
const CREAM = '#fff3df';        // warm headline / body text
const CORAL = '#ff8f6b';        // friendly accent (cursor / prompt)
const GO = '#ffd27a';           // CTA fill
const SCREEN = '#181109';       // warm near-black
const PIXEL = "'Press Start 2P', monospace";
const TERM = "'VT323', 'Courier New', monospace";

// ---- animations ------------------------------------------------------------
const blink = keyframes`50% { opacity: 0.2; }`;
const flicker = keyframes`
  0%,19%,21%,55%,57%,100% { opacity: 1; }
  20%,56% { opacity: 0.92; }
`;
const glow = keyframes`
  0%,100% { text-shadow: 0 0 8px rgba(255,184,77,.55), 0 0 22px rgba(255,143,107,.30); }
  50%     { text-shadow: 0 0 12px rgba(255,184,77,.80), 0 0 34px rgba(255,143,107,.45); }
`;
const float = keyframes`
  0%,100% { transform: translateY(0); }
  50%     { transform: translateY(-7px); }
`;

// warm, time-of-day greeting — a small human touch
function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return 'Still up?';
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

function PixelBlock({ sx }: { sx?: object }) {
  return (
    <Box
      aria-hidden
      sx={{
        position: 'absolute',
        width: 12,
        height: 12,
        bgcolor: AMBER,
        boxShadow: `0 0 10px ${AMBER}, 16px 0 0 ${CORAL}, 0 16px 0 ${GO}`,
        opacity: 0.35,
        animation: `${float} 6s ease-in-out infinite`,
        ...sx,
      }}
    />
  );
}

export default function WorkflowStartPage() {
  const [request, setRequest] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [focused, setFocused] = useState(false);
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
      setError(err?.response?.data?.detail || err.message || 'SOMETHING WENT WRONG — LET’S TRY AGAIN');
    } finally {
      setLoading(false);
    }
  };

  const canRun = request.trim().length >= 5 && !loading;

  return (
    <Box
      sx={{
        minHeight: 'calc(100vh - 64px)',
        bgcolor: SCREEN,
        color: AMBER,
        position: 'relative',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        px: 2,
        py: { xs: 5, md: 8 },
        // warm radial glow + faint grid
        backgroundImage: `
          radial-gradient(1000px 520px at 50% -8%, rgba(255,163,71,0.16), transparent 62%),
          radial-gradient(700px 400px at 100% 110%, rgba(255,143,107,0.10), transparent 60%),
          linear-gradient(rgba(255,184,77,0.045) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,184,77,0.045) 1px, transparent 1px)`,
        backgroundSize: 'auto, auto, 34px 34px, 34px 34px',
        // soft CRT scanlines
        '&::after': {
          content: '""',
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'repeating-linear-gradient(0deg, rgba(0,0,0,0.16) 0px, rgba(0,0,0,0.16) 1px, transparent 1px, transparent 3px)',
          animation: `${flicker} 7s infinite`,
          zIndex: 2,
        },
      }}
    >
      <PixelBlock sx={{ top: '15%', left: '11%', animationDelay: '0s' }} />
      <PixelBlock sx={{ bottom: '18%', right: '13%', animationDelay: '1.6s' }} />
      <PixelBlock sx={{ top: '24%', right: '20%', animationDelay: '3.1s', opacity: 0.22 }} />

      {/* console */}
      <Box
        component="form"
        onSubmit={handleSubmit}
        sx={{
          position: 'relative',
          zIndex: 3,
          width: '100%',
          maxWidth: 780,
          border: `2px solid ${AMBER}`,
          borderRadius: 3,
          bgcolor: 'rgba(24,17,9,0.78)',
          boxShadow: `0 0 0 4px #0d0906, 0 20px 60px rgba(0,0,0,0.55), 0 0 46px rgba(255,163,71,0.22), inset 0 0 70px rgba(255,163,71,0.06)`,
          p: { xs: 2.5, md: 4 },
        }}
      >
        {/* warm greeting */}
        <Box sx={{ fontFamily: TERM, fontSize: 22, color: AMBER_DIM, mb: 0.5 }}>
          {greeting()} — What are we building?
        </Box>

        {/* headline */}
        <Box
          sx={{
            fontFamily: PIXEL,
            fontSize: { xs: 22, sm: 32, md: 42 },
            lineHeight: 1.25,
            color: CREAM,
            animation: `${glow} 3s ease-in-out infinite`,
            mb: 2,
          }}
        >
          YOUR
          <br />
          MOVE
          <Box component="span" sx={{ color: CORAL, animation: `${blink} 1s step-start infinite` }}>_</Box>
        </Box>

        <Box sx={{ fontFamily: TERM, fontSize: 23, color: CREAM, mb: 3, lineHeight: 1.25, maxWidth: 560 }}>
          Just say it in plain words — a feature, a fix, or a rough idea. I’ll draft the spec,
          write the code, and run the tests. You stay in charge and approve every step.
        </Box>

        {/* terminal input */}
        <Box
          sx={{
            display: 'flex', gap: 1,
            border: `1px solid ${focused ? AMBER : 'rgba(255,184,77,0.55)'}`,
            borderRadius: 2,
            bgcolor: 'rgba(0,0,0,0.4)',
            p: 1.5,
            transition: 'border-color .15s ease, box-shadow .15s ease',
            boxShadow: focused
              ? `inset 0 0 22px rgba(255,163,71,0.14), 0 0 0 3px rgba(255,163,71,0.14)`
              : 'inset 0 0 22px rgba(255,163,71,0.08)',
          }}
        >
          <Box sx={{ fontFamily: TERM, fontSize: 32, color: CORAL, lineHeight: 1.1, userSelect: 'none' }}>&gt;</Box>
          <Box
            component="textarea"
            value={request}
            onChange={(e: any) => setRequest(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            rows={3}
            spellCheck={false}
            autoFocus
            placeholder="e.g. let people reset their password by email…"
            sx={{
              flex: 1, resize: 'vertical', border: 'none', outline: 'none',
              background: 'transparent', color: CREAM, fontFamily: TERM,
              fontSize: 30, lineHeight: 1.3, caretColor: CORAL,
              '::placeholder': { color: 'rgba(216,168,116,0.55)' },
            }}
          />
        </Box>

        {/* error — gentle, not alarming */}
        {error && (
          <Box sx={{ mt: 2, fontFamily: TERM, fontSize: 22, color: '#ff9d7a' }}>
            ⚠ {String(error).toUpperCase()}
          </Box>
        )}

        {/* actions */}
        <Box sx={{ mt: 3.5, display: 'flex', alignItems: 'center', gap: 2.5, flexWrap: 'wrap' }}>
          <Box
            component="button"
            type="submit"
            disabled={!canRun}
            sx={{
              fontFamily: PIXEL, fontSize: 13, color: '#2a1602',
              bgcolor: canRun ? GO : '#4a3a22',
              border: 'none', cursor: canRun ? 'pointer' : 'not-allowed',
              px: 3, py: 1.75, borderRadius: 1.5,
              boxShadow: canRun ? `3px 3px 0 #7a4a15, 0 0 22px rgba(255,184,77,0.5)` : '3px 3px 0 #2a1c0c',
              transition: 'transform .06s ease, box-shadow .06s ease, filter .15s ease',
              '&:hover': canRun ? { filter: 'brightness(1.06)' } : {},
              '&:active': canRun ? { transform: 'translate(3px,3px)', boxShadow: '0 0 0 #7a4a15' } : {},
            }}
          >
            {loading ? 'ON IT…' : "LET’S BUILD ▶"}
          </Box>
        </Box>

        {/* lean status footer */}
        <Box
          sx={{
            mt: 3,
            pt: 1.5,
            borderTop: '1px solid rgba(216,168,116,0.22)',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            fontFamily: PIXEL, fontSize: 8, color: AMBER_DIM, letterSpacing: '0.05em',
          }}
        >
          <span>ADD://NEW-TASK</span>
          <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 0.6 }}>
            <Box component="span" sx={{
              width: 6, height: 6, bgcolor: '#7CFC9A', borderRadius: '1px',
              boxShadow: '0 0 6px #7CFC9A', animation: `${blink} 1.6s step-start infinite`,
            }} />
            READY WHEN YOU ARE
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
