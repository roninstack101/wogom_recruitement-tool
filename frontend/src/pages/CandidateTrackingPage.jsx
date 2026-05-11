import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Users, RefreshCw, Briefcase, ChevronDown, ChevronUp,
    AlertTriangle, Search, Filter, Eye
} from 'lucide-react';
import * as api from '../services/api';
import './CandidateTrackingPage.css';

const STAGE_COLORS = {
    'Applied': '#6366f1',
    'CV Evaluated': '#818cf8',
    'Requirement Gathering': '#3b82f6',
    'CV Shortlisted': '#0ea5e9',
    'Interviewed': '#8b5cf6',
    'Offer': '#f59e0b',
    'Hired': '#16a34a',
};

const STAGES = Object.keys(STAGE_COLORS);

export default function CandidateTrackingPage() {
    const navigate = useNavigate();
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [expandedJob, setExpandedJob] = useState(null);
    const [search, setSearch] = useState('');
    const [stageFilter, setStageFilter] = useState('');

    useEffect(() => { loadData(); }, []);

    async function loadData() {
        setLoading(true);
        setError('');
        try {
            const result = await api.getAllCandidates();
            setData(result);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    // Flatten all candidates with role info for counting
    const allCandidates = data.flatMap(job =>
        (job.candidates || []).map(c => ({ ...c, role_title: job.role_title, job_id: job.job_id }))
    );

    const totalCandidates = allCandidates.length;
    const totalJobs = data.length;

    // Stage summary counts
    const stageSummary = {};
    allCandidates.forEach(c => {
        const s = c.stage || 'Unknown';
        stageSummary[s] = (stageSummary[s] || 0) + 1;
    });

    return (
        <div className="ct-page">
            <div className="ct-header">
                <div>
                    <h1>Candidate Tracking</h1>
                    <p className="ct-subtitle">Candidates applying for your posted roles</p>
                </div>
                <button className="ct-btn ghost" onClick={loadData}>
                    <RefreshCw size={16} /> Refresh
                </button>
            </div>

            {/* Summary Cards */}
            <div className="ct-summary">
                <div className="ct-summary-card">
                    <Briefcase size={20} className="ct-summary-icon" />
                    <div>
                        <span className="ct-summary-value">{totalJobs}</span>
                        <span className="ct-summary-label">Active Roles</span>
                    </div>
                </div>
                <div className="ct-summary-card">
                    <Users size={20} className="ct-summary-icon" />
                    <div>
                        <span className="ct-summary-value">{totalCandidates}</span>
                        <span className="ct-summary-label">Total Candidates</span>
                    </div>
                </div>
                {STAGES.map(stage => (
                    <div key={stage} className={`ct-summary-card mini ${stageFilter === stage ? 'active-filter' : ''}`} onClick={() => setStageFilter(stageFilter === stage ? '' : stage)} style={{ cursor: 'pointer', borderColor: stageFilter === stage ? STAGE_COLORS[stage] : undefined }}>
                        <span className="ct-stage-dot" style={{ background: STAGE_COLORS[stage] }}></span>
                        <div>
                            <span className="ct-summary-value">{stageSummary[stage] || 0}</span>
                            <span className="ct-summary-label">{stage}</span>
                        </div>
                    </div>
                ))}
            </div>

            {/* Error */}
            {error && (
                <div className="ct-error">
                    <AlertTriangle size={16} /> {error}
                    <button onClick={() => setError('')}>✕</button>
                </div>
            )}

            {/* Search */}
            <div className="ct-toolbar">
                <div className="ct-search">
                    <Search size={16} />
                    <input
                        type="text"
                        placeholder="Search candidates by name or email..."
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                </div>
                {stageFilter && (
                    <button className="ct-btn ghost" onClick={() => setStageFilter('')}>
                        <Filter size={14} /> Clear: {stageFilter}
                    </button>
                )}
            </div>

            {/* Content */}
            {loading ? (
                <div className="ct-loading">Loading candidates...</div>
            ) : data.length === 0 ? (
                <div className="ct-empty">
                    <Users size={40} />
                    <p>No posted jobs with candidates yet</p>
                    <p className="ct-empty-sub">Activate a job from the HR Dashboard to start tracking candidates.</p>
                </div>
            ) : (
                <div className="ct-job-list">
                    {data.map(job => {
                        const isExpanded = expandedJob === job.job_id;
                        let filteredCandidates = job.candidates || [];

                        // Apply filters
                        if (search) {
                            const q = search.toLowerCase();
                            filteredCandidates = filteredCandidates.filter(c =>
                                c.name?.toLowerCase().includes(q) || c.email?.toLowerCase().includes(q)
                            );
                        }
                        if (stageFilter) {
                            filteredCandidates = filteredCandidates.filter(c => c.stage === stageFilter);
                        }

                        const totalForJob = job.candidates?.length || 0;
                        const filteredCount = filteredCandidates.length;

                        // Stage counts per job for funnel
                        const jobStageCounts = {};
                        (job.candidates || []).forEach(c => {
                            const s = c.stage || 'Unknown';
                            jobStageCounts[s] = (jobStageCounts[s] || 0) + 1;
                        });
                        const maxStageCount = Math.max(...Object.values(jobStageCounts), 1);

                        return (
                            <div key={job.job_id} className="ct-job-card">
                                <div
                                    className="ct-job-row"
                                    onClick={() => setExpandedJob(isExpanded ? null : job.job_id)}
                                >
                                    <div className="ct-job-info">
                                        <h4>{job.role_title}</h4>
                                        <div className="ct-job-meta">
                                            <span className="ct-badge" style={{ background: `${job.status === 'active' ? '#16a34a' : '#6b7280'}18`, color: job.status === 'active' ? '#16a34a' : '#6b7280' }}>
                                                {job.status}
                                            </span>
                                            <span className="ct-count">
                                                <Users size={14} /> {filteredCount}{filteredCount !== totalForJob ? ` / ${totalForJob}` : ''} candidates
                                            </span>
                                        </div>
                                    </div>
                                    {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                                </div>

                                {isExpanded && (
                                    <div className="ct-job-expanded">
                                        {/* Stage Funnel per Role */}
                                        <div className="ct-role-funnel">
                                            <h5>Stage Distribution</h5>
                                            <div className="ct-funnel-rows">
                                                {STAGES.map(stage => {
                                                    const count = jobStageCounts[stage] || 0;
                                                    const widthPct = maxStageCount > 0
                                                        ? Math.max((count / maxStageCount) * 100, count > 0 ? 12 : 4)
                                                        : 4;
                                                    return (
                                                        <div key={stage} className="ct-funnel-row">
                                                            <span className="ct-funnel-label">{stage}</span>
                                                            <div className="ct-funnel-bar-wrap">
                                                                <div
                                                                    className="ct-funnel-bar"
                                                                    style={{
                                                                        width: `${widthPct}%`,
                                                                        background: `linear-gradient(135deg, ${STAGE_COLORS[stage]}, ${STAGE_COLORS[stage]}cc)`,
                                                                    }}
                                                                >
                                                                    <span className="ct-funnel-count">{count}</span>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>

                                        {/* Action Buttons */}
                                        <div className="ct-actions">
                                            <button
                                                className="ct-btn evaluate"
                                                onClick={() => navigate('/candidate', { state: { generatedProfile: job.generated_profile, jdText: job.jd_text, roleTitle: job.role_title } })}
                                            >
                                                <Eye size={14} /> Evaluate CVs
                                            </button>
                                        </div>

                                        {/* Candidate Table */}
                                        {filteredCandidates.length === 0 ? (
                                            <p className="ct-no-cand">No candidates match your filters.</p>
                                        ) : (
                                            <table className="ct-table">
                                                <thead>
                                                    <tr>
                                                        <th>Name</th>
                                                        <th>Email</th>
                                                        <th>Stage</th>
                                                        <th>Applied</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {filteredCandidates.map(c => (
                                                        <tr key={c.id}>
                                                            <td className="ct-name">{c.name}</td>
                                                            <td>{c.email}</td>
                                                            <td>
                                                                <span
                                                                    className="ct-stage-badge"
                                                                    style={{
                                                                        background: `${STAGE_COLORS[c.stage] || '#6b7280'}18`,
                                                                        color: STAGE_COLORS[c.stage] || '#6b7280',
                                                                    }}
                                                                >
                                                                    {c.stage}
                                                                </span>
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
                        );
                    })}
                </div>
            )}
        </div>
    );
}
