import { useState, useEffect, useCallback, useRef, type ReactNode, type SyntheticEvent } from 'react';
import { useParams } from 'react-router-dom';
import {
  Container, Typography, Grid, Paper, Box, Alert, CircularProgress, Chip, Button,
  Accordion, AccordionSummary, AccordionDetails,
} from '@mui/material';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import {
  getWorkflow,
  getWorkflowSpec,
  getWorkflowCode,
  approveWorkflow,
  rejectWorkflow,
  approveWorkflowCode,
  rejectWorkflowCode,
  cancelWorkflow,
} from '../api/client';
import { useWorkflowSocket } from '../hooks/useWorkflowSocket';
import PipelineStepper from '../components/PipelineStepper';
import SpecViewer from '../components/SpecViewer';
import ApprovalDialog from '../components/ApprovalDialog';
import CodeApprovalDialog from '../components/CodeApprovalDialog';
import ActivityLog from '../components/ActivityLog';
import type { LogEntry } from '../components/ActivityLog';
import LiveMetrics from '../components/LiveMetrics';
import type { Workflow, SpecDetail, CodeDetail } from '../types';

type SnapshotSpec = Partial<SpecDetail> & {
  generated_spec?: string;
  current_agent?: string;
};

interface PersistedLogEntry {
  agent: string;
  sub_step: string;
  detail: string;
  model: string;
  timestamp: string;
}

/** Collapsible section — click the header to expand/collapse its details. */
function Section({ title, badge, expanded, onChange, children }: {
  title: string;
  badge?: ReactNode;
  expanded: boolean;
  onChange: (e: SyntheticEvent, v: boolean) => void;
  children: ReactNode;
}) {
  return (
    <Accordion
      expanded={expanded}
      onChange={onChange}
      disableGutters
      sx={{
        mb: 2,
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        boxShadow: 'none',
        overflow: 'hidden',
        '&:before': { display: 'none' },
      }}
    >
      <AccordionSummary
        expandIcon={<ExpandMoreIcon />}
        sx={{
          bgcolor: 'action.hover',
          '& .MuiAccordionSummary-content': { alignItems: 'center', gap: 1, my: 1.25 },
        }}
      >
        <Typography variant="h6">{title}</Typography>
        {badge}
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 2 }}>{children}</AccordionDetails>
    </Accordion>
  );
}

