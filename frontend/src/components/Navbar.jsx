import { Link, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { useState } from 'react';
import './Navbar.css';

export default function Navbar() {
    const location = useLocation();
    const [mobileOpen, setMobileOpen] = useState(false);

    const links = [
        { to: '/', label: 'Home' },
        { to: '/recruiter', label: 'JD Generator' },
        { to: '/candidate', label: 'Candidates' },
    ];

    return (
        <nav className="navbar">
            <div className="navbar-inner">
                <Link to="/" className="navbar-logo">
                    <span className="navbar-logo-icon">🏢</span>
                    <span className="navbar-logo-text">WOGOM</span>
                </Link>

                <div className={`navbar-links ${mobileOpen ? 'open' : ''}`}>
                    {links.map((link) => (
                        <Link
                            key={link.to}
                            to={link.to}
                            className={`navbar-link ${location.pathname === link.to ? 'active' : ''}`}
                            onClick={() => setMobileOpen(false)}
                        >
                            {link.label}
                        </Link>
                    ))}
                </div>

                <button
                    className="navbar-toggle"
                    onClick={() => setMobileOpen(!mobileOpen)}
                    aria-label="Toggle navigation"
                >
                    {mobileOpen ? <X size={22} /> : <Menu size={22} />}
                </button>
            </div>
        </nav>
    );
}
