import { useRef, useState } from 'react';
import { Upload, FileText, X } from 'lucide-react';
import './FileUpload.css';

export default function FileUpload({
    label,
    accept = '.pdf,.docx,.txt',
    onFile,
    id,
}) {
    const inputRef = useRef(null);
    const [file, setFile] = useState(null);
    const [dragActive, setDragActive] = useState(false);

    const handleFile = (f) => {
        setFile(f);
        onFile(f);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setDragActive(false);
        if (e.dataTransfer.files?.[0]) {
            handleFile(e.dataTransfer.files[0]);
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        setDragActive(true);
    };

    const handleDragLeave = () => setDragActive(false);

    const handleRemove = () => {
        setFile(null);
        onFile(null);
        if (inputRef.current) inputRef.current.value = '';
    };

    return (
        <div className="file-upload-wrapper">
            {label && <label className="label">{label}</label>}

            <div
                className={`file-upload-zone ${dragActive ? 'drag-active' : ''} ${file ? 'has-file' : ''}`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => !file && inputRef.current?.click()}
                id={id}
            >
                <input
                    ref={inputRef}
                    type="file"
                    accept={accept}
                    className="file-input-hidden"
                    onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
                />

                {file ? (
                    <div className="file-selected">
                        <FileText size={20} className="file-icon" />
                        <span className="file-name">{file.name}</span>
                        <button
                            className="file-remove"
                            onClick={(e) => {
                                e.stopPropagation();
                                handleRemove();
                            }}
                            aria-label="Remove file"
                        >
                            <X size={16} />
                        </button>
                    </div>
                ) : (
                    <div className="file-placeholder">
                        <Upload size={28} className="upload-icon" />
                        <p className="upload-text">
                            Drag & drop or <span className="upload-link">browse</span>
                        </p>
                        <p className="upload-hint">{accept.replace(/\./g, '').toUpperCase()}</p>
                    </div>
                )}
            </div>
        </div>
    );
}
