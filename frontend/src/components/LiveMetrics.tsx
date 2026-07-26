import { useEffect, useState } from 'react';
import { Box, Chip, Fade } from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import PaidIcon from '@mui/icons-material/Paid';

interface Props {
  status: string;
  /** Sum of completed-stage durations (seconds), from token_usage. */
  committedDur: number;
  /** Sum of completed-stage LLM cost (USD), from token_usage. */
  committedCost: number;
  /** Epoch ms when the current stage started (resets each stage). */
  stageStartMs: number;
  /** In-progress LLM cost of the current stage (USD), pushed via WS. */
  liveStageCost: number;
}

function formatDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m ${remainingSeconds}s`;
  if (minutes > 0) return `${minutes}m ${remainingSeconds}s`;
  return `${remainingSeconds}s`;
}

/**
 * Self-contained live time + cost chips. Owns its own 1-second ticker so the
 * running clock updates HERE ONLY — the parent page (with its heavy spec/code
 * panels) no longer re-renders every second, which was causing the flicker.
 */
export default function LiveMetrics({
  status, committedDur, committedCost, stageStartMs, liveStageCost,
}: Props) {
  const running = status === 'running';

  // Local tick: re-render just these chips once per second while running.
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, [running]);

  const liveDur = running
    ? committedDur + (Date.now() - stageStartMs) / 1000
    : committedDur;
  const liveCost = running ? committedCost + liveStageCost : committedCost;
  const show = running || committedDur > 0 || committedCost > 0;

  return (
    <Fade in={show}>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Chip size="small" variant="outlined" icon={<AccessTimeIcon />}
          sx={{ transition: 'all .3s ease' }}
          label={`${formatDuration(liveDur)} total`} />
        <Chip size="small" variant="outlined" color="secondary" icon={<PaidIcon />}
          sx={{ transition: 'all .3s ease' }}
          label={`$${liveCost.toFixed(4)} LLM`} />
      </Box>
    </Fade>
  );
}
