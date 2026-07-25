import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box } from '@mui/material';
import { keyframes } from '@mui/system';
import { startWorkflow } from '../api/client';

// ---- retro palette ---------------------------------------------------------
const NEON = '#3ef2a0';       // emerald neon (ties to brand)
const NEON_DIM = '#7fd8b5';
const AMBER = '#ffcf4d';
const SCREEN = '#070c0a';
const PIXEL = "'Press Start 2P', monospace";
const TERM = "'VT323', 'Courier New', monospace";

// ---- animations ------------------------------------------------------------
const blink = keyframes`50% { opacity: 0.15; }`;
const flicker = keyframes`
  0%,19%,21%,55%,57%,100% { opacity: 1; }
  20%,56% { opacity: 0.86; }
`;
const glow = keyframes`
  0%,100% { text-shadow: 0 0 6px ${NEON}, 0 0 18px rgba(62,242,160,.55), 2px 0 rgba(255,0,128,.35), -2px 0 rgba(0,229,255,.35); }
  50%     { text-shadow: 0 0 10px ${NEON}, 0 0 28px rgba(62,242,160,.75), 2px 0 rgba(255,0,128,.35), -2px 0 rgba(0,229,255,.35); }
`;
const float = keyframes`
  0%,100% { transform: translateY(0); }
  50%     { transform: translateY(-8px); }
`;

