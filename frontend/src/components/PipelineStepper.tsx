import { useEffect, useRef, useState } from 'react';
import {
  Stepper, Step, StepLabel, StepContent, Typography, Chip, Box,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import RadioButtonCheckedIcon from '@mui/icons-material/RadioButtonChecked';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import ArrowRightIcon from '@mui/icons-material/ArrowRight';
import { PIPELINE_STAGES } from '../types';

interface Props {
  currentAgent: string;
  status: string;
  activeSubStep?: string;
  activeDetail?: string;
  validationResults?: { check: string; is_valid: boolean; message: string }[];
}

const STEP_ANIMATION_DELAY = 800; // ms between each step transition

export default function PipelineStepper({ currentAgent, status, activeSubStep, activeDetail, validationResults }: Props) {
  const targetIndex = PIPELINE_STAGES.findIndex((s) => s.key === currentAgent);
  const isCompleted = status === 'completed';
  const isError = status === 'error' || status === 'failed';

  // Animated display index — walks up to targetIndex one step at a time
  const [displayIndex, setDisplayIndex] = useState(targetIndex >= 0 ? targetIndex : 0);
  const prevTargetRef = useRef(targetIndex);

  // Track completed sub-steps per stage: { "spec_discovery": ["LLM Request Parsing", ...] }
  // Initialize with all stages before the current one fully completed (for page reload)
  const [completedSubSteps, setCompletedSubSteps] = useState<Record<string, string[]>>(() => {
    const initial: Record<string, string[]> = {};
    if (targetIndex > 0) {
      for (let i = 0; i < targetIndex; i++) {
        initial[PIPELINE_STAGES[i].key] = [...PIPELINE_STAGES[i].subSteps];
      }
    }
    return initial;
  });
  const prevSubStepRef = useRef<string>('');

  useEffect(() => {
    if (targetIndex < 0) return;

    if (targetIndex > displayIndex) {
      const timer = setTimeout(() => {
        setDisplayIndex((prev) => prev + 1);
      }, STEP_ANIMATION_DELAY);
      return () => clearTimeout(timer);
    }

    if (targetIndex < displayIndex) {
      setDisplayIndex(targetIndex);
    }

    prevTargetRef.current = targetIndex;
  }, [targetIndex, displayIndex]);

  // When activeSubStep changes, mark the previous one as completed
  useEffect(() => {
    if (!activeSubStep || !currentAgent) return;

    // Mark all sub-steps BEFORE the current one as completed
    const stage = PIPELINE_STAGES.find((s) => s.key === currentAgent);
    if (stage) {
      const currentSubIdx = stage.subSteps.indexOf(activeSubStep);
      if (currentSubIdx > 0) {
        const stepsToComplete = stage.subSteps.slice(0, currentSubIdx);
        setCompletedSubSteps((prev) => {
          const agentSteps = prev[currentAgent] || [];
          const merged = [...new Set([...agentSteps, ...stepsToComplete])];
          if (merged.length !== agentSteps.length) {
            return { ...prev, [currentAgent]: merged };
          }
          return prev;
        });
      }
    }
    prevSubStepRef.current = activeSubStep;
  }, [activeSubStep, currentAgent]);

  // When agent changes, mark ALL sub-steps of the previous agent as completed
  const prevAgentRef = useRef(currentAgent);
  useEffect(() => {
    if (currentAgent !== prevAgentRef.current && prevAgentRef.current) {
      const prevAgent = prevAgentRef.current;
      const stage = PIPELINE_STAGES.find((s) => s.key === prevAgent);
      if (stage) {
        setCompletedSubSteps((prev) => ({
          ...prev,
          [prevAgent]: [...stage.subSteps],
        }));
      }
    }
    prevAgentRef.current = currentAgent;
  }, [currentAgent]);

  // When workflow completes, mark everything as done
  useEffect(() => {
    if (isCompleted) {
      const allDone: Record<string, string[]> = {};
      PIPELINE_STAGES.forEach((stage) => {
        allDone[stage.key] = [...stage.subSteps];
      });
      setCompletedSubSteps(allDone);
    }
  }, [isCompleted]);

  const activeIndex = isCompleted ? PIPELINE_STAGES.length : displayIndex;

  return (
    <Stepper
      activeStep={activeIndex}
      orientation="vertical"
      nonLinear
    >
      {PIPELINE_STAGES.map((stage, idx) => {
        const isCurrent = idx === activeIndex;
        const isPast = isCompleted || idx < activeIndex;
    const isWaiting = (
      (isCurrent && status === 'waiting_approval' && stage.key === 'spec_approval_gate')
      || (isCurrent && status === 'waiting_code_approval' && stage.key === 'code_approval_gate')
    );
        const isFuture = !isPast && !isCurrent;

        let icon;
        if (isCompleted || isPast) {
          icon = <CheckCircleIcon color="success" />;
        } else if (isError && isCurrent) {
          icon = <ErrorIcon color="error" />;
        } else if (isWaiting) {
          icon = <HourglassEmptyIcon color="warning" />;
        } else if (isCurrent) {
          icon = <RadioButtonCheckedIcon color="primary" />;
        } else if (isFuture) {
          icon = <RadioButtonUncheckedIcon color="disabled" />;
        }

        const showSubSteps = isCurrent || isPast;
        const doneSubSteps = completedSubSteps[stage.key] || [];

        return (
          <Step key={stage.key} completed={isPast} active={isCurrent}>
            <StepLabel
              StepIconComponent={() => icon || <RadioButtonUncheckedIcon color="disabled" />}
              error={isError && isCurrent}
            >
              <Typography
                fontWeight={isCurrent ? 700 : isPast ? 500 : 400}
                color={isCurrent ? 'primary' : isPast ? 'success.main' : 'text.secondary'}
                sx={{ transition: 'all 0.3s ease' }}
              >
                {stage.label}
              </Typography>
              {isWaiting && (
                <Chip label="Waiting for approval" color="warning" size="small" sx={{ ml: 1 }} />
              )}
            </StepLabel>
            {showSubSteps && stage.subSteps.length > 0 && (
              <StepContent>
                <Box sx={{ pl: 0.5, pt: 0.5 }}>
                  {stage.subSteps.map((sub) => {
                    const isSubDone = doneSubSteps.includes(sub) || isPast;
                    const isSubActive = isCurrent && activeSubStep === sub && !isSubDone;

                    return (
                      <Box
                        key={sub}
                        display="flex"
                        alignItems="center"
                        gap={0.5}
                        py={0.3}
                        sx={{ transition: 'all 0.3s ease' }}
                      >
                        {isSubActive ? (
                          <ArrowRightIcon
                            sx={{ fontSize: 16, color: 'primary.main' }}
                          />
                        ) : isSubDone ? (
                          <CheckCircleIcon
                            sx={{ fontSize: 14, ml: '1px', mr: '1px', color: 'success.main' }}
                          />
                        ) : (
                          <FiberManualRecordIcon
                            sx={{
                              fontSize: 7,
                              ml: '4.5px',
                              mr: '4.5px',
                              color: 'text.disabled',
                            }}
                          />
                        )}
                        <Box>
                          <Typography
                            variant="caption"
                            fontWeight={isSubActive ? 600 : isSubDone ? 500 : 400}
                            color={
                              isSubActive ? 'primary.main'
                              : isSubDone ? 'success.main'
                              : 'text.secondary'
                            }
                            sx={{ transition: 'all 0.3s ease' }}
                          >
                            {sub}
                          </Typography>
                          {isSubActive && activeDetail && (
                            <Typography
                              variant="caption"
                              display="block"
                              color="text.secondary"
                              sx={{ pl: 0.5, fontSize: '0.7rem', lineHeight: 1.3, mt: 0.2 }}
                            >
                              {activeDetail}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    );
                  })}
                </Box>
                {isCurrent && stage.key === 'spec_validator' && validationResults && (
                  <Box sx={{ pl: 0.5, pt: 1, borderTop: '1px solid', borderColor: 'divider', mt: 1 }}>
                    {validationResults.map((v) => (
                      <Typography key={v.check} variant="body2" color={v.is_valid ? 'success.main' : 'error.main'}>
                        {v.is_valid ? '✓' : '✗'} {v.check}: {v.message}
                      </Typography>
                    ))}
                  </Box>
                )}
              </StepContent>
            )}
          </Step>
        );
      })}
    </Stepper>
  );
}
