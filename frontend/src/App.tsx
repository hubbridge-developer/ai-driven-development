import { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import {
  AppBar, Toolbar, Button, Box, CssBaseline, ThemeProvider, Stack,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ListIcon from '@mui/icons-material/List';
import LogoutIcon from '@mui/icons-material/Logout';
import WorkflowStartPage from './pages/WorkflowStartPage';
import WorkflowListPage from './pages/WorkflowListPage';
import WorkflowDetailPage from './pages/WorkflowDetailPage';
import LoginPage from './pages/LoginPage';
import BrandMark from './components/BrandMark';
import theme from './theme';
import { isAuthenticated, logout } from './auth';

function NavBar({ onLogout }: { onLogout: () => void }) {
  const location = useLocation();
  const navBtn = (active: boolean) => ({
    borderRadius: 2,
    px: 2,
    color: active ? 'primary.main' : 'text.secondary',
    bgcolor: active ? 'action.hover' : 'transparent',
    fontWeight: 600,
  });
  return (
    <AppBar position="sticky">
      <Toolbar sx={{ gap: 2 }}>
        <Box component={Link} to="/" sx={{ textDecoration: 'none' }}>
          <BrandMark />
        </Box>
        <Stack direction="row" spacing={1} sx={{ ml: 'auto' }}>
          <Button
            component={Link}
            to="/"
            startIcon={<AddIcon />}
            sx={navBtn(location.pathname === '/')}
          >
            New Task
          </Button>
          <Button
            component={Link}
            to="/workflows"
            startIcon={<ListIcon />}
            sx={navBtn(location.pathname.startsWith('/workflow'))}
          >
            Workflows
          </Button>
          <Button onClick={onLogout} startIcon={<LogoutIcon />} sx={navBtn(false)}>
            Sign out
          </Button>
        </Stack>
      </Toolbar>
    </AppBar>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(isAuthenticated());

  const handleLogout = () => {
    logout();
    setAuthed(false);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {!authed ? (
        <LoginPage onSuccess={() => setAuthed(true)} />
      ) : (
        <BrowserRouter>
          <NavBar onLogout={handleLogout} />
          <Box sx={{ pb: 6, minHeight: 'calc(100vh - 64px)' }}>
            <Routes>
              <Route path="/" element={<WorkflowStartPage />} />
              <Route path="/workflows" element={<WorkflowListPage />} />
              <Route path="/workflow/:workflowId" element={<WorkflowDetailPage />} />
            </Routes>
          </Box>
        </BrowserRouter>
      )}
    </ThemeProvider>
  );
}