// small decorative pixel block
function PixelBlock({ sx }: { sx?: object }) {
  return (
    <Box
      aria-hidden
      sx={{
        position: 'absolute',
        width: 14,
        height: 14,
        bgcolor: NEON,
        boxShadow: `0 0 10px ${NEON}, 18px 0 0 ${AMBER}, 0 18px 0 rgba(0,229,255,.9)`,
        opacity: 0.5,
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
      setError(err?.response?.data?.detail || err.message || 'FAILED TO START WORKFLOW');
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
        color: NEON,
        position: 'relative',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        px: 2,
        py: { xs: 5, md: 8 },
        // grid glow backdrop
        backgroundImage: `
          radial-gradient(900px 500px at 50% -10%, rgba(62,242,160,0.12), transparent 60%),
          linear-gradient(rgba(62,242,160,0.06) 1px, transparent 1px),
          linear-gradient(90deg, rgba(62,242,160,0.06) 1px, transparent 1px)`,
        backgroundSize: 'auto, 32px 32px, 32px 32px',
        // CRT scanlines + flicker
        '&::after': {
          content: '""',
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'repeating-linear-gradient(0deg, rgba(0,0,0,0.28) 0px, rgba(0,0,0,0.28) 1px, transparent 1px, transparent 3px)',
          animation: `${flicker} 6s infinite`,
          zIndex: 2,
        },
      }}
    >
      {/* floating pixel decor */}
      <PixelBlock sx={{ top: '14%', left: '10%', animationDelay: '0s' }} />
      <PixelBlock sx={{ bottom: '16%', right: '12%', animationDelay: '1.5s' }} />
      <PixelBlock sx={{ top: '22%', right: '18%', animationDelay: '3s', opacity: 0.35 }} />

      {/* console */}
      <Box
        component="form"
        onSubmit={handleSubmit}
        sx={{
          position: 'relative',
          zIndex: 3,
          width: '100%',
          maxWidth: 820,
          border: `2px solid ${NEON}`,
          borderRadius: 2,
          bgcolor: 'rgba(4,10,8,0.72)',
          boxShadow: `0 0 0 4px #000, 0 0 40px rgba(62,242,160,0.25), inset 0 0 60px rgba(62,242,160,0.06)`,
          p: { xs: 2.5, md: 4 },
        }}
      >
        {/* status bar */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontFamily: PIXEL,
            fontSize: 9,
            color: NEON_DIM,
            letterSpacing: '0.05em',
            mb: { xs: 3, md: 4 },
          }}
        >
          <span>ADD://NEW-TASK</span>
          <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            <Box
              component="span"
              sx={{
                width: 8, height: 8, bgcolor: NEON, borderRadius: '2px',
                boxShadow: `0 0 8px ${NEON}`, animation: `${blink} 1.4s step-start infinite`,
              }}
            />
            ONLINE
          </Box>
        </Box>

        {/* headline */}
        <Box
          sx={{
            fontFamily: PIXEL,
            fontSize: { xs: 20, sm: 30, md: 40 },
            lineHeight: 1.25,
            color: '#eafff5',
            animation: `${glow} 2.8s ease-in-out infinite`,
            mb: 2,
          }}
        >
          YOUR
          <br />
          MOVE
          <Box component="span" sx={{ color: AMBER }}>_</Box>
        </Box>

        <Box sx={{ fontFamily: TERM, fontSize: 24, color: NEON_DIM, mb: 3, lineHeight: 1.2 }}>
          Describe a feature, fix, or change. ADD writes the spec, builds the code,
          runs the tests — you sign off at every gate.
        </Box>

        {/* terminal input */}
        <Box
          sx={{
            display: 'flex',
            gap: 1,
            border: `1px solid ${NEON}`,
            borderRadius: 1,
            bgcolor: 'rgba(0,0,0,0.55)',
            p: 1.5,
            boxShadow: `inset 0 0 20px rgba(62,242,160,0.10)`,
          }}
        >
          <Box sx={{ fontFamily: TERM, fontSize: 26, color: AMBER, lineHeight: 1.1, userSelect: 'none' }}>
            &gt;
          </Box>
          <Box
            component="textarea"
            value={request}
            onChange={(e: any) => setRequest(e.target.value)}
            rows={3}
            spellCheck={false}
            autoFocus
            placeholder="e.g. add a password reset feature with email verification and rate limiting_"
            sx={{
              flex: 1,
              resize: 'vertical',
              border: 'none',
              outline: 'none',
              background: 'transparent',
              color: NEON,
              fontFamily: TERM,
              fontSize: 24,
              lineHeight: 1.25,
              caretColor: NEON,
              '::placeholder': { color: 'rgba(127,216,181,0.5)' },
            }}
          />
        </Box>

        {/* error */}
        {error && (
          <Box sx={{ mt: 2, fontFamily: TERM, fontSize: 22, color: '#ff5c7a' }}>
            ⚠ ERROR: {String(error).toUpperCase()}
          </Box>
        )}

        {/* actions */}
        <Box sx={{ mt: 3.5, display: 'flex', alignItems: 'center', gap: 3, flexWrap: 'wrap' }}>
          <Box
            component="button"
            type="submit"
            disabled={!canRun}
            sx={{
              fontFamily: PIXEL,
              fontSize: 13,
              color: '#04140d',
              bgcolor: canRun ? NEON : '#2b4b3d',
              border: 'none',
              cursor: canRun ? 'pointer' : 'not-allowed',
              px: 3,
              py: 1.75,
              borderRadius: 0,
              boxShadow: canRun ? `4px 4px 0 #04140d, 0 0 18px rgba(62,242,160,0.5)` : '4px 4px 0 #04140d',
              transition: 'transform .05s ease, box-shadow .05s ease',
              '&:active': canRun
                ? { transform: 'translate(4px,4px)', boxShadow: '0 0 0 #04140d' }
                : {},
            }}
          >
            {loading ? 'RUNNING…' : '▶ RUN BUILD'}
          </Box>

          <Box sx={{ display: 'flex', gap: 1.25, flexWrap: 'wrap', fontFamily: PIXEL, fontSize: 8 }}>
            {['2 HUMAN GATES', 'TESTS MUST PASS', 'AUTO PR'].map((t) => (
              <Box
                key={t}
                sx={{
                  border: `1px solid ${NEON_DIM}`,
                  color: NEON_DIM,
                  px: 1,
                  py: 0.75,
                  letterSpacing: '0.05em',
                }}
              >
                [ {t} ]
              </Box>
            ))}
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
