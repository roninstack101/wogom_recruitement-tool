import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogIn, UserPlus, BriefcaseBusiness, Mail, Lock, User, ChevronDown } from 'lucide-react';
import * as api from '../services/api';
import './LoginPage.css';

export default function LoginPage() {
    const navigate = useNavigate();
    const [isRegister, setIsRegister] = useState(false);
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [role, setRole] = useState('team_lead');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    async function handleSubmit(e) {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            if (isRegister) {
                await api.register(name, email, password, role);
            }
            const data = await api.login(email, password);
            const userRole = data.user?.role;
            if (userRole === 'hr') navigate('/hr');
            else navigate('/team-lead');
        } catch (err) {
            setError(err.message || 'Something went wrong');
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="login-page">
            <div className="login-card">
                <div className="login-header">
                    <BriefcaseBusiness size={36} className="login-logo" />
                    <h1>WOGOM</h1>
                    <p>Recruitment AI Portal</p>
                </div>

                <div className="login-tabs">
                    <button
                        className={`login-tab ${!isRegister ? 'active' : ''}`}
                        onClick={() => setIsRegister(false)}
                    >
                        <LogIn size={16} /> Sign In
                    </button>
                    <button
                        className={`login-tab ${isRegister ? 'active' : ''}`}
                        onClick={() => setIsRegister(true)}
                    >
                        <UserPlus size={16} /> Register
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="login-form">
                    {isRegister && (
                        <div className="form-group">
                            <User size={16} className="form-icon" />
                            <input
                                type="text"
                                placeholder="Full name"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                required
                            />
                        </div>
                    )}

                    <div className="form-group">
                        <Mail size={16} className="form-icon" />
                        <input
                            type="email"
                            placeholder="Email address"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                    </div>

                    <div className="form-group">
                        <Lock size={16} className="form-icon" />
                        <input
                            type="password"
                            placeholder="Password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>

                    {isRegister && (
                        <div className="form-group select-group">
                            <BriefcaseBusiness size={16} className="form-icon" />
                            <select value={role} onChange={(e) => setRole(e.target.value)}>
                                <option value="team_lead">Team Lead</option>
                                <option value="hr">HR</option>
                            </select>
                            <ChevronDown size={16} className="select-arrow" />
                        </div>
                    )}

                    {error && (
                        <div className="login-error">
                            {error.includes('\n') ? (
                                <ul className="login-error-list">
                                    {error.split('\n').map((msg, i) => (
                                        <li key={i}>{msg}</li>
                                    ))}
                                </ul>
                            ) : error}
                        </div>
                    )}

                    <button type="submit" className="login-submit" disabled={loading}>
                        {loading ? 'Please wait…' : isRegister ? 'Create Account' : 'Sign In'}
                    </button>
                </form>
            </div>
        </div>
    );
}
