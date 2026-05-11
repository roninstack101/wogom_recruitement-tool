import { Navigate } from 'react-router-dom';
import { getUser } from '../services/api';

/**
 * Wraps a page component and redirects to /login if not authenticated.
 * If `allowedRoles` is provided, also checks the user's role.
 */
export default function ProtectedRoute({ children, allowedRoles }) {
    const user = getUser();

    if (!user) {
        return <Navigate to="/login" replace />;
    }

    if (allowedRoles && !allowedRoles.includes(user.role)) {
        // Redirect to their correct dashboard
        const dest = user.role === 'hr' ? '/hr' : '/team-lead';
        return <Navigate to={dest} replace />;
    }

    return children;
}
