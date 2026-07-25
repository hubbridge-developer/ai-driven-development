import { useEffect, useRef } from 'react';
import {
  Box, Typography, Paper, Chip, Avatar, Divider,
  LinearProgress, Card, CardContent, Fade, Stack,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PlayCircleFilledIcon from '@mui/icons-material/PlayCircleFilled';
import StorageIcon from '@mui/icons-material/Storage';
import GitHubIcon from '@mui/icons-material/GitHub';
import CodeIcon from '@mui/icons-material/Code';
import BugReportIcon from '@mui/icons-material/BugReport';
import PublishIcon from '@mui/icons-material/Publish';
import MergeIcon from '@mui/icons-material/MergeType';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import SearchIcon from '@mui/icons-material/Search';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import GavelIcon from '@mui/icons-material/Gavel';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import { PIPELINE_STAGES } from '../types';

export interface LogEntry {
  id: number;
  agent: string;
  subStep: string;
  detail: string;
  model: string;
  timestamp: Date;
}

/** Friendly label for an agent key */
function agentLabel(key: string): string {
  return PIPELINE_STAGES.find((s) => s.key === key)?.label || key;
}

/** Theme color per agent */
const AGENT_THEME: Record<string, { color: string; bgcolor: string; icon: React.ReactNode }> = {
  // POC1 agents
  spec_discovery:      { color: '#00695c', bgcolor: '#e0f2f1', icon: <SearchIcon sx={{ fontSize: 16 }} /> },
  spec_generator:      { color: '#4527a0', bgcolor: '#ede7f6', icon: <AutoFixHighIcon sx={{ fontSize: 16 }} /> },
  spec_validator:      { color: '#bf360c', bgcolor: '#fbe9e7', icon: <FactCheckIcon sx={{ fontSize: 16 }} /> },
  spec_approval_gate:  { color: '#e65100', bgcolor: '#fff3e0', icon: <GavelIcon sx={{ fontSize: 16 }} /> },
  // POC2 agents
  spec_publisher:      { color: '#2e7d32', bgcolor: '#e8f5e9', icon: <PublishIcon sx={{ fontSize: 16 }} /> },
  namespace_resolver:  { color: '#0277bd', bgcolor: '#e1f5fe', icon: <StorageIcon sx={{ fontSize: 16 }} /> },
  code_developer:      { color: '#6a1b9a', bgcolor: '#f3e5f5', icon: <CodeIcon sx={{ fontSize: 16 }} /> },
  code_publisher:      { color: '#e65100', bgcolor: '#fff3e0', icon: <GitHubIcon sx={{ fontSize: 16 }} /> },
  code_approval_gate:  { color: '#f57f17', bgcolor: '#fffde7', icon: <BugReportIcon sx={{ fontSize: 16 }} /> },
  code_review_handoff: { color: '#1565c0', bgcolor: '#e3f2fd', icon: <MergeIcon sx={{ fontSize: 16 }} /> },
};

const DEFAULT_THEME = { color: '#546e7a', bgcolor: '#eceff1', icon: <SmartToyIcon sx={{ fontSize: 16 }} /> };

function getTheme(agent: string) {
  return AGENT_THEME[agent] || DEFAULT_THEME;
}

interface Props {
  entries: LogEntry[];
  running?: boolean;
}

export default function ActivityLog({ entries, running }: Props) {
  const cardRef = useRef<HTMLDivElement>(null);

  // Auto-scroll within the card only (not the page)
  useEffect(() => {
    const el = cardRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }
  }, [entries.length]);

  if (entries.length === 0 && !running) return null;

  // Group entries by agent (consecutive)
  const groups: { agent: string; model: string; entries: LogEntry[] }[] = [];
  for (const entry of entries) {
    const last = groups[groups.length - 1];
    if (last && last.agent === entry.agent) {
      last.entries.push(entry);
      if (!last.model && entry.model) last.model = entry.model;
    } else {
      groups.push({ agent: entry.agent, model: entry.model || '', entries: [entry] });
    }
  }

  return (
    <Card
      ref={cardRef}
      variant="outlined"
      sx={{
        maxHeight: 540,
        overflow: 'auto',
        borderRadius: 2,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.paper',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 2, py: 1.5,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          bgcolor: running ? 'primary.main' : 'grey.800',
          color: '#fff',
          position: 'sticky',
          top: 0,
          zIndex: 1,
        }}
      >
        <SmartToyIcon sx={{ fontSize: 20 }} />
        <Typography variant="subtitle2" fontWeight={700} sx={{ flexGrow: 1 }}>
          Agent Activity
        </Typography>
        {running ? (
          <Chip
            label="LIVE"
            size="small"
            sx={{
              height: 20,
              fontSize: '0.65rem',
              fontWeight: 700,
              bgcolor: 'rgba(255,255,255,0.2)',
              color: '#fff',
              animation: 'pulse 1.5s ease-in-out infinite',
              '@keyframes pulse': {
                '0%, 100%': { opacity: 1 },
                '50%': { opacity: 0.5 },
              },
            }}
          />
        ) : entries.length > 0 ? (
          <Chip
            label="DONE"
            size="small"
            sx={{ height: 20, fontSize: '0.65rem', fontWeight: 700, bgcolor: 'rgba(255,255,255,0.2)', color: '#fff' }}
          />
        ) : null}
      </Box>

      {/* Progress bar while running */}
      {running && (
        <LinearProgress
          sx={{
            height: 2,
            '& .MuiLinearProgress-bar': { animationDuration: '1.8s' },
          }}
        />
      )}

      <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
        {groups.map((group, gIdx) => {
          const theme = getTheme(group.agent);
          const isLastGroup = gIdx === groups.length - 1;

          return (
            <Box key={`${group.agent}-${gIdx}`}>
              {/* Agent section header */}
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  px: 2,
                  py: 1,
                  bgcolor: theme.bgcolor,
                  borderBottom: '1px solid',
                  borderBottomColor: 'divider',
                  ...(gIdx > 0 && { borderTop: '1px solid', borderTopColor: 'divider' }),
                }}
              >
                <Avatar
                  sx={{
                    width: 26, height: 26,
                    bgcolor: theme.color,
                    color: '#fff',
                  }}
                >
                  {theme.icon}
                </Avatar>
                <Typography variant="body2" fontWeight={700} sx={{ color: theme.color }}>
                  {agentLabel(group.agent)}
                </Typography>
                {group.model && (
                  <Chip
                    label={group.model}
                    size="small"
                    sx={{
                      height: 18,
                      fontSize: '0.6rem',
                      fontWeight: 600,
                      bgcolor: 'rgba(0,0,0,0.08)',
                      color: 'text.secondary',
                      borderRadius: '4px',
                    }}
                  />
                )}
                <Chip
                  label={`${group.entries.length} step${group.entries.length > 1 ? 's' : ''}`}
                  size="small"
                  sx={{
                    ml: 'auto',
                    height: 18,
                    fontSize: '0.6rem',
                    fontWeight: 600,
                    bgcolor: 'rgba(0,0,0,0.06)',
                    color: 'text.secondary',
                  }}
                />
              </Box>

              {/* Steps within the agent */}
              <Stack spacing={0} sx={{ px: 2, py: 0.5 }}>
                {group.entries.map((entry, eIdx) => {
                  const isLastEntry = isLastGroup && eIdx === group.entries.length - 1;
                  const isActive = isLastEntry && running;
                  const time = entry.timestamp.toLocaleTimeString([], {
                    hour: '2-digit', minute: '2-digit', second: '2-digit',
                  });

                  return (
                    <Fade in key={entry.id} timeout={400}>
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 1.5,
                          py: 0.8,
                          pl: 0.5,
                          ...(eIdx < group.entries.length - 1 && {
                            borderBottom: '1px solid',
                            borderBottomColor: 'grey.100',
                          }),
                          ...(isActive && {
                            bgcolor: 'action.hover',
                            borderRadius: 1,
                            mx: -0.5,
                            px: 1,
                          }),
                        }}
                      >
                        {/* Status icon */}
                        <Box sx={{ pt: '3px', display: 'flex', alignItems: 'center' }}>
                          {isActive ? (
                            <FiberManualRecordIcon
                              sx={{
                                fontSize: 10,
                                color: theme.color,
                                animation: 'pulse 1.2s ease-in-out infinite',
                              }}
                            />
                          ) : (
                            <CheckCircleIcon
                              sx={{ fontSize: 14, color: 'success.main', opacity: 0.7 }}
                            />
                          )}
                        </Box>

                        {/* Content */}
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Typography
                            variant="body2"
                            fontWeight={isActive ? 600 : 500}
                            sx={{
                              fontSize: '0.82rem',
                              lineHeight: 1.4,
                              color: isActive ? 'text.primary' : 'text.secondary',
                            }}
                          >
                            {entry.subStep}
                          </Typography>
                          {entry.detail && (
                            <Typography
                              variant="caption"
                              display="block"
                              sx={{
                                fontSize: '0.72rem',
                                lineHeight: 1.35,
                                mt: 0.2,
                                color: 'text.disabled',
                                fontStyle: 'italic',
                              }}
                            >
                              {entry.detail}
                            </Typography>
                          )}
                        </Box>

                        {/* Timestamp */}
                        <Typography
                          variant="caption"
                          sx={{
                            fontSize: '0.65rem',
                            color: 'text.disabled',
                            whiteSpace: 'nowrap',
                            pt: '2px',
                            fontFamily: 'monospace',
                          }}
                        >
                          {time}
                        </Typography>
                      </Box>
                    </Fade>
                  );
                })}
              </Stack>
            </Box>
          );
        })}

        {/* Empty state while waiting for first message */}
        {entries.length === 0 && running && (
          <Box sx={{ px: 2, py: 3, textAlign: 'center' }}>
            <PlayCircleFilledIcon sx={{ fontSize: 32, color: 'text.disabled', mb: 1 }} />
            <Typography variant="body2" color="text.secondary">
              Waiting for agent output...
            </Typography>
          </Box>
        )}

      </CardContent>
    </Card>
  );
}
