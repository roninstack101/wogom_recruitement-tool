import { Link, useLocation } from 'react-router-dom';
import {
    LayoutDashboard,
    FileText,
    Users,
    ChevronLeft,
    ChevronRight,
    BriefcaseBusiness,
    ClipboardList,
    Inbox,
    UserCheck,
} from 'lucide-react';
import { useState, useEffect } from 'react';
import { getUser } from '../services/api';
import './Sidebar.css';

export default function Sidebar() {
    const location = useLocation();
    const [collapsed, setCollapsed] = useState(false);
    const user = getUser();
    const role = user?.role;

    // Auto-collapse on small screens
    useEffect(() => {
        const handleResize = () => {
            if (window.innerWidth < 1024) {
                setCollapsed(true);
            } else {
                setCollapsed(false);
            }
        };

        // Initial check
        handleResize();

        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const NAV_ITEMS = role === 'hr'
        ? [
            { to: '/hr', label: 'HR Dashboard', icon: LayoutDashboard },
            { to: '/tracking', label: 'Candidate Tracking', icon: UserCheck },
            { to: '/recruiter', label: 'JD Generator', icon: FileText },
            { to: '/candidate', label: 'Candidates', icon: Users },
        ]
        : [
            { to: '/team-lead', label: 'My Requests', icon: ClipboardList },
            { to: '/recruiter', label: 'JD Generator', icon: FileText },
        ];

    return (
        <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
            {/* Logo */}
            <div className="sidebar-logo">
                <BriefcaseBusiness size={28} className="sidebar-logo-icon" />
                {!collapsed && <span className="sidebar-logo-text">WOGOM</span>}
            </div>

            {/* Role badge */}
            {!collapsed && (
                <div className="sidebar-role-badge">
                    {role === 'hr' ? 'HR' : 'Team Lead'}
                </div>
            )}

            {/* Main Nav */}
            <nav className="sidebar-nav">
                <div className="sidebar-section-label">{!collapsed && 'MAIN MENU'}</div>
                {NAV_ITEMS.map((item) => {
                    const Icon = item.icon;
                    const isActive = location.pathname === item.to;
                    return (
                        <Link
                            key={item.to}
                            to={item.to}
                            className={`sidebar-link ${isActive ? 'active' : ''}`}
                            title={collapsed ? item.label : undefined}
                        >
                            <Icon size={20} />
                            {!collapsed && <span>{item.label}</span>}
                        </Link>
                    );
                })}
            </nav>

            {/* Bottom items */}
            <div className="sidebar-bottom">
                {/* Collapse toggle */}
                <button
                    className="sidebar-toggle"
                    onClick={() => setCollapsed(!collapsed)}
                    aria-label="Toggle sidebar"
                >
                    {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
                    {!collapsed && <span>Collapse</span>}
                </button>
            </div>
        </aside>
    );
}
