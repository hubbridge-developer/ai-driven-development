import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container, Typography, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Paper, Chip, IconButton, Box, ToggleButtonGroup,
  ToggleButton,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { listWorkflows } from '../api/client';
import type { Workflow } from '../types';

const STATUS_COLORS: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'error'> = {
  running: 'primary',
  waiting_approval: 'warning',
  waiting_code_approval: 'warning',
  completed: 'success',
  failed: 'error',
  error: 'error',
};

export default function WorkflowListPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [filter, setFilter] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const fetchWorkflows = async () => {
    setLoading(true);
    try {
      const data = await listWorkflows(filter || undefined);
      setWorkflows(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
    const interval = setInterval(fetchWorkflows, 5000);
    return () => clearInterval(interval);
  }, [filter]);

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h4" fontWeight={700}>Workflows</Typography>
        <IconButton onClick={fetchWorkflows} disabled={loading}>
          <RefreshIcon />
        </IconButton>
      </Box>

      <ToggleButtonGroup
        value={filter}
        exclusive
        onChange={(_, val) => setFilter(val || '')}
        size="small"
        sx={{ mb: 2 }}
      >
        <ToggleButton value="">All</ToggleButton>
        <ToggleButton value="running">Running</ToggleButton>
        <ToggleButton value="waiting_approval">Waiting</ToggleButton>
        <ToggleButton value="waiting_code_approval">Code Review</ToggleButton>
        <ToggleButton value="completed">Completed</ToggleButton>
        <ToggleButton value="error">Error</ToggleButton>
      </ToggleButtonGroup>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Workflow ID</TableCell>
              <TableCell>Request</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Current Agent</TableCell>
              <TableCell>Created</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {workflows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  <Typography color="text.secondary" py={3}>
                    No workflows yet. Start one from the New Task page.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              workflows.map((wf) => (
                <TableRow
                  key={wf.workflow_id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/workflow/${wf.workflow_id}`)}
                >
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace">
                      {wf.workflow_id}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" noWrap sx={{ maxWidth: 300 }}>
                      {wf.user_request}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={wf.status.replace('_', ' ')}
                      color={STATUS_COLORS[wf.status] || 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>{wf.current_agent || '—'}</TableCell>
                  <TableCell>
                    {new Date(wf.created_at).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Container>
  );
}
