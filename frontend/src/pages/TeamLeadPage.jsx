import { useState, useEffect } from 'react';
import {
    Plus, Send, XCircle, Eye, Clock, CheckCircle2,
    Calendar, Briefcase, FileText, RefreshCw,
    AlertTriangle, ArrowRight, ChevronDown, ChevronUp, Upload, Edit, Pencil,
    Search, MapPin, Building2, Layers
} from 'lucide-react';
import * as api from '../services/api';
import './TeamLeadPage.css';

const STATUS_CONFIG = {
    draft: { label: 'Draft', color: '#f59e0b', bg: '#fef3c7', icon: FileText },
    pending_hr: { label: 'Pending HR', color: '#3b82f6', bg: '#dbeafe', icon: Clock },
    active: { label: 'Active', color: '#16a34a', bg: '#dcfce7', icon: CheckCircle2 },
    cancelled: { label: 'Cancelled', color: '#ef4444', bg: '#fee2e2', icon: XCircle },
    closed: { label: 'Closed', color: '#6b7280', bg: '#f3f4f6', icon: CheckCircle2 },
};

export default function TeamLeadPage() {
    const [jobs, setJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [expandedJob, setExpandedJob] = useState(null);
    const [error, setError] = useState('');
    const [actionLoading, setActionLoading] = useState(null);
    const [editingJobId, setEditingJobId] = useState(null);

    // ── Form state ──
    const [roleTitle, setRoleTitle] = useState('');
    const [jdText, setJdText] = useState('');
    const [budget, setBudget] = useState('');
    const [adjustableBudget, setAdjustableBudget] = useState('');
    const [endDate, setEndDate] = useState('');

    // ── Dual-mode state ──
    const [createMode, setCreateMode] = useState('saved'); // 'saved' | 'manual'
    const [savedForms, setSavedForms] = useState([]);
    const [formSearch, setFormSearch] = useState('');
    const [selectedFormId, setSelectedFormId] = useState(null);
    const [selectedFormProfile, setSelectedFormProfile] = useState(null);
    const [formsLoading, setFormsLoading] = useState(false);

    useEffect(() => { loadJobs(); }, []);

    useEffect(() => {
        if (showForm && !editingJobId) {
            loadSavedForms();
        }
    }, [showForm]);

    async function loadSavedForms() {
        setFormsLoading(true);
        try {
            const data = await api.fetchSavedForms();
            setSavedForms(data);
        } catch (_) { /* silent */ }
        finally { setFormsLoading(false); }
    }

    async function loadJobs() {
        setLoading(true);
        try {
            const data = await api.listJobs();
            setJobs(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    async function handleCreate(e) {
        e.preventDefault();
        setActionLoading('create');
        try {
            // Build profile_json — wrap the generated_profile if coming from a saved form
            let profileJsonStr = null;
            if (createMode === 'saved' && selectedFormProfile) {
                const profileData = typeof selectedFormProfile === 'string'
                    ? selectedFormProfile
                    : JSON.stringify(selectedFormProfile);
                profileJsonStr = JSON.stringify({ generated_profile: JSON.parse(profileData) });
            }
            await api.createJob({
                role_title: roleTitle,
                jd_text: jdText || null,
                profile_json: profileJsonStr,
                budget: budget ? parseFloat(budget) : null,
                adjustable_budget: adjustableBudget ? parseFloat(adjustableBudget) : null,
                end_date: endDate || null,
            });
            resetForm();
            setShowForm(false);
            await loadJobs();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    }

    async function handleUpdate(e) {
        e.preventDefault();
        setActionLoading('update');
        try {
            await api.updateJob(editingJobId, {
                role_title: roleTitle,
                jd_text: jdText || null,
                budget: budget ? parseFloat(budget) : null,
                adjustable_budget: adjustableBudget ? parseFloat(adjustableBudget) : null,
                end_date: endDate || null,
            });
            resetForm();
            setShowForm(false);
            await loadJobs();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    }

    async function handleFileUpload(e) {
        const file = e.target.files[0];
        if (!file) return;

        setActionLoading('upload');
        try {
            const data = await api.uploadJD(file);
            setJdText(data.text);
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
            e.target.value = ''; // Reset input
        }
    }

    async function handleSubmit(jobId) {
        setActionLoading(`submit-${jobId}`);
        try {
            await api.submitJob(jobId);
            await loadJobs();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    }

    async function handleCancel(jobId) {
        if (!confirm('Cancel this job request? HR will be notified.')) return;
        setActionLoading(`cancel-${jobId}`);
        try {
            await api.cancelJob(jobId);
            await loadJobs();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(null);
        }
    }

    function resetForm() {
        setRoleTitle(''); setJdText(''); setBudget(''); setAdjustableBudget(''); setEndDate('');
        setEditingJobId(null);
        setSelectedFormId(null);
        setSelectedFormProfile(null);
        setCreateMode('saved');
        setFormSearch('');
        setError('');
    }

    function selectSavedForm(form) {
        if (selectedFormId === form.id) {
            // deselect
            setSelectedFormId(null);
            setSelectedFormProfile(null);
            setRoleTitle('');
            setJdText('');
            setBudget('');
            setAdjustableBudget('');
            setEndDate('');
            return;
        }
        setSelectedFormId(form.id);
        setSelectedFormProfile(form.generated_profile || null);
        setRoleTitle(form.role || '');
        setJdText(form.generated_jd || '');
    }

    function startEdit(job) {
        setEditingJobId(job.id);
        setRoleTitle(job.role_title);
        setJdText(job.jd_text || '');
        setBudget(job.budget || '');
        setAdjustableBudget(job.adjustable_budget || '');
        setEndDate(job.end_date ? job.end_date.split('T')[0] : '');
        setShowForm(true);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    const stats = {
        total: jobs.length,
        draft: jobs.filter(j => j.status === 'draft').length,
        pending: jobs.filter(j => j.status === 'pending_hr').length,
        active: jobs.filter(j => j.status === 'active').length,
    };

    return (
        <div className="tl-page">
            <div className="tl-header">
                <div>
                    <h1>Team Lead Dashboard</h1>
                    <p className="tl-subtitle">Create and manage job requests</p>
                </div>
                <button
                    className="tl-btn primary"
                    onClick={() => { resetForm(); setShowForm(!showForm); }}
                >
                    <Plus size={18} />
                    New Job Request
                </button>
            </div>

            {/* Stats */}
            <div className="tl-stats">
                {[
                    { label: 'Total', value: stats.total, color: '#818cf8', bg: '#eef2ff' },
                    { label: 'Drafts', value: stats.draft, color: '#f59e0b', bg: '#fef3c7' },
                    { label: 'Pending HR', value: stats.pending, color: '#3b82f6', bg: '#dbeafe' },
                    { label: 'Active', value: stats.active, color: '#16a34a', bg: '#dcfce7' },
                ].map(s => (
                    <div key={s.label} className="tl-stat-card" style={{ borderLeftColor: s.color }}>
                        <span className="tl-stat-value" style={{ color: s.color }}>{s.value}</span>
                        <span className="tl-stat-label">{s.label}</span>
                    </div>
                ))}
            </div>

            {/* Error */}
            {error && (
                <div className="tl-error">
                    <AlertTriangle size={16} /> {error}
                    <button onClick={() => setError('')}>✕</button>
                </div>
            )}

            {/* Create/Edit Form */}
            {showForm && (
                <form className="tl-create-section" onSubmit={editingJobId ? handleUpdate : handleCreate}>
                    <h3>
                        {editingJobId ? <Pencil size={18} /> : <Plus size={18} />}
                        {editingJobId ? 'Edit Job Request' : 'New Job Request'}
                    </h3>

                    {/* Mode tabs — only show for new, not edit */}
                    {!editingJobId && (
                        <div className="tl-mode-tabs">
                            <button
                                type="button"
                                className={`tl-mode-tab ${createMode === 'saved' ? 'active' : ''}`}
                                onClick={() => {
                                    setCreateMode('saved');
                                    setSelectedFormId(null);
                                    setSelectedFormProfile(null);
                                    setRoleTitle('');
                                    setJdText('');
                                    setBudget('');
                                    setAdjustableBudget('');
                                    setEndDate('');
                                }}
                            >
                                <Layers size={15} /> Use Saved Form
                            </button>
                            <button
                                type="button"
                                className={`tl-mode-tab ${createMode === 'manual' ? 'active' : ''}`}
                                onClick={() => {
                                    setCreateMode('manual');
                                    setSelectedFormId(null);
                                    setSelectedFormProfile(null);
                                    setRoleTitle('');
                                    setJdText('');
                                    setBudget('');
                                    setAdjustableBudget('');
                                    setEndDate('');
                                }}
                            >
                                <Edit size={15} /> Fill Manually
                            </button>
                        </div>
                    )}

                    {/* ── SAVED FORM MODE ── */}
                    {!editingJobId && createMode === 'saved' && (
                        <div className="tl-saved-section">
                            <div className="tl-search-bar">
                                <Search size={15} />
                                <input
                                    value={formSearch}
                                    onChange={e => setFormSearch(e.target.value)}
                                    placeholder="Search saved forms…"
                                />
                            </div>

                            {formsLoading ? (
                                <div className="tl-forms-loading">Loading saved forms…</div>
                            ) : (() => {
                                const filtered = savedForms.filter(f =>
                                    (f.role || '').toLowerCase().includes(formSearch.toLowerCase()) ||
                                    (f.department || '').toLowerCase().includes(formSearch.toLowerCase())
                                );
                                if (filtered.length === 0) {
                                    return (
                                        <div className="tl-forms-empty">
                                            <FileText size={32} />
                                            <p>{savedForms.length === 0 ? 'No saved forms yet. Ask your recruiter to create JD forms.' : 'No forms match your search.'}</p>
                                        </div>
                                    );
                                }
                                return (
                                    <div
                                        className="tl-forms-grid"
                                        onClick={(e) => {
                                            if (e.target === e.currentTarget) {
                                                setSelectedFormId(null);
                                                setSelectedFormProfile(null);
                                                setRoleTitle('');
                                                setJdText('');
                                                setBudget('');
                                                setAdjustableBudget('');
                                                setEndDate('');
                                            }
                                        }}
                                    >
                                        {filtered.map(form => (
                                            <div
                                                key={form.id}
                                                className={`tl-form-card ${selectedFormId === form.id ? 'selected' : ''} ${!form.generated_jd ? 'no-jd' : ''}`}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    selectSavedForm(form);
                                                }}
                                            >
                                                <div className="tl-form-card-header">
                                                    <Briefcase size={14} />
                                                    <span className="tl-form-card-role">{form.role || 'Untitled Role'}</span>
                                                </div>
                                                <div className="tl-form-card-details">
                                                    {form.department && (
                                                        <span><Building2 size={12} /> {form.department}</span>
                                                    )}
                                                    {form.location && (
                                                        <span><MapPin size={12} /> {form.location}</span>
                                                    )}
                                                    {form.experience && (
                                                        <span><Clock size={12} /> {form.experience}</span>
                                                    )}
                                                </div>
                                                {form.generated_jd ? (
                                                    <div className="tl-form-card-jd-badge has-jd">
                                                        <CheckCircle2 size={12} /> JD Generated
                                                    </div>
                                                ) : (
                                                    <div className="tl-form-card-jd-badge no-jd-badge">
                                                        <AlertTriangle size={12} /> No JD Yet
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                );
                            })()}

                            {/* Show selected form JD preview */}
                            {selectedFormId && jdText && (
                                <div className="tl-selected-preview">
                                    <label><FileText size={14} /> Generated JD Preview</label>
                                    <pre className="tl-jd-preview">{jdText}</pre>
                                </div>
                            )}
                        </div>
                    )}

                    {/* ── MANUAL MODE / EDIT MODE — standard fields ── */}
                    {(editingJobId || createMode === 'manual') && (
                        <div className="tl-form-grid">
                            <div className="tl-form-group">
                                <label><Briefcase size={14} /> Role Title *</label>
                                <input
                                    value={roleTitle} onChange={e => setRoleTitle(e.target.value)}
                                    placeholder="e.g. Senior Software Engineer" required
                                />
                            </div>
                            <div className="tl-form-group">
                                <label>Budget (LPA)</label>
                                <input
                                    type="number" step="0.1" value={budget}
                                    onChange={e => setBudget(e.target.value)}
                                    placeholder="e.g. 15"
                                />
                            </div>
                            <div className="tl-form-group">
                                <label>Adjustable Budget (LPA)</label>
                                <input
                                    type="number" step="0.1" value={adjustableBudget}
                                    onChange={e => setAdjustableBudget(e.target.value)}
                                    placeholder="e.g. 2"
                                />
                            </div>
                            <div className="tl-form-group">
                                <label><Calendar size={14} /> End Date</label>
                                <input
                                    type="date" value={endDate}
                                    onChange={e => setEndDate(e.target.value)}
                                />
                            </div>
                            <div className="tl-form-group full-width">
                                <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span><FileText size={14} /> Job Description</span>
                                    <div style={{ position: 'relative', overflow: 'hidden' }}>
                                        <button type="button" className="tl-btn ghost small" style={{ fontSize: '0.75rem', padding: '4px 8px' }}>
                                            <Upload size={12} /> {actionLoading === 'upload' ? 'Uploading...' : 'Upload DOCX/PDF'}
                                        </button>
                                        <input
                                            type="file"
                                            accept=".docx,.pdf"
                                            onChange={handleFileUpload}
                                            style={{ position: 'absolute', top: 0, left: 0, opacity: 0, width: '100%', height: '100%', cursor: 'pointer' }}
                                            disabled={actionLoading === 'upload'}
                                        />
                                    </div>
                                </label>
                                <textarea
                                    value={jdText} onChange={e => setJdText(e.target.value)}
                                    rows={5} placeholder="Paste or type the job description here…"
                                />
                            </div>
                        </div>
                    )}

                    {/* ── SAVED MODE — extra fields (budget, date) ── */}
                    {!editingJobId && createMode === 'saved' && (
                        <div className="tl-form-grid" style={{ marginTop: 16 }}>
                            <div className="tl-form-group">
                                <label>Budget (LPA)</label>
                                <input
                                    type="number" step="0.1" value={budget}
                                    onChange={e => setBudget(e.target.value)}
                                    placeholder="e.g. 15"
                                />
                            </div>
                            <div className="tl-form-group">
                                <label>Adjustable Budget (LPA)</label>
                                <input
                                    type="number" step="0.1" value={adjustableBudget}
                                    onChange={e => setAdjustableBudget(e.target.value)}
                                    placeholder="e.g. 2"
                                />
                            </div>
                            <div className="tl-form-group">
                                <label><Calendar size={14} /> End Date</label>
                                <input
                                    type="date" value={endDate}
                                    onChange={e => setEndDate(e.target.value)}
                                />
                            </div>
                        </div>
                    )}

                    <div className="tl-form-actions">
                        <button type="button" className="tl-btn ghost" onClick={() => { setShowForm(false); resetForm(); }}>
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="tl-btn primary"
                            disabled={
                                actionLoading === 'create' || actionLoading === 'update' ||
                                (!editingJobId && createMode === 'saved' && !selectedFormId)
                            }
                        >
                            {editingJobId
                                ? (actionLoading === 'update' ? 'Updating...' : 'Update Draft')
                                : (actionLoading === 'create' ? 'Creating...' : 'Create Draft')
                            }
                        </button>
                    </div>
                </form>
            )}

            {/* Job List */}
            <div className="tl-header" style={{ marginBottom: '14px' }}>
                <h2 className="tl-section-label">Your Job Requests</h2>
                <button className="tl-btn ghost" onClick={loadJobs}>
                    <RefreshCw size={14} /> Refresh
                </button>
            </div>

            {loading ? (
                <div className="tl-loading">Loading jobs…</div>
            ) : jobs.length === 0 ? (
                <div className="tl-empty">
                    <Briefcase size={40} />
                    <p>No job requests yet. Click <strong>"New Job Request"</strong> to get started.</p>
                </div>
            ) : (
                <div className="tl-job-list">
                    {jobs.map(job => {
                        const cfg = STATUS_CONFIG[job.status] || STATUS_CONFIG.draft;
                        const StatusIcon = cfg.icon;
                        const isExpanded = expandedJob === job.id;

                        return (
                            <div key={job.id} className="tl-job-card">
                                <div
                                    className="tl-job-row"
                                    onClick={() => setExpandedJob(isExpanded ? null : job.id)}
                                >
                                    <div className="tl-job-info">
                                        <h4>{job.role_title}</h4>
                                        <span className="tl-job-date">
                                            Created {new Date(job.created_at).toLocaleDateString()}
                                        </span>
                                    </div>

                                    <div className="tl-job-meta">
                                        {job.budget && (
                                            <span className="tl-chip budget">
                                                ₹{job.budget} LPA
                                            </span>
                                        )}
                                        {job.end_date && (
                                            <span className="tl-chip date">
                                                <Calendar size={12} /> {new Date(job.end_date).toLocaleDateString()}
                                            </span>
                                        )}
                                        <span
                                            className="tl-status-badge"
                                            style={{ color: cfg.color, background: cfg.bg }}
                                        >
                                            <StatusIcon size={14} /> {cfg.label}
                                        </span>
                                        {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                                    </div>
                                </div>

                                {isExpanded && (
                                    <div className="tl-job-expanded">
                                        {job.jd_text ? (
                                            <pre className="tl-jd-preview">{job.jd_text}</pre>
                                        ) : (
                                            <p className="tl-no-jd">No JD text yet. You can add one by editing this draft.</p>
                                        )}

                                        <div className="tl-job-actions">
                                            {job.status === 'draft' && (
                                                <>
                                                    <button
                                                        className="tl-btn primary small"
                                                        onClick={() => handleSubmit(job.id)}
                                                        disabled={actionLoading === `submit-${job.id}`}
                                                    >
                                                        <Send size={14} />
                                                        {actionLoading === `submit-${job.id}` ? 'Sending…' : 'Submit to HR'}
                                                    </button>
                                                    <button
                                                        className="tl-btn ghost small"
                                                        onClick={() => startEdit(job)}
                                                    >
                                                        <Edit size={14} /> Edit
                                                    </button>
                                                </>
                                            )}
                                            {!['cancelled', 'closed'].includes(job.status) && (
                                                <button
                                                    className="tl-btn danger small"
                                                    onClick={() => handleCancel(job.id)}
                                                    disabled={actionLoading === `cancel-${job.id}`}
                                                >
                                                    <XCircle size={14} />
                                                    {actionLoading === `cancel-${job.id}` ? 'Cancelling…' : 'Cancel Request'}
                                                </button>
                                            )}
                                        </div>
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