export default function WorkflowDetailPage() {
  const { workflowId } = useParams<{ workflowId: string }>();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [spec, setSpec] = useState<SpecDetail | null>(null);
  const [code, setCode] = useState<CodeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeSubStep, setActiveSubStep] = useState<string>('');
  const [activeDetail, setActiveDetail] = useState<string>('');
  const [activityLog, setActivityLog] = useState<LogEntry[]>([]);
  const logIdRef = useRef(0);

  // Live metrics: <LiveMetrics> owns the 1s ticker so only the chips re-render
  // each second (the page — with its heavy spec/code panels — does not). The
  // current stage's in-progress LLM cost comes from WS so totals rise between
  // stage completions instead of jumping only at the end of each stage.
  const stageStartRef = useRef<number>(Date.now());
  const [liveStageCost, setLiveStageCost] = useState(0);

  // Which collapsible sections are open. The section needing attention
  // auto-expands (spec when awaiting spec approval, code when awaiting code).
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    activity: true, discovery: false, spec: true, code: false,
  });
  const toggleSection = (key: string) => (_e: SyntheticEvent, v: boolean) =>
    setOpenSections((prev) => ({ ...prev, [key]: v }));

  const wsMessages = useWorkflowSocket(workflowId);
  const processedCountRef = useRef(0);

  const initialLoadDone = useRef(false);

  const fetchData = useCallback(async () => {
    if (!workflowId) return;
    try {
      const wf = await getWorkflow(workflowId);
      setWorkflow(wf);

      // On first load, restore activity log from persisted state_snapshot
      if (!initialLoadDone.current) {
        initialLoadDone.current = true;
        const persistedLog = (wf.state_snapshot as Record<string, unknown>)?.activity_log as PersistedLogEntry[] | undefined;
        if (persistedLog && persistedLog.length > 0) {
          const restored: LogEntry[] = persistedLog.map((entry, idx) => ({
            id: idx + 1,
            agent: entry.agent,
            subStep: entry.sub_step,
            detail: entry.detail || '',
            model: entry.model || '',
            timestamp: new Date(entry.timestamp),
          }));
          logIdRef.current = restored.length;
          setActivityLog(restored);

          // Restore active sub-step from the last log entry
          const lastEntry = persistedLog[persistedLog.length - 1];
          if (lastEntry) {
            setActiveSubStep(lastEntry.sub_step);
            setActiveDetail(lastEntry.detail || '');
          }
        }
      }

      // Fetch spec if we're past the generator stage
      const specStages = ['spec_validator', 'spec_approval_gate', 'spec_publisher',
        'namespace_resolver', 'code_developer', 'code_publisher', 'code_approval_gate', 'code_review_handoff'];
      if (specStages.includes(wf.current_agent)
          || wf.status === 'completed' || wf.status === 'waiting_approval'
          || wf.status === 'waiting_code_approval') {
        const s = await getWorkflowSpec(workflowId);
        setSpec(s);
      }
      // Fetch code if we're in code stages or waiting for/after code approval
      if (
        ['namespace_resolver', 'code_developer', 'code_publisher', 'code_approval_gate', 'code_review_handoff'].includes(wf.current_agent)
        || wf.status === 'waiting_code_approval'
        || wf.status === 'completed'
      ) {
        const c = await getWorkflowCode(workflowId);
        setCode(c);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load workflow');
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  // Initial fetch
  useEffect(() => { fetchData(); }, [fetchData]);

  // Reset per-stage live counters whenever the active stage changes.
  useEffect(() => {
    stageStartRef.current = Date.now();
    setLiveStageCost(0);
  }, [workflow?.current_agent]);

  // Auto-open the section that currently needs attention.
  useEffect(() => {
    const st = workflow?.status;
    if (!st) return;
    setOpenSections((prev) => ({
      ...prev,
      spec: st === 'waiting_approval' ? true : prev.spec,
      code: st === 'waiting_code_approval' ? true : prev.code,
      activity: st === 'running' ? true : prev.activity,
    }));
  }, [workflow?.status]);

  // Handle WebSocket messages: process ALL new messages in the queue (no drops)
  useEffect(() => {
    if (wsMessages.length <= processedCountRef.current) return;

    const newMessages = wsMessages.slice(processedCountRef.current);
    processedCountRef.current = wsMessages.length;

    const newLogEntries: LogEntry[] = [];
    let latestSubStep = '';
    let latestDetail = '';
    let latestAgent = '';
    let latestStageCost: number | null = null;
    let needsFetch = false;

    for (const msg of newMessages) {
      if (msg.sub_step) {
        latestSubStep = msg.sub_step;
      }
      latestDetail = msg.detail || '';
      if (msg.current_agent) {
        latestAgent = msg.current_agent;
      }
      if (typeof msg.stage_cost_usd === 'number') {
        latestStageCost = msg.stage_cost_usd;
      }

      // Accumulate activity log entries
      if (msg.sub_step && msg.current_agent) {
        logIdRef.current += 1;
        newLogEntries.push({
          id: logIdRef.current,
          agent: msg.current_agent,
          subStep: msg.sub_step,
          detail: msg.detail || '',
          model: msg.model || '',
          timestamp: new Date(),
        });
      }

      // Check for major status changes
      if (msg.status && msg.status !== 'running') {
        needsFetch = true;
      }
    }

    // Batch-update state once for all new messages
    if (latestSubStep) setActiveSubStep(latestSubStep);
    if (latestDetail !== undefined) setActiveDetail(latestDetail);
    if (latestAgent) {
      setWorkflow((prev) => prev ? { ...prev, current_agent: latestAgent } : prev);
    }
    if (newLogEntries.length > 0) {
      setActivityLog((prev) => [...prev, ...newLogEntries]);
    }
    if (latestStageCost !== null) {
      setLiveStageCost(latestStageCost);
    }
    if (needsFetch) {
      fetchData();
    }
  }, [wsMessages.length]);

  // Fetch spec/code data when agent transitions to a stage that has new data
  // Only fetch when not already running a live WS session (avoid layout shifts)
  const prevAgentRef = useRef(workflow?.current_agent);
  useEffect(() => {
    if (!workflow) return;
    const prev = prevAgentRef.current;
    prevAgentRef.current = workflow.current_agent;
    // Skip if agent didn't actually change
    if (prev === workflow.current_agent) return;
    // Only fetch when transitioning INTO a stage that produces spec/code data
    const specDataStages = ['spec_validator', 'spec_approval_gate', 'spec_publisher'];
    const codeDataStages = ['namespace_resolver', 'code_developer', 'code_publisher', 'code_approval_gate', 'code_review_handoff'];
    if (specDataStages.includes(workflow.current_agent) && !spec) {
      getWorkflowSpec(workflowId!).then(setSpec).catch(() => {});
    }
    if (codeDataStages.includes(workflow.current_agent) && !code) {
      getWorkflowCode(workflowId!).then(setCode).catch(() => {});
    }
  }, [workflow?.current_agent]);

  // Lightweight fallback poll: refresh only the workflow status/metrics — NOT
  // the heavy spec/code sections (those load on stage transitions). Skip the
  // state update entirely when nothing changed, so the page doesn't re-render /
  // "flash" on every tick.
  const refreshStatus = useCallback(async () => {
    if (!workflowId) return;
    try {
      const wf = await getWorkflow(workflowId);
      setWorkflow((prev) =>
        prev && JSON.stringify(prev) === JSON.stringify(wf) ? prev : wf);
    } catch { /* ignore transient poll errors */ }
  }, [workflowId]);

  useEffect(() => {
    if (!workflow || workflow.status === 'completed' || workflow.status === 'error' || workflow.status === 'cancelled') return;
    const interval = setInterval(refreshStatus, 4000);
    return () => clearInterval(interval);
  }, [workflow?.status, refreshStatus]);

  const handleApprove = async () => {
    if (!workflowId) return;
    setActionLoading(true);
    try {
      await approveWorkflow(workflowId);
      await fetchData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (feedback: string) => {
    if (!workflowId) return;
    setActionLoading(true);
    try {
      await rejectWorkflow(workflowId, feedback);
      await fetchData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!workflowId) return;
    setActionLoading(true);
    try {
      await cancelWorkflow(workflowId);
      await fetchData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleApproveCode = async () => {
    if (!workflowId) return;
    setActionLoading(true);
    try {
      await approveWorkflowCode(workflowId);
      await fetchData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRejectCode = async (feedback: string) => {
    if (!workflowId) return;
    setActionLoading(true);
    try {
      await rejectWorkflowCode(workflowId, feedback);
      await fetchData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4, textAlign: 'center' }}>
        <CircularProgress />
      </Container>
    );
  }

  if (!workflow) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">Workflow not found</Alert>
      </Container>
    );
  }

  const snapshot = (workflow.state_snapshot || {}) as SnapshotSpec;
  const specData: SnapshotSpec = {
    ...snapshot,
    ...(spec || {}),
  };
  const hasDiscoveryData = Boolean(
    specData.request_classification
    || specData.identified_namespaces?.length
    || specData.related_specs?.length,
  );
  const hasGeneratedSpec = Boolean(specData.generated_spec);
  const hasCodeData = Boolean(code?.generated_files?.length || code?.implementation_summary || code?.code_pr_url);

  const showActivityLog = activityLog.length > 0 || workflow.status === 'running';

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <Typography variant="h4" fontWeight={700}>Workflow</Typography>
        <Chip
          label={workflow.status.replace('_', ' ')}
          color={
            workflow.status === 'completed' ? 'success'
            : workflow.status === 'waiting_approval' ? 'warning'
            : workflow.status === 'waiting_code_approval' ? 'warning'
            : workflow.status === 'cancelled' ? 'default'
            : workflow.status === 'error' ? 'error'
            : 'primary'
          }
        />
        {(() => {
          const tu = (workflow.token_usage || {}) as Record<string, number>;
          return (
            <LiveMetrics
              status={workflow.status}
              committedDur={tu.total_duration_sec || 0}
              committedCost={tu.total_cost_usd || 0}
              stageStartMs={stageStartRef.current}
              liveStageCost={liveStageCost}
            />
          );
        })()}
      </Box>

      <Paper sx={{ p: 2, mb: 3 }} variant="outlined">
        <Typography variant="subtitle2" color="text.secondary">Workflow Id</Typography>
        <Typography variant="body2" fontFamily="monospace" sx={{ mb: 1.5 }}>
          {workflow.workflow_id}
        </Typography>
        <Typography variant="subtitle2" color="text.secondary">User Request</Typography>
        <Typography variant="body1">{workflow.user_request}</Typography>
      </Paper>

      <Grid container spacing={3}>
        {/* Left: Pipeline Stepper */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>Pipeline</Typography>
            <PipelineStepper
              currentAgent={workflow.current_agent}
              status={workflow.status}
              activeSubStep={activeSubStep}
              activeDetail={activeDetail}
              validationResults={spec?.validation_results}
            />
          </Paper>

          {workflow.status === 'running' && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Pipeline is running... Current stage: <strong>{workflow.current_agent}</strong>
            </Alert>
          )}
          {workflow.status === 'waiting_code_approval' && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              Waiting for code approval. Current stage: <strong>{workflow.current_agent}</strong>
            </Alert>
          )}

          {workflow.error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {workflow.error}
            </Alert>
          )}

          {/* Discovery Results */}
          {hasDiscoveryData && (
            <Box sx={{ mt: 2 }}>
              <Section title="Discovery Results" expanded={openSections.discovery} onChange={toggleSection('discovery')}>

              {specData.request_classification && (
                <Box mb={1}>
                  <Typography variant="subtitle2" color="text.secondary">Classification</Typography>
                  <Chip
                    label={specData.request_classification}
                    color={specData.request_classification === 'new' ? 'info' : specData.request_classification === 'update' ? 'warning' : 'error'}
                    size="small"
                  />
                  {specData.extends_spec && (
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                      Extends: <strong>{specData.extends_spec}</strong>
                    </Typography>
                  )}
                </Box>
              )}

              {specData.identified_namespaces?.length ? (
                <Box mb={1}>
                  <Typography variant="subtitle2" color="text.secondary">Found Namespaces</Typography>
                  {specData.identified_namespaces.map((ns) => (
                    <Chip key={ns} label={ns} size="small" sx={{ mr: 0.5 }} variant="outlined" />
                  ))}
                </Box>
              ) : workflow.current_agent !== 'spec_discovery' ? (
                <Box mb={1}>
                  <Typography variant="subtitle2" color="text.secondary">Found Namespaces</Typography>
                  <Typography variant="body2" color="text.secondary">No namespace match found.</Typography>
                </Box>
              ) : null}

              {specData.related_specs?.length ? (
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">Related Specs (from Qdrant)</Typography>
                  {specData.related_specs.map((rs) => (
                    <Box key={rs.spec_id} display="flex" alignItems="center" gap={1} py={0.5}>
                      <Chip label={rs.spec_id} size="small" />
                      <Typography variant="body2">
                        score: <strong>{rs.score.toFixed(3)}</strong>
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        ({rs.match_type})
                      </Typography>
                    </Box>
                  ))}
                </Box>
              ) : workflow.current_agent !== 'spec_discovery' ? (
                <Box>
                  <Typography variant="subtitle2" color="text.secondary">Related Specs (from Qdrant)</Typography>
                  <Typography variant="body2" color="text.secondary">No related specs found.</Typography>
                </Box>
              ) : null}
              </Section>
            </Box>
          )}
        </Grid>

        {/* Right: Spec Viewer + Approval */}
        <Grid item xs={12} md={8}>
          {/* Live activity log — all agent output */}
          {showActivityLog && (
            <Box sx={{ mb: 3 }}>
              <ActivityLog
                entries={activityLog}
                running={workflow.status === 'running'}
              />
            </Box>
          )}

          {hasGeneratedSpec ? (
            <Section
              title="Generated Specification"
              badge={specData.spec_id ? <Chip label={specData.spec_id} size="small" color="primary" /> : undefined}
              expanded={openSections.spec}
              onChange={toggleSection('spec')}
            >
              <SpecViewer
                specContent={specData.generated_spec || ''}
                specId={specData.spec_id || ''}
                lowConfidenceSections={specData.low_confidence_sections}
                duplicateWarning={specData.duplicate_warning}
                consistencyWarnings={specData.consistency_warnings}
              />

              {workflow.status === 'waiting_approval' && (
                <ApprovalDialog
                  open={true}
                  specId={specData.spec_id || ''}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  onCancel={handleCancel}
                  loading={actionLoading}
                />
              )}

              {workflow.status === 'completed' && specData.spec_pr_url && (
                <Alert
                  severity="success"
                  sx={{ mt: 2 }}
                  action={
                    <Button
                      color="inherit"
                      size="small"
                      href={specData.spec_pr_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      endIcon={<OpenInNewIcon />}
                    >
                      View PR #{specData.spec_pr_number}
                    </Button>
                  }
                >
                  Specification published to GitHub and indexed into Qdrant.
                </Alert>
              )}

              {workflow.status === 'completed' && !specData.spec_pr_url && (
                <Alert severity="success" sx={{ mt: 2 }}>
                  Specification saved and indexed into Qdrant. (GitHub publishing not configured)
                </Alert>
              )}

              {workflow.status === 'cancelled' && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  Workflow cancelled. The specification was not published.
                </Alert>
              )}
            </Section>
          ) : (
            !showActivityLog && (
              <Paper sx={{ p: 4 }}>
                <Typography color="text.secondary">
                  No specification available yet.
                </Typography>
              </Paper>
            )
          )}

          {/* Code section */}
          {hasCodeData && (
            <Section title="Generated Code" expanded={openSections.code} onChange={toggleSection('code')}>
              {code?.implementation_summary && (
                <Paper sx={{ p: 2, mb: 2 }} variant="outlined">
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Implementation Summary
                  </Typography>
                  <Box component="pre" sx={{ whiteSpace: 'pre-wrap', m: 0, fontSize: '0.9rem' }}>
                    {code.implementation_summary}
                  </Box>
                </Paper>
              )}

              {code?.generated_files?.length ? (
                <Paper sx={{ p: 2, mb: 2 }} variant="outlined">
                  <Typography variant="subtitle2" gutterBottom>Files</Typography>
                  {code.generated_files.map((f) => (
                    <Box key={f.path} display="flex" justifyContent="space-between" alignItems="center" py={0.5}>
                      <Typography variant="body2" fontFamily="monospace">{f.path}</Typography>
                      <Chip label={f.action || 'modify'} size="small" />
                    </Box>
                  ))}
                </Paper>
              ) : null}

              {code?.generated_tests?.length ? (
                <Paper sx={{ p: 2, mb: 2 }} variant="outlined">
                  <Typography variant="subtitle2" gutterBottom>Tests</Typography>
                  {code.generated_tests.map((t) => (
                    <Box key={t.path} display="flex" justifyContent="space-between" alignItems="center" py={0.5}>
                      <Typography variant="body2" fontFamily="monospace">{t.path}</Typography>
                      <Chip label={t.test_type || 'test'} size="small" color="info" />
                    </Box>
                  ))}
                </Paper>
              ) : null}

              {code?.code_pr_url && (
                <Alert
                  severity="info"
                  sx={{ mb: 2 }}
                  action={(
                    <Button
                      color="inherit"
                      size="small"
                      href={code.code_pr_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      endIcon={<OpenInNewIcon />}
                    >
                      View Code PR
                    </Button>
                  )}
                >
                  Code published to GitHub.
                </Alert>
              )}

              {workflow.status === 'waiting_code_approval' && (
                <CodeApprovalDialog
                  open
                  specId={code?.spec_id || specData.spec_id || ''}
                  implementationSummary={code?.implementation_summary || ''}
                  codePrUrl={code?.code_pr_url || ''}
                  onApprove={handleApproveCode}
                  onReject={handleRejectCode}
                  loading={actionLoading}
                />
              )}
            </Section>
          )}
        </Grid>
      </Grid>
    </Container>
  );
}
