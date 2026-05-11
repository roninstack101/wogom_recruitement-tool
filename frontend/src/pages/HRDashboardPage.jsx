import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Inbox, CheckCircle2, XCircle, Clock,
    RefreshCw, Users, AlertTriangle, ChevronDown,
    ChevronUp, Calendar, Briefcase, Eye, BarChart2,
    Pencil, Save, X
} from 'lucide-react';
import * as api from '../services/api';
import './HRDashboardPage.css';

const STATUS_CONFIG = {
    draft: { label: 'Draft', color: '#f59e0b', icon: Clock },
    pending_hr: { label: 'Pending', color: '#3b82f6', icon: Inbox },
    active: { label: 'Active', color: '#16a34a', icon: CheckCircle2 },
    cancelled: { label: 'Cancelled', color: '#ef4444', icon: XCircle },
    closed: { label: 'Closed', color: '#6b7280', icon: CheckCircle2 },
};

export default function HRDashboardPage() {
    const navigate = useNavigate();
    const [allJobs, setAllJobs] = useState([]);
    const [incoming, setIncoming] = useState([]);
    const [loading, setLoading] = useState(true);
    const [tab, setTab] = useState('incoming');  // incoming | all | analytics
    const [error, setError] = useState('');
    const [actionLoading, setActionLoading] = useState(null);
    const [expandedJob, setExpandedJob] = useState(null);
    const [candidates, setCandidates] = useState({});
    const [analyticsData, setAnalyticsData] = useState([]);

    // Edit state
    const [editingJob, setEditingJob] = useState(null);
    const [editForm, setEditForm] = useState({ role_title: '', jd_text: '', budget: '', end_date: '' });

    useEffect(() => {
        if (tab === 'analytics') loadAnalytics();
        else loadData();
    }, [tab]);

    async function loadData() {
        setLoading(true);
        try {
            const [allData, pendingData] = await Promise.all([
                api.listJobs(),
                api.incomingJobs(),
            ]);
            setAllJobs(allData);
            setIncoming(pendingData);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    async function loadAnalytics() {
        setLoading(true);
        try {
            const data = await api.getAnalytics();
            setAnalyticsData(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    function startEditing(job) {
        setEditingJob(job.id);
        setEditForm({
            role_title: job.role_title || '',
            jd_text: job.jd_text || '',
            budget: job.budget || '',
            end_date: job.end_date ? job.end_date.split('T')[0] : '',
        });
    }

    function cancelEditing() {
        setEditingJob(null);
        setEditForm({ role_title: '', jd_text: '', budget: '', end_date: '' });
    }

    async function handleSaveEdit(jobId) {
        setActionLoading(`edit-${jobId}`);
        try {
            await api.hrEditJob(jobId, {
                role_title: editForm.role_title,
                jd_text: editForm.jd_text,
                budget: editForm.budget ? parseFloat(editForm.budget) : null,
                end_date: editForm.end_date || null,
            });
            setEditingJob(null);
            await loadData();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    }

    async function handleActivate(jobId) {
        setActionLoading(`activate-${jobId}`);
        try {
            await api.activateJob(jobId);
            await loadData();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    }

    const stats = {
        pending: allJobs.filter(j => j.status === 'pending_hr').length,
        active: allJobs.filter(j => j.status === 'active').length,
        total: allJobs.length,
        cancelled: allJobs.filter(j => j.status === 'cancelled').length,
    };

    const displayJobs = tab === 'incoming' ? incoming : allJobs;

    return (
        <div className="hr-page">
            <div className="hr-header">
                <div>
                    <h1>HR Dashboard</h1>
                    <p className="hr-subtitle">Manage job requests and evaluate candidates</p>
                </div>
                <button className="hr-btn ghost" onClick={tab === 'analytics' ? loadAnalytics : loadData}>
                    <RefreshCw size={16} /> Refresh
                </button>
            </div>

            {/* Stats */}
            <div className="hr-stats">
                {[
                    { label: 'Pending Review', value: stats.pending, color: '#3b82f6', icon: Inbox },
                    { label: 'Active Jobs', value: stats.active, color: '#16a34a', icon: CheckCircle2 },
                    { label: 'Total Requests', value: stats.total, color: '#818cf8', icon: Briefcase },
                    { label: 'Cancelled', value: stats.cancelled, color: '#ef4444', icon: XCircle },
                ].map(s => {
                    const Icon = s.icon;
                    return (
                        <div key={s.label} className="hr-stat-card">
                            <div className="hr-stat-icon" style={{ background: `${s.color}18`, color: s.color }}>
                                <Icon size={20} />
                            </div>
                            <div>
                                <span className="hr-stat-value" style={{ color: s.color }}>{s.value}</span>
                                <span className="hr-stat-label">{s.label}</span>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Error */}
            {error && (
                <div className="hr-error">
                    <AlertTriangle size={16} /> {error}
                    <button onClick={() => setError('')}>✕</button>
                </div>
            )}

            {/* Tabs */}
            <div className="hr-tabs">
                <button
                    className={`hr-tab ${tab === 'incoming' ? 'active' : ''}`}
                    onClick={() => setTab('incoming')}
                >
                    <Inbox size={16} /> Incoming ({stats.pending})
                </button>
                <button
                    className={`hr-tab ${tab === 'all' ? 'active' : ''}`}
                    onClick={() => setTab('all')}
                >
                    <Briefcase size={16} /> All Jobs ({stats.total})
                </button>
                <button
                    className={`hr-tab ${tab === 'analytics' ? 'active' : ''}`}
                    onClick={() => setTab('analytics')}
                >
                    <BarChart2 size={16} /> Analytics
                </button>
            </div>

            {/* Analytics – Funnel View */}
            {tab === 'analytics' && (
                loading ? <div className="hr-loading">Loading analytics...</div> :
                    analyticsData.length === 0 ? (
                        <div className="hr-empty">
                            <BarChart2 size={40} />
                            <p>No data available</p>
                        </div>
                    ) : (
                        <div className="hr-analytics-grid">
                            {analyticsData.map(item => {
                                const stages = item.stages || {};
                                const total = item.total_candidates || 1;

                                const funnel = [
                                    { name: 'Applied', count: stages['Applied'] || 0, color: '#6366f1' },
                                    { name: 'CV Evaluated', count: stages['CV Evaluated'] || 0, color: '#818cf8' },
                                    { name: 'Requirement Gathering', count: stages['Requirement Gathering'] || 0, color: '#3b82f6' },
                                    { name: 'CV Shortlisted', count: stages['CV Shortlisted'] || 0, color: '#0ea5e9' },
                                    { name: 'Interviewed', count: stages['Interviewed'] || 0, color: '#8b5cf6' },
                                    { name: 'Offer', count: stages['Offer'] || 0, color: '#f59e0b' },
                                    { name: 'Hired', count: stages['Hired'] || 0, color: '#16a34a' },
                                ];

                                const maxCount = Math.max(...funnel.map(f => f.count), 1);

                                return (
                                    <div key={item.job_id} className="hr-stat-card full-width">
                                        <div className="hr-analytics-header">
                                            <h4>{item.role_title}</h4>
                                            <span className="hr-badge">{item.status}</span>
                                        </div>
                                        <div className="hr-funnel">
                                            {funnel.map((step, idx) => {
                                                const widthPct = maxCount > 0 ? Math.max((step.count / maxCount) * 100, 8) : 8;
                                                return (
                                                    <div key={step.name} className="hr-funnel-row">
                                                        <span className="hr-funnel-label">{step.name}</span>
                                                        <div className="hr-funnel-bar-wrap">
                                                            <div
                                                                className="hr-funnel-bar"
                                                                style={{
                                                                    width: `${widthPct}%`,
                                                                    background: `linear-gradient(135deg, ${step.color}, ${step.color}cc)`,
                                                                }}
                                                            >
                                                                <span className="hr-funnel-count">{step.count}</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )
            )}

            {/* Job List View */}
            {tab !== 'analytics' && (
                loading ? (
                    <div className="hr-loading">Loading jobs...</div>
                ) : displayJobs.length === 0 ? (
                    <div className="hr-empty">
                        <Inbox size={40} />
                        <p>{tab === 'incoming' ? 'No pending requests from Team Leads' : 'No jobs yet'}</p>
                    </div>
                ) : (
                    <div className="hr-job-list">
                        {displayJobs.map(job => {
                            const cfg = STATUS_CONFIG[job.status] || STATUS_CONFIG.draft;
                            const StatusIcon = cfg.icon;
                            const isExpanded = expandedJob === job.id;
                            const jobCandidates = candidates[job.id];
                            const isEditing = editingJob === job.id;

                            return (
                                <div key={job.id} className="hr-job-card">
                                    <div
                                        className="hr-job-row"
                                        onClick={() => setExpandedJob(isExpanded ? null : job.id)}
                                    >
                                        <div className="hr-job-info">
                                            <h4>{job.role_title}</h4>
                                            <span className="hr-job-meta-text">
                                                By {job.creator_name || 'Unknown'} · {new Date(job.created_at).toLocaleDateString()}
                                            </span>
                                        </div>
                                        <div className="hr-job-meta">
                                            {job.budget && (
                                                <span className="hr-chip budget">
                                                    ₹{job.budget} LPA
                                                </span>
                                            )}
                                            {job.end_date && (
                                                <span className="hr-chip date">
                                                    <Calendar size={12} /> {new Date(job.end_date).toLocaleDateString()}
                                                </span>
                                            )}
                                            <span
                                                className="hr-status-badge"
                                                style={{ color: cfg.color, background: `${cfg.color}18` }}
                                            >
                                                <StatusIcon size={14} /> {cfg.label}
                                            </span>
                                            {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                                        </div>
                                    </div>

                                    {isExpanded && (
                                        <div className="hr-job-expanded">
                                            {/* Edit form for pending_hr jobs */}
                                            {isEditing ? (
                                                <div className="hr-edit-form">
                                                    <div className="hr-edit-field">
                                                        <label>Role Title</label>
                                                        <input
                                                            type="text"
                                                            value={editForm.role_title}
                                                            onChange={e => setEditForm(prev => ({ ...prev, role_title: e.target.value }))}
                                                        />
                                                    </div>
                                                    <div className="hr-edit-field">
                                                        <label>Job Description</label>
                                                        <textarea
                                                            rows={6}
                                                            value={editForm.jd_text}
                                                            onChange={e => setEditForm(prev => ({ ...prev, jd_text: e.target.value }))}
                                                        />
                                                    </div>
                                                    <div className="hr-edit-row">
                                                        <div className="hr-edit-field">
                                                            <label>Budget (LPA)</label>
                                                            <input
                                                                type="number"
                                                                value={editForm.budget}
                                                                onChange={e => setEditForm(prev => ({ ...prev, budget: e.target.value }))}
                                                            />
                                                        </div>
                                                        <div className="hr-edit-field">
                                                            <label>End Date</label>
                                                            <input
                                                                type="date"
                                                                value={editForm.end_date}
                                                                onChange={e => setEditForm(prev => ({ ...prev, end_date: e.target.value }))}
                                                            />
                                                        </div>
                                                    </div>
                                                    <div className="hr-edit-actions">
                                                        <button
                                                            className="hr-btn primary"
                                                            onClick={() => handleSaveEdit(job.id)}
                                                            disabled={actionLoading === `edit-${job.id}`}
                                                        >
                                                            <Save size={14} />
                                                            {actionLoading === `edit-${job.id}` ? 'Saving…' : 'Save Changes'}
                                                        </button>
                                                        <button className="hr-btn ghost" onClick={cancelEditing}>
                                                            <X size={14} /> Cancel
                                                        </button>
                                                    </div>
                                                </div>
                                            ) : (
                                                <>
                                                    {job.jd_text ? (
                                                        <pre className="hr-jd-preview">{job.jd_text}</pre>
                                                    ) : (
                                                        <p className="hr-no-jd">No JD text provided.</p>
                                                    )}
                                                </>
                                            )}

                                            <div className="hr-job-actions">
                                                {/* Pending → Edit + Activate */}
                                                {job.status === 'pending_hr' && !isEditing && (
                                                    <>
                                                        <button
                                                            className="hr-btn secondary"
                                                            onClick={() => startEditing(job)}
                                                        >
                                                            <Pencil size={14} /> Edit Request
                                                        </button>
                                                        <button
                                                            className="hr-btn primary"
                                                            onClick={() => handleActivate(job.id)}
                                                            disabled={actionLoading === `activate-${job.id}`}
                                                        >
                                                            <CheckCircle2 size={14} />
                                                            {actionLoading === `activate-${job.id}` ? 'Activating…' : 'Accept & Activate'}
                                                        </button>
                                                    </>
                                                )}

                                                {/* Active → View Candidates */}
                                                {job.status === 'active' && (
                                                    <>
                                                        <button
                                                            className="hr-btn ghost"
                                                            onClick={() => navigate('/tracking')}
                                                        >
                                                            <Eye size={14} /> Candidate Tracking
                                                        </button>
                                                    </>
                                                )}
                                            </div>

                                            {/* Candidates table */}
                                            {jobCandidates && (
                                                <div className="hr-candidates">
                                                    <h5><Users size={16} /> Candidates ({jobCandidates.length})</h5>
                                                    {jobCandidates.length === 0 ? (
                                                        <p className="hr-no-cand">No candidates yet.</p>
                                                    ) : (
                                                        <table className="hr-cand-table">
                                                            <thead>
                                                                <tr>
                                                                    <th>Name</th>
                                                                    <th>Email</th>
                                                                    <th>Stage</th>
                                                                    <th>Applied</th>
                                                                </tr>
                                                            </thead>
                                                            <tbody>
                                                                {jobCandidates.map(c => (
                                                                    <tr key={c.id}>
                                                                        <td>{c.name}</td>
                                                                        <td>{c.email}</td>
                                                                        <td>
                                                                            <span className="hr-stage-badge">{c.stage}</span>
                                                                        </td>
                                                                        <td>{new Date(c.applied_at).toLocaleDateString()}</td>
                                                                    </tr>
                                                                ))}
                                                            </tbody>
                                                        </table>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )
            )}
        </div>
    );
}
