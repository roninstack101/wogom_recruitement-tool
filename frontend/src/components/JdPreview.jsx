import ReactMarkdown from 'react-markdown';
import './JdPreview.css';

export default function JdPreview({ markdown }) {
    if (!markdown) return null;

    return (
        <div className="jd-preview card">
            <ReactMarkdown>{markdown}</ReactMarkdown>
        </div>
    );
}
