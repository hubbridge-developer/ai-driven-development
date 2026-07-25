import axios from 'axios';
import type { Workflow, SpecDetail, CodeDetail, Namespace } from '../types';

const API_BASE = '/api/v1';

const api = axios.create({ baseURL: API_BASE });

export async function startWorkflow(userRequest: string): Promise<{ workflow_id: string }> {
  const { data } = await api.post('/workflow/start', { user_request: userRequest });
  return data;
}

export async function getWorkflow(workflowId: string): Promise<Workflow> {
  const { data } = await api.get(`/workflow/${workflowId}`);
  return data;
}

export async function getWorkflowSpec(workflowId: string): Promise<SpecDetail> {
  const { data } = await api.get(`/workflow/${workflowId}/spec`);
  return data;
}

export async function getWorkflowCode(workflowId: string): Promise<CodeDetail> {
  const { data } = await api.get(`/workflow/${workflowId}/code`);
  return data;
}

export async function approveWorkflow(workflowId: string): Promise<void> {
  await api.post(`/workflow/${workflowId}/approve`);
}

export async function rejectWorkflow(workflowId: string, feedback: string): Promise<void> {
  await api.post(`/workflow/${workflowId}/reject`, { feedback });
}

export async function approveWorkflowCode(workflowId: string): Promise<void> {
  await api.post(`/workflow/${workflowId}/approve-code`);
}

export async function rejectWorkflowCode(workflowId: string, feedback: string): Promise<void> {
  await api.post(`/workflow/${workflowId}/reject-code`, { feedback });
}

export async function cancelWorkflow(workflowId: string): Promise<void> {
  await api.post(`/workflow/${workflowId}/cancel`);
}

export async function listWorkflows(status?: string): Promise<Workflow[]> {
  const params = status ? { status } : {};
  const { data } = await api.get('/workflows', { params });
  return data;
}

export async function listNamespaces(): Promise<Namespace[]> {
  const { data } = await api.get('/namespaces/');
  return data;
}

export async function searchSpecs(query: string): Promise<{ results: unknown[] }> {
  const { data } = await api.post('/specs/search', { query });
  return data;
}
