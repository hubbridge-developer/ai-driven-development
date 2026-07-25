import { useState } from 'react';
import {
  Box, Button, TextField, Typography, Stack,
} from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import BlockIcon from '@mui/icons-material/Block';

interface Props {
  open: boolean;
  specId: string;
  onApprove: () => void;
  onReject: (feedback: string) => void;
  onCancel: () => void;
  loading: boolean;
}

export default function ApprovalDialog({ open, specId, onApprove, onReject, onCancel, loading }: Props) {
  const [showReject, setShowReject] = useState(false);
  const [showCancel, setShowCancel] = useState(false);
  const [feedback, setFeedback] = useState('');

  const handleReject = () => {
    if (feedback.trim()) {
      onReject(feedback.trim());
      setFeedback('');
      setShowReject(false);
    }
  };

  return (
    <Box sx={{ mt: 3 }}>
      <Typography variant="h6" gutterBottom>
        Review Specification: {specId}
      </Typography>

      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <Button
          variant="contained"
          color="success"
          startIcon={<CheckIcon />}
          onClick={onApprove}
          disabled={loading}
          size="large"
        >
          Approve
        </Button>
        <Button
          variant="outlined"
          color="error"
          startIcon={<CloseIcon />}
          onClick={() => { setShowReject(true); setShowCancel(false); }}
          disabled={loading}
          size="large"
        >
          Reject
        </Button>
        <Button
          variant="outlined"
          color="warning"
          startIcon={<BlockIcon />}
          onClick={() => { setShowCancel(true); setShowReject(false); }}
          disabled={loading}
          size="large"
        >
          Cancel Spec
        </Button>
      </Stack>

      {showReject && (
        <Box sx={{ mt: 2 }}>
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
          <Stack direction="row" spacing={1}>
            <Button
              variant="contained"
              color="error"
              onClick={handleReject}
              disabled={!feedback.trim() || loading}
            >
              Submit Rejection
            </Button>
            <Button onClick={() => { setShowReject(false); setFeedback(''); }}>
              Back
            </Button>
          </Stack>
        </Box>
      )}

      {showCancel && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            This will permanently cancel the workflow. The spec will not be published or regenerated.
          </Typography>
          <Stack direction="row" spacing={1}>
            <Button
              variant="contained"
              color="warning"
              onClick={() => { onCancel(); setShowCancel(false); }}
              disabled={loading}
            >
              Confirm Cancel
            </Button>
            <Button onClick={() => setShowCancel(false)}>
              Back
            </Button>
          </Stack>
        </Box>
      )}
    </Box>
  );
}
