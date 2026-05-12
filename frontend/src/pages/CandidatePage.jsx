import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import {
    Upload, Rocket, Trophy, Search, Filter, Users,
    Brain, Target, ChevronRight, Star, AlertTriangle,
    CheckCircle, BarChart3, Sparkles, FileText, Download, MapPin
} from 'lucide-react';
import * as XLSX from 'xlsx';
import FileUpload from '../components/FileUpload';
import * as api from '../services/api';
import './CandidatePage.css';

const STEPS = [
    { id: 'profile', label: 'Role Profile', icon: Target },
    { id: 'personas', label: 'Personas', icon: Brain },
    { id: 'upload', label: 'Upload CVs', icon: Upload },
    { id: 'results', label: 'Results', icon: Trophy },
];

function gradeColor(grade) {
    if (!grade) return 'var(--slate-500)';
    const g = grade.replace(/[+-]/g, '');
    if (g === 'A') return 'var(--emerald-500, #10b981)';
    if (g === 'B') return 'var(--blue-500, #3b82f6)';
    if (g === 'C') return 'var(--amber-500, #f59e0b)';
    return 'var(--red-500, #ef4444)';
}

function scoreBarColor(score) {
    if (score >= 80) return 'linear-gradient(90deg, #10b981, #059669)';
    if (score >= 60) return 'linear-gradient(90deg, #3b82f6, #6366f1)';
    if (score >= 40) return 'linear-gradient(90deg, #f59e0b, #f97316)';
    return 'linear-gradient(90deg, #ef4444, #dc2626)';
}

