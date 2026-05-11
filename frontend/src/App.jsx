import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import RecruiterPage from './pages/RecruiterPage';
import CandidatePage from './pages/CandidatePage';
import TeamLeadPage from './pages/TeamLeadPage';
import HRDashboardPage from './pages/HRDashboardPage';
import CandidateTrackingPage from './pages/CandidateTrackingPage';
import { getUser } from './services/api';

function AppShell({ children }) {
    return (
        <div className="app-shell">
            <Sidebar />
            <div className="app-main">
                <TopBar />
                <main className="app-content">{children}</main>
            </div>
        </div>
    );
}

export default function App() {
    const location = useLocation();
    const isLoginPage = location.pathname === '/login';

    if (isLoginPage) {
        return <LoginPage />;
    }

    return (
        <AppShell>
            <Routes>
                {/* Team Lead routes */}
                <Route
                    path="/team-lead"
                    element={
                        <ProtectedRoute allowedRoles={['team_lead']}>
                            <TeamLeadPage />
                        </ProtectedRoute>
                    }
                />

                {/* HR Dashboard */}
                <Route
                    path="/hr"
                    element={
                        <ProtectedRoute allowedRoles={['hr']}>
                            <HRDashboardPage />
                        </ProtectedRoute>
                    }
                />

                {/* Candidate Tracking */}
                <Route
                    path="/tracking"
                    element={
                        <ProtectedRoute allowedRoles={['hr']}>
                            <CandidateTrackingPage />
                        </ProtectedRoute>
                    }
                />

                {/* Shared tool pages (both roles can use them) */}
                <Route
                    path="/recruiter"
                    element={
                        <ProtectedRoute>
                            <RecruiterPage />
                        </ProtectedRoute>
                    }
                />
                <Route
                    path="/candidate"
                    element={
                        <ProtectedRoute allowedRoles={['hr']}>
                            <CandidatePage />
                        </ProtectedRoute>
                    }
                />

                {/* Root: redirect to role-specific dashboard */}
                <Route
                    path="/"
                    element={<RootRedirect />}
                />

                {/* Catch-all */}
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </AppShell>
    );
}

function RootRedirect() {
    const user = getUser();
    if (!user) return <Navigate to="/login" replace />;
    if (user.role === 'hr') return <Navigate to="/hr" replace />;
    return <Navigate to="/team-lead" replace />;
}
