import { memo } from 'react';
import { Box, Typography, Paper, Alert, Chip, Stack } from '@mui/material';

interface Props {
  specContent: string;
  specId: string;
  lowConfidenceSections?: string[];
  duplicateWarning?: string | null;
  consistencyWarnings?: string[];
}

// Memoized: the parent page re-renders on every WS/poll tick, but this heavy
// section-parsing view should only re-render when its own props change.
function SpecViewer({ specContent, specId, lowConfidenceSections, duplicateWarning, consistencyWarnings }: Props) {
  if (!specContent) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography color="text.secondary">No spec generated yet.</Typography>
      </Paper>
    );
  }

  // Parse sections for structured display
  const sections = parseSections(specContent);

  return (
    <Box>
      {duplicateWarning && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {duplicateWarning}
        </Alert>
      )}

      {consistencyWarnings && consistencyWarnings.length > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          <Typography variant="subtitle2">Consistency Check Warnings:</Typography>
          {consistencyWarnings.map((w, i) => (
            <Typography key={i} variant="body2">• {w}</Typography>
          ))}
        </Alert>
      )}

      {lowConfidenceSections && lowConfidenceSections.length > 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>
          <Typography variant="subtitle2">Low confidence sections:</Typography>
          {lowConfidenceSections.map((s, i) => (
            <Typography key={i} variant="body2">• {s}</Typography>
          ))}
        </Alert>
      )}

      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        <Chip label={specId} color="primary" variant="outlined" />
        {sections.spec_header?.namespace && (
          <Chip label={`ns: ${sections.spec_header.namespace}`} size="small" />
        )}
        {sections.spec_header?.type && (
          <Chip label={sections.spec_header.type} size="small" color="info" />
        )}
      </Stack>

      {Object.entries(sections).map(([name, content]) => (
        <Paper key={name} sx={{ p: 2, mb: 2 }} variant="outlined">
          <Typography variant="subtitle1" fontWeight={700} color="primary" gutterBottom>
            &lt;{name}&gt;
          </Typography>
          <Box
            component="pre"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: 'monospace',
              fontSize: '0.85rem',
              m: 0,
              lineHeight: 1.6,
            }}
          >
            {typeof content === 'string' ? content : JSON.stringify(content, null, 2)}
          </Box>
        </Paper>
      ))}

      {/* Raw fallback */}
      <Paper sx={{ p: 2, mt: 2, bgcolor: 'grey.50' }} variant="outlined">
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Raw Spec
        </Typography>
        <Box
          component="pre"
          sx={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: 'monospace',
            fontSize: '0.8rem',
            m: 0,
            maxHeight: 400,
            overflow: 'auto',
          }}
        >
          {specContent}
        </Box>
      </Paper>
    </Box>
  );
}

function parseSections(content: string): Record<string, unknown> {
  const sections: Record<string, string> = {};
  const tagPattern = /<(\w+)>([\s\S]*?)<\/\1>/g;
  let match;
  while ((match = tagPattern.exec(content)) !== null) {
    sections[match[1]] = match[2].trim();
  }

  // Try to parse spec_header as structured
  const result: Record<string, unknown> = {};
  for (const [key, val] of Object.entries(sections)) {
    if (key === 'spec_header') {
      try {
        const parsed: Record<string, string> = {};
        val.split('\n').forEach((line) => {
          const colonIdx = line.indexOf(':');
          if (colonIdx > 0) {
            parsed[line.slice(0, colonIdx).trim()] = line.slice(colonIdx + 1).trim();
          }
        });
        result[key] = parsed;
      } catch {
        result[key] = val;
      }
    } else {
      result[key] = val;
    }
  }
  return result;
}

export default memo(SpecViewer);