export default function CandidatePage() {
    const location = useLocation();
    const [step, setStep] = useState('profile');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // Profile state
    const [profileJson, setProfileJson] = useState('');
    const [profile, setProfile] = useState(null);
    const [profileMode, setProfileMode] = useState('describe'); // 'describe' | 'paste'
    const [description, setDescription] = useState('');

    // Job ID for DB persistence
    const [jobId, setJobId] = useState('');

    // Auto-fill from navigation state (e.g. from Candidate Tracking)
    useEffect(() => {
        const state = location.state;
        if (state?.jobId) setJobId(String(state.jobId));
        if (state?.generatedProfile) {
            const profileData = typeof state.generatedProfile === 'string'
                ? state.generatedProfile
                : JSON.stringify(state.generatedProfile, null, 2);
            setProfileJson(profileData);
            try {
                setProfile(typeof state.generatedProfile === 'string'
                    ? JSON.parse(state.generatedProfile)
                    : state.generatedProfile);
            } catch {
                setProfile(profileData);
            }
            setStep('personas');
        } else if (state?.jdText) {
            setProfileJson(state.jdText);
            try {
                setProfile(JSON.parse(state.jdText));
            } catch {
                setProfile(state.jdText);
            }
            setStep('personas');
        }
    }, []);

    // Personas state
    const [personas, setPersonas] = useState([]);

    // CV upload + evaluation
    const [resumeFile, setResumeFile] = useState(null);
    const [evaluations, setEvaluations] = useState([]);

    // Final ranking + DB summary
    const [ranking, setRanking] = useState(null);
    const [dbSummary, setDbSummary] = useState(null);

    // Expanded row tracking
    const [expandedRow, setExpandedRow] = useState(null);

    // ─── Step 1: Parse profile ───
    const handleProfileSubmit = async () => {
        setError('');

        if (profileMode === 'describe') {
            if (!description.trim()) {
                setError('Please describe the role.');
                return;
            }
            setLoading(true);
            try {
                const data = await api.quickGenerateProfile(description.trim());
                if (data.error) throw new Error(data.error);
                setProfile(data.profile);
                setProfileJson(JSON.stringify(data.profile, null, 2));
                setStep('personas');
            } catch (err) {
                setError(err.message || 'Failed to generate profile.');
            }
            setLoading(false);
        } else {
            const trimmed = profileJson.trim();
            if (!trimmed) {
                setError('Please paste a profile JSON.');
                return;
            }
            try {
                setProfile(JSON.parse(trimmed));
            } catch {
                setError('Invalid JSON. Please paste a valid profile from Agent 2.');
                return;
            }
            setStep('personas');
        }
    };

    // ─── Step 2: Generate personas ───
    const handleGeneratePersonas = async () => {
        setLoading(true);
        setError('');
        try {
            const data = await api.buildPersonas(profile);
            if (data.error) throw new Error(data.error);
            setPersonas(data.personas || []);
            setStep('upload');
        } catch (err) {
            setError(err.message || 'Failed to generate personas.');
        }
        setLoading(false);
    };

    // ─── Step 3: Evaluate CVs ───
    const [progressMsg, setProgressMsg] = useState('');

    const handleEvaluate = async () => {
        if (!resumeFile) return;
        setLoading(true);
        setError('');
        setProgressMsg('Uploading resumes…');

        try {
            const parsedJobId = jobId && !isNaN(Number(jobId)) ? Number(jobId) : null;
            const data = await api.startCVPipeline(resumeFile, profile, parsedJobId);
            if (data.error) throw new Error(data.error);

            const evalJobId = data.job_id;
            setProgressMsg('Processing started…');

            await new Promise((resolve, reject) => {
                const interval = setInterval(async () => {
                    try {
                        const status = await api.getCVJobStatus(evalJobId);
                        setProgressMsg(status.message || 'Processing…');

                        if (status.status === 'complete') {
                            clearInterval(interval);
                            const result = status.result;
                            setEvaluations(result.evaluations || []);
                            setRanking(result.ranking);
                            setDbSummary(result.db_summary || null);
                            setStep('results');
                            resolve();
                        } else if (status.status === 'failed') {
                            clearInterval(interval);
                            reject(new Error(status.error || 'Evaluation failed.'));
                        } else if (status.status === 'not_found') {
                            clearInterval(interval);
                            reject(new Error('Job lost — server may have restarted. Please try again.'));
                        }
                    } catch (pollErr) {
                        clearInterval(interval);
                        reject(pollErr);
                    }
                }, 5000);
            });

        } catch (err) {
            setError(err.message || 'CV evaluation failed.');
        }

        setLoading(false);
        setProgressMsg('');
    };

    const handleDownloadExcel = () => {
        if (!ranking?.shortlist?.length) return;
        const rows = ranking.shortlist.map(row => ({
            Rank: row.rank,
            Candidate: row.candidate_id,
            Location: row.location || '—',
            'Best Persona': row.persona_name || row.persona,
            Score: row.score,
            Grade: row.grade,
            Summary: row.why || '',
        }));
        const ws = XLSX.utils.json_to_sheet(rows);
        ws['!cols'] = [
            { wch: 6 }, { wch: 30 }, { wch: 25 }, { wch: 25 },
            { wch: 8 }, { wch: 8 }, { wch: 60 },
        ];
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, 'Candidates');
        XLSX.writeFile(wb, `candidate_results_${Date.now()}.xlsx`);
    };

    const currentStepIdx = STEPS.findIndex(s => s.id === step);

    return (
        <div className="candidate-page">
            {/* Page Header */}
            <div className="page-header animate-fade-in">
                <div className="flex items-center gap-sm">
                    <Users size={20} style={{ color: 'var(--accent-primary)' }} />
                    <h1>CV Analysis Pipeline</h1>
                </div>
                <p>Persona-based candidate evaluation — powered by AI</p>
            </div>

            {/* Step Indicator */}
            <div className="cv-stepper animate-fade-in-up delay-1">
                {STEPS.map((s, i) => {
                    const Icon = s.icon;
                    const isActive = s.id === step;
                    const isDone = i < currentStepIdx;
                    return (
                        <div key={s.id} className="cv-stepper-row">
                            <button
                                className={`cv-step ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}`}
                                onClick={() => isDone && setStep(s.id)}
                                disabled={!isDone && !isActive}
                                id={`step-${s.id}`}
                            >
                                <div className="cv-step-icon">
                                    {isDone ? <CheckCircle size={18} /> : <Icon size={18} />}
                                </div>
                                <span>{s.label}</span>
                            </button>
                            {i < STEPS.length - 1 && (
                                <ChevronRight size={16} className="cv-step-arrow" />
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Error */}
            {error && (
                <div className="alert alert-error mt-md animate-fade-in">
                    <AlertTriangle size={16} /> {error}
                </div>
            )}

            {/* ═══ STEP 1: Profile Input ═══ */}
            {step === 'profile' && (
                <div className="card animate-fade-in-up delay-2">
                    <h3 className="section-heading">
                        <Target size={16} /> Role Profile
                    </h3>

                    {/* Mode toggle */}
                    <div className="cv-mode-toggle mb-md">
                        <button
                            className={`cv-mode-btn ${profileMode === 'describe' ? 'active' : ''}`}
                            onClick={() => setProfileMode('describe')}
                        >
                            <Sparkles size={14} /> JD / Description
                        </button>
                        <button
                            className={`cv-mode-btn ${profileMode === 'paste' ? 'active' : ''}`}
                            onClick={() => setProfileMode('paste')}
                        >
                            <FileText size={14} /> Profile JSON
                        </button>
                    </div>

                    {profileMode === 'describe' ? (
                        <>
                            <p className="text-sm text-muted mb-md">
                                Paste an existing Job Description or describe the role in plain text — the AI will convert it into a structured profile automatically.
                            </p>
                            <textarea
                                className="cv-textarea"
                                rows={10}
                                placeholder="Paste a full Job Description or write a short description e.g. 'We need a Backend Engineer with 3–5 years in Python, FastAPI, PostgreSQL...'"
                                value={description}
                                onChange={e => setDescription(e.target.value)}
                                id="description-input"
                            />
                        </>
                    ) : (
                        <>
                            <p className="text-sm text-muted mb-md">
                                Paste the profile JSON generated by Agent 2 (Profile Builder).
                            </p>
                            <textarea
                                className="cv-textarea"
                                rows={12}
                                placeholder='{ "role": "Backend Engineer", "must_have_skills_refined": [...], ... }'
                                value={profileJson}
                                onChange={e => setProfileJson(e.target.value)}
                                id="profile-input"
                            />
                        </>
                    )}

                    <div className="mt-md">
                        <button
                            className="btn btn-primary"
                            disabled={loading || (profileMode === 'describe' ? !description.trim() : !profileJson.trim())}
                            onClick={handleProfileSubmit}
                            id="submit-profile-btn"
                        >
                            {loading ? (
                                <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Generating Profile…</>
                            ) : (
                                <><ChevronRight size={16} /> Continue to Personas</>
                            )}
                        </button>
                    </div>
                </div>
            )}

            {/* ═══ STEP 2: Persona Generation ═══ */}
            {step === 'personas' && (
                <div className="animate-fade-in-up">
                    <div className="card mb-lg">
                        <h3 className="section-heading">
                            <Brain size={16} /> Ideal Candidate Personas
                        </h3>
                        <p className="text-sm text-muted mb-md">
                            Generate 3–5 distinct ideal candidate personas from the role profile.
                            Each represents a different type of successful hire.
                        </p>

                        {personas.length === 0 ? (
                            <button
                                className="btn btn-primary btn-lg"
                                disabled={loading}
                                onClick={handleGeneratePersonas}
                                id="generate-personas-btn"
                            >
                                {loading ? (
                                    <>
                                        <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                                        Generating personas…
                                    </>
                                ) : (
                                    <>
                                        <Sparkles size={16} /> Generate Personas
                                    </>
                                )}
                            </button>
                        ) : (
                            <>
                                <div className="persona-grid">
                                    {personas.map((p, i) => (
                                        <div key={p.persona_id} className="persona-card" style={{ animationDelay: `${i * 0.1}s` }}>
                                            <div className="persona-header">
                                                <span className="persona-id">{p.persona_id}</span>
                                                <h4 className="persona-name">{p.name}</h4>
                                            </div>
                                            <p className="persona-summary">{p.summary}</p>
                                            <div className="persona-meta">
                                                <span className="badge badge-info">{p.experience_range}</span>
                                            </div>
                                            <div className="persona-section">
                                                <strong>Core Strengths</strong>
                                                <ul>{p.core_strengths?.map((s, j) => <li key={j}>{s}</li>)}</ul>
                                            </div>
                                            <div className="persona-section">
                                                <strong>Required Skills</strong>
                                                <div className="tag-list">
                                                    {p.required_skills?.map((s, j) => (
                                                        <span key={j} className="skill-tag">{s}</span>
                                                    ))}
                                                </div>
                                            </div>
                                            <div className="persona-section">
                                                <strong>Red Flags</strong>
                                                <ul className="red-flags">
                                                    {p.red_flags?.map((f, j) => (
                                                        <li key={j}><AlertTriangle size={12} /> {f}</li>
                                                    ))}
                                                </ul>
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                <div className="mt-lg">
                                    <button
                                        className="btn btn-primary"
                                        onClick={() => setStep('upload')}
                                        id="continue-to-upload-btn"
                                    >
                                        <ChevronRight size={16} /> Continue to CV Upload
                                    </button>
                                    <button
                                        className="btn btn-secondary ml-sm"
                                        disabled={loading}
                                        onClick={() => { setPersonas([]); handleGeneratePersonas(); }}
                                    >
                                        <Sparkles size={14} /> Regenerate
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}

            {/* ═══ STEP 3: CV Upload & Evaluate ═══ */}
            {step === 'upload' && (
                <div className="card animate-fade-in-up">
                    <h3 className="section-heading">
                        <Upload size={16} /> Upload Candidate Resumes
                    </h3>
                    <p className="text-sm text-muted mb-md">
                        Upload a ZIP file containing resumes, or a single PDF/DOCX file.
                        Each will be evaluated against the {personas.length} persona(s) generated above.
                    </p>

                    <div style={{ maxWidth: 400 }}>
                        <label className="text-sm font-semibold mb-xs" style={{ display: 'block' }}>
                            Job ID <span style={{ color: 'var(--slate-400)', fontWeight: 400 }}>(optional — leave blank to evaluate without saving)</span>
                        </label>
                        <input
                            type="number"
                            className="input"
                            placeholder="e.g. 3 — or leave blank for quick evaluation"
                            value={jobId}
                            onChange={e => setJobId(e.target.value)}
                            style={{ marginBottom: '1rem' }}
                            id="job-id-input"
                        />
                    </div>

                    <div style={{ maxWidth: 400 }}>
                        <FileUpload
                            label="Resumes (ZIP, PDF, DOCX)"
                            accept=".zip,.pdf,.docx"
                            onFile={setResumeFile}
                            id="cv-upload"
                        />
                    </div>

                    <div className="mt-lg">
                        <button
                            className="btn btn-primary btn-lg"
                            disabled={!resumeFile || loading}
                            onClick={handleEvaluate}
                            id="evaluate-btn"
                        >
                            {loading ? (
                                <>
                                    <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                                    Evaluating CVs…
                                </>
                            ) : (
                                <>
                                    <Rocket size={16} /> Evaluate & Rank Candidates
                                </>
                            )}
                        </button>
                    </div>

                    {loading && (
                        <div className="cv-progress-msg mt-md">
                            <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2, flexShrink: 0 }} />
                            {progressMsg || 'Processing…'}
                        </div>
                    )}
                </div>
            )}

            {/* ═══ STEP 4: Results ═══ */}
            {step === 'results' && ranking && (
                <div className="results-section animate-fade-in-up">
                    {/* Summary stats */}
                    <div className="cv-stats-row mb-lg">
                        <div className="cv-stat-card">
                            <FileText size={20} />
                            <div>
                                <div className="cv-stat-value">{ranking.total_evaluated}</div>
                                <div className="cv-stat-label">CVs Evaluated</div>
                            </div>
                        </div>
                        <div className="cv-stat-card">
                            <Trophy size={20} style={{ color: 'var(--amber-500)' }} />
                            <div>
                                <div className="cv-stat-value">{ranking.shortlist?.length || 0}</div>
                                <div className="cv-stat-label">Shortlisted</div>
                            </div>
                        </div>
                        <div className="cv-stat-card">
                            <Brain size={20} />
                            <div>
                                <div className="cv-stat-value">
                                    {Object.keys(ranking.persona_distribution || {}).length}
                                </div>
                                <div className="cv-stat-label">Persona Types</div>
                            </div>
                        </div>
                    </div>

                    {/* DB save confirmation */}
                    {dbSummary && (
                        <div className="alert alert-success mb-md animate-fade-in" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <CheckCircle size={16} />
                            {dbSummary.candidates_saved} candidate(s) saved to Job #{dbSummary.job_id}
                        </div>
                    )}

                    {/* Ranking Table */}
                    <div className="toolbar">
                        <div className="flex items-center gap-sm">
                            <Trophy size={18} className="trophy-icon" />
                            <h2>Top Candidates</h2>
                            <span className="badge badge-info">
                                {ranking.shortlist?.length || 0} results
                            </span>
                        </div>
                        <button className="btn btn-secondary" onClick={handleDownloadExcel}>
                            <Download size={15} /> Download Excel
                        </button>
                    </div>

                    {ranking.shortlist && ranking.shortlist.length > 0 ? (
                        <div className="results-table-wrap card"
                            style={{ borderTopLeftRadius: 0, borderTopRightRadius: 0, borderTop: 'none' }}>
                            <table className="data-table">
                                <thead>
                                    <tr>
                                        <th>Rank</th>
                                        <th>Candidate</th>
                                        <th>Location</th>
                                        <th>Best Persona</th>
                                        <th>Score</th>
                                        <th>Grade</th>
                                        <th>Summary</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {ranking.shortlist.map((row, i) => (
                                        <>
                                            <tr
                                                key={`row-${i}`}
                                                className={`result-row ${expandedRow === i ? 'expanded' : ''}`}
                                                onClick={() => setExpandedRow(expandedRow === i ? null : i)}
                                                style={{ cursor: 'pointer' }}
                                            >
                                                <td>
                                                    <span className="rank-badge">
                                                        {row.rank}
                                                    </span>
                                                </td>
                                                <td className="font-semibold">
                                                    {row.candidate_id}
                                                </td>
                                                <td className="text-sm" style={{ color: 'var(--slate-500)' }}>
                                                    {row.location ? (
                                                        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                                            <MapPin size={12} /> {row.location}
                                                        </span>
                                                    ) : '—'}
                                                </td>
                                                <td>
                                                    <span className="badge badge-accent">
                                                        {row.persona_name || row.persona}
                                                    </span>
                                                </td>
                                                <td>
                                                    <div className="fit-bar">
                                                        <div
                                                            className="fit-fill"
                                                            style={{
                                                                width: `${row.score || 0}%`,
                                                                background: scoreBarColor(row.score),
                                                            }}
                                                        />
                                                        <span className="fit-label">
                                                            {row.score || 0}
                                                        </span>
                                                    </div>
                                                </td>
                                                <td>
                                                    <span
                                                        className="grade-badge"
                                                        style={{ color: gradeColor(row.grade) }}
                                                    >
                                                        {row.grade}
                                                    </span>
                                                </td>
                                                <td className="text-sm">{row.why || '—'}</td>
                                            </tr>

                                            {/* Expanded persona breakdown */}
                                            {expandedRow === i && row.persona_results && (
                                                <tr key={`detail-${i}`} className="detail-row">
                                                    <td colSpan={7}>
                                                        <div className="persona-breakdown">
                                                            <h4>Persona Breakdown</h4>
                                                            <div className="breakdown-grid">
                                                                {row.persona_results.map((pr, j) => (
                                                                    <div key={j} className="breakdown-card">
                                                                        <div className="breakdown-header">
                                                                            <span className="breakdown-persona">
                                                                                {pr.persona_id}
                                                                            </span>
                                                                            <span
                                                                                className="grade-badge"
                                                                                style={{ color: gradeColor(pr.grade) }}
                                                                            >
                                                                                {pr.grade} ({pr.score})
                                                                            </span>
                                                                        </div>
                                                                        {pr.strengths?.length > 0 && (
                                                                            <div className="breakdown-section">
                                                                                <strong>
                                                                                    <Star size={12} /> Strengths
                                                                                </strong>
                                                                                <ul>
                                                                                    {pr.strengths.map((s, k) => (
                                                                                        <li key={k}>{s}</li>
                                                                                    ))}
                                                                                </ul>
                                                                            </div>
                                                                        )}
                                                                        {pr.gaps?.length > 0 && (
                                                                            <div className="breakdown-section">
                                                                                <strong>
                                                                                    <AlertTriangle size={12} /> Gaps
                                                                                </strong>
                                                                                <ul>
                                                                                    {pr.gaps.map((g, k) => (
                                                                                        <li key={k}>{g}</li>
                                                                                    ))}
                                                                                </ul>
                                                                            </div>
                                                                        )}
                                                                        <p className="breakdown-explanation">
                                                                            {pr.explanation}
                                                                        </p>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    </td>
                                                </tr>
                                            )}
                                        </>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="alert alert-warning mt-md">
                            No suitable candidates found.
                        </div>
                    )}

                    {/* Notes */}
                    {ranking.notes && (
                        <div className="cv-ranking-notes mt-md">
                            <CheckCircle size={14} /> {ranking.notes}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
