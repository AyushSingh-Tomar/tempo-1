import { createBrowserRouter } from 'react-router-dom';
import { ProjectListPage } from '../pages/ProjectListPage';
import { ProjectDetailPage } from '../pages/ProjectDetailPage';
import { NewRunPage } from '../pages/NewRunPage';
import { RunWizardPage } from '../pages/RunWizardPage';
import { ReconciliationPage } from '../pages/ReconciliationPage';
import { ReconRunPage } from '../pages/ReconRunPage';

export const router = createBrowserRouter([
  { path: '/', element: <ProjectListPage /> },
  { path: '/projects/:projectId', element: <ProjectDetailPage /> },
  { path: '/projects/:projectId/new-run', element: <NewRunPage /> },
  { path: '/projects/:projectId/reconciliation', element: <ReconciliationPage /> },
  { path: '/projects/:projectId/reconciliation/runs/:runId', element: <ReconRunPage /> },
  { path: '/runs/:runId', element: <RunWizardPage /> },
]);
