import { useLocation, useNavigate } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';
import { Bell, ChevronRight, LogOut } from 'lucide-react';
import { getUser, clearToken, fetchUnreadCount, fetchNotifications, markAllRead } from '../services/api';
import './TopBar.css';

const ROUTE_LABELS = {
    '/': 'Dashboard',
    '/team-lead': 'Team Lead Dashboard',
    '/hr': 'HR Dashboard',
    '/recruiter': 'JD Generator',
    '/candidate': 'Candidates',
};

export default function TopBar() {
    const location = useLocation();
    const navigate = useNavigate();
    const user = getUser();
    const pageLabel = ROUTE_LABELS[location.pathname] || 'Page';

    const [unread, setUnread] = useState(0);
    const [showNotifs, setShowNotifs] = useState(false);
    const [notifs, setNotifs] = useState([]);
    const notifRef = useRef(null);

    useEffect(() => {
        loadUnread();
        const interval = setInterval(loadUnread, 30000);
        return () => clearInterval(interval);
    }, []);

    // Close notifications when clicking outside
    useEffect(() => {
        function handleClickOutside(event) {
            if (notifRef.current && !notifRef.current.contains(event.target)) {
                setShowNotifs(false);
            }
        }

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, []);

    async function loadUnread() {
        try {
            const data = await fetchUnreadCount();
            setUnread(data.count);
        } catch { /* silently ignore */ }
    }

    async function toggleNotifs() {
        if (!showNotifs) {
            try {
                const data = await fetchNotifications();
                setNotifs(data);
            } catch { /* ignore */ }
        }
        setShowNotifs(!showNotifs);
    }

    async function handleMarkAllRead() {
        try {
            await markAllRead();
            setUnread(0);
            setNotifs(prev => prev.map(n => ({ ...n, is_read: true })));
        } catch { /* ignore */ }
    }

    function handleLogout() {
        clearToken();
        navigate('/login');
    }

    const initials = user
        ? user.name.split(' ').map(w => w[0]).join('').toUpperCase().substring(0, 2)
        : '??';

    return (
        <header className="topbar">
            <div className="topbar-left">
                <div className="topbar-breadcrumb">
                    <span className="breadcrumb-root">WOGOM</span>
                    <ChevronRight size={14} className="breadcrumb-sep" />
                    <span className="breadcrumb-current">{pageLabel}</span>
                </div>
            </div>

            <div className="topbar-right">
                {/* Notifications */}
                <div className="topbar-notif-wrapper" ref={notifRef}>
                    <button className="topbar-icon-btn" aria-label="Notifications" onClick={toggleNotifs}>
                        <Bell size={18} />
                        {unread > 0 && <span className="topbar-notif-dot">{unread}</span>}
                    </button>

                    {showNotifs && (
                        <div className="topbar-notif-dropdown">
                            <div className="notif-dropdown-header">
                                <span>Notifications</span>
                                {unread > 0 && (
                                    <button className="notif-mark-all" onClick={handleMarkAllRead}>
                                        Mark all read
                                    </button>
                                )}
                            </div>
                            <div className="notif-list">
                                {notifs.length === 0 ? (
                                    <div className="notif-empty">No notifications</div>
                                ) : (
                                    notifs.slice(0, 10).map(n => (
                                        <div key={n.id} className={`notif-item ${!n.is_read ? 'unread' : ''}`}>
                                            <p>{n.message}</p>
                                            <span className="notif-time">
                                                {new Date(n.created_at).toLocaleString()}
                                            </span>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {/* User */}
                <div className="topbar-user">
                    <div className="topbar-avatar">
                        <span className="avatar-initials">{initials}</span>
                    </div>
                    {user && <span className="topbar-username">{user.name}</span>}
                </div>

                <button className="topbar-icon-btn logout-btn" aria-label="Logout" onClick={handleLogout}>
                    <LogOut size={18} />
                </button>
            </div>
        </header>
    );
}
