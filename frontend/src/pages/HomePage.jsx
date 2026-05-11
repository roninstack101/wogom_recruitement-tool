import { useNavigate } from 'react-router-dom';
import {
    FileText,
    Users,
    Briefcase,
    ArrowRight,
    TrendingUp,
    Clock,
    CheckCircle2,
    Plus,
    BarChart3,
} from 'lucide-react';
import { getUser } from '../services/api';
import './HomePage.css';

const STATS = [
    {
        label: 'Active Roles',
        value: '12',
        sub: '+3 this month',
        icon: <Briefcase size={20} />,
        color: '#4f46e5',
        bg: '#eef2ff',
    },
    {
        label: 'JDs Created',
        value: '34',
        sub: '+8 this week',
        icon: <FileText size={20} />,
        color: '#7c3aed',
        bg: '#f5f3ff',
    },
    {
        label: 'Candidates Processed',
        value: '156',
        sub: '+24 today',
        icon: <Users size={20} />,
        color: '#2563eb',
        bg: '#eff6ff',
    },
    {
        label: 'Avg. Match Score',
        value: '78%',
        sub: '↑ 5% from last month',
        icon: <TrendingUp size={20} />,
        color: '#16a34a',
        bg: '#f0fdf4',
    },
];

const QUICK_ACTIONS = [
    {
        title: 'Create New JD',
        desc: 'Start a 6-step AI-powered job description wizard',
        icon: <Plus size={20} />,
        color: '#4f46e5',
        bg: '#eef2ff',
        route: '/recruiter',
    },
    {
        title: 'Analyze Candidates',
        desc: 'Upload resumes and run AI matching pipeline',
        icon: <BarChart3 size={20} />,
        color: '#2563eb',
        bg: '#eff6ff',
        route: '/candidate',
    },
];

const RECENT_ACTIVITY = [
    { text: 'JD created for "AI Engineer" role', time: '2 hours ago', color: '#4f46e5' },
    { text: '8 candidates processed for "Sales Executive"', time: '5 hours ago', color: '#2563eb' },
    { text: 'JD refined for "HR Manager" role', time: 'Yesterday', color: '#7c3aed' },
    { text: '12 candidates ranked for "Product Manager"', time: '2 days ago', color: '#16a34a' },
    { text: 'New role "Data Analyst" added from form', time: '3 days ago', color: '#f59e0b' },
];

export default function HomePage() {
    const navigate = useNavigate();
    const user = getUser();
    const isHR = user?.role === 'hr';

    // Filter quick actions based on role
    const quickActions = QUICK_ACTIONS.filter(action => {
        // Hide Analyze Candidates for team leads
        if (action.route === '/candidate' && !isHR) return false;
        return true;
    });

    return (
        <div className="dashboard">
            {/* Page Header */}
            <div className="page-header animate-fade-in">
                <h1>Dashboard</h1>
                <p>Welcome back — here's an overview of your recruitment pipeline</p>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-4 animate-fade-in-up">
                {STATS.map((s, i) => (
                    <div key={i} className="stat-card">
                        <div
                            className="stat-card-icon"
                            style={{ background: s.bg, color: s.color }}
                        >
                            {s.icon}
                        </div>
                        <div className="stat-card-body">
                            <div className="stat-card-label">{s.label}</div>
                            <div className="stat-card-value">{s.value}</div>
                            <div className="stat-card-sub">{s.sub}</div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Quick Actions + Recent Activity */}
            <div className="grid grid-2 mt-xl animate-fade-in-up delay-1">
                {/* Quick Actions */}
                <div>
                    <h2 className="section-title">Quick Actions</h2>
                    <div className="flex flex-col gap-md mt-md">
                        {quickActions.map((action, i) => (
                            <div
                                key={i}
                                className="action-tile"
                                onClick={() => navigate(action.route)}
                            >
                                <div
                                    className="action-tile-icon"
                                    style={{ background: action.bg, color: action.color }}
                                >
                                    {action.icon}
                                </div>
                                <div className="action-tile-body">
                                    <h3>{action.title}</h3>
                                    <p>{action.desc}</p>
                                </div>
                                <ArrowRight size={16} className="action-tile-arrow" />
                            </div>
                        ))}
                    </div>
                </div>

                {/* Recent Activity */}
                <div>
                    <h2 className="section-title">Recent Activity</h2>
                    <div className="card mt-md">
                        {RECENT_ACTIVITY.map((item, i) => (
                            <div key={i} className="activity-item">
                                <div
                                    className="activity-dot"
                                    style={{ background: item.color }}
                                />
                                <span className="activity-text">{item.text}</span>
                                <span className="activity-time">
                                    <Clock size={12} style={{ marginRight: 4, verticalAlign: 'middle' }} />
                                    {item.time}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Pipeline Status */}
            <div className="mt-xl animate-fade-in-up delay-2">
                <h2 className="section-title">Pipeline Status</h2>
                <div className="grid grid-3 mt-md">
                    <div className="pipeline-stage">
                        <div className="pipeline-stage-header" style={{ borderColor: '#f59e0b' }}>
                            <Clock size={16} style={{ color: '#f59e0b' }} />
                            <span>In Progress</span>
                            <span className="pipeline-count">3</span>
                        </div>
                        <div className="pipeline-stage-body">
                            <div className="pipeline-item">AI Engineer — Step 4/6</div>
                            <div className="pipeline-item">Sales Executive — Step 2/6</div>
                            <div className="pipeline-item">UX Designer — Step 1/6</div>
                        </div>
                    </div>
                    <div className="pipeline-stage">
                        <div className="pipeline-stage-header" style={{ borderColor: '#3b82f6' }}>
                            <Users size={16} style={{ color: '#3b82f6' }} />
                            <span>Matching</span>
                            <span className="pipeline-count">2</span>
                        </div>
                        <div className="pipeline-stage-body">
                            <div className="pipeline-item">Product Manager — 8 candidates</div>
                            <div className="pipeline-item">Data Analyst — 12 candidates</div>
                        </div>
                    </div>
                    <div className="pipeline-stage">
                        <div className="pipeline-stage-header" style={{ borderColor: '#22c55e' }}>
                            <CheckCircle2 size={16} style={{ color: '#22c55e' }} />
                            <span>Completed</span>
                            <span className="pipeline-count">7</span>
                        </div>
                        <div className="pipeline-stage-body">
                            <div className="pipeline-item">HR Manager — Hired</div>
                            <div className="pipeline-item">Marketing Lead — Hired</div>
                            <div className="pipeline-item">+5 more</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
