import { useState } from 'react';
import {
  Box, Button, TextField, Typography, Stack, Alert, Link as MuiLink,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';

interface Props {
  open: boolean;
  specId: string;
  implementationSummary: string;
  codePrUrl?: string;
  onApprove: () => void;
  onReject: (feedback: string) => void;
  loading: boolean;
}

export default function CodeApprovalDialog({
  open,
  specId,
  implementationSummary,
  codePrUrl,
  onApprove,
  onReject,
  loading,
}: Props) {
  const [feedback, setFeedback] = useState('');

  if (!open) return null;

  return (
    <Box sx={{ mt: 3 }}>
      <Typography variant="h6" gutterBottom>
        Review Generated Code: {specId}
      </Typography>

      {codePrUrl && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Pull request ready:{' '}
          <MuiLink href={codePrUrl} target="_blank" rel="noopener noreferrer">
            {codePrUrl}
          </MuiLink>
        </Alert>
      )}

      {implementationSummary && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Implementation Summary
          </Typography>
          <Box component="pre" sx={{ whiteSpace: 'pre-wrap', m: 0, fontSize: '0.9rem' }}>
            {implementationSummary}
          </Box>
        </Box>
      )}

      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <Button
          variant="contained"
          color="success"
          startIcon={<CheckIcon />}
          onClick={onApprove}
          disabled={loading}
          size="large"
        >
          Approve Code
        </Button>
        <Button
          variant="outlined"
          color="error"
          startIcon={<CloseIcon />}
          onClick={() => onReject(feedback.trim() || 'Please revise the code.')}
          disabled={loading}
          size="large"
        >
          Reject with Feedback
        </Button>
      </Stack>

      <TextField
        fullWidth
        multiline
        rows={3}
        label="Rejection feedback"
        placeholder="Explain what needs to change..."
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        sx={{ mb: 1 }}
      />
    </Box>
  );
}
