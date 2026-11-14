import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  FolderOpen,
  Upload,
  FileText,
  Search,
  Trash2,
  Edit3,
  RefreshCw,
  Sparkles,
  MessageSquare,
  CheckSquare,
  Eye,
  BookOpen,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';

export const SourcesPage: React.FC = () => {
  const { addToast } = useApp();
  const [searchParams] = useSearchParams();

  const [sources, setSources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  // Upload & Paste Modal States
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadMode, setUploadMode] = useState<'file' | 'text'>('file');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [customTitle, setCustomTitle] = useState('');
  const [textContent, setTextContent] = useState('');
  const [uploading, setUploading] = useState(false);

  // Source Preview & Citation Inspector
  const [previewSource, setPreviewSource] = useState<any | null>(null);
  const [highlightedPage, setHighlightedPage] = useState<number | null>(null);

  // Rename & Delete Modals
  const [renamingSource, setRenamingSource] = useState<any | null>(null);
  const [renameTitle, setRenameTitle] = useState('');
  const [deletingSource, setDeletingSource] = useState<any | null>(null);

  // Multi-source Selection & Grounded Q&A
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [qaResult, setQaResult] = useState<any | null>(null);

  const fetchSources = async () => {
    setLoading(true);
    try {
      const res = await apiRequest<{ sources: any[] }>(
        `/api/sources?search=${encodeURIComponent(searchQuery)}&status_filter=${statusFilter}`
      );
      setSources(res.sources || []);
    } catch (err: any) {
      addToast(err.message || 'Failed to load sources.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSources();
  }, [searchQuery, statusFilter]);

  useEffect(() => {
    if (searchParams.get('upload') === '1') {
      setShowUploadModal(true);
    }
    const openId = searchParams.get('open');
    if (openId) {
      openSourcePreview(openId);
    }
  }, [searchParams]);

  const openSourcePreview = async (sourceId: string, pageNum?: number) => {
    try {
      const res = await apiRequest<{ source: any }>(`/api/sources/${sourceId}`);
      setPreviewSource(res.source);
      setHighlightedPage(pageNum || null);
    } catch (err: any) {
      addToast(err.message || 'Could not open source document.', 'error');
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploading(true);
    try {
      if (uploadMode === 'file') {
        if (!selectedFile) {
          addToast('Please choose a file to upload.', 'error');
          setUploading(false);
          return;
        }
        const formData = new FormData();
        formData.append('file', selectedFile);
        if (customTitle.trim()) {
          formData.append('title', customTitle.trim());
        }
        const res = await apiRequest<{ source: any }>('/api/sources/upload', {
          method: 'POST',
          body: formData,
        });
        addToast(
          res.source.status === 'ready'
            ? `Uploaded and indexed "${res.source.title}" (${res.source.word_count} words).`
            : `Uploaded "${res.source.title}" with status: ${res.source.status}`,
          res.source.status === 'ready' ? 'success' : 'error'
        );
      } else {
        if (!customTitle.trim() || textContent.trim().length < 20) {
          addToast('Please provide a title and at least 20 characters of study text.', 'error');
          setUploading(false);
          return;
        }
        const res = await apiRequest<{ source: any }>('/api/sources/text', {
          method: 'POST',
          body: JSON.stringify({
            title: customTitle.trim(),
            content: textContent,
            file_type: '.md',
          }),
        });
        addToast(`Saved and indexed "${res.source.title}" (${res.source.word_count} words).`, 'success');
      }
      setShowUploadModal(false);
      setSelectedFile(null);
      setCustomTitle('');
      setTextContent('');
      fetchSources();
    } catch (err: any) {
      addToast(err.message || 'Upload failed.', 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleRenameSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!renamingSource || !renameTitle.trim()) return;
    try {
      await apiRequest(`/api/sources/${renamingSource.id}`, {
        method: 'PUT',
        body: JSON.stringify({ title: renameTitle.trim() }),
      });
      addToast('Source renamed.', 'success');
      setRenamingSource(null);
      fetchSources();
    } catch (err: any) {
      addToast(err.message || 'Rename failed.', 'error');
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deletingSource) return;
    try {
      await apiRequest(`/api/sources/${deletingSource.id}`, { method: 'DELETE' });
      addToast(`Deleted source "${deletingSource.title}".`, 'info');
      setSelectedSourceIds((prev) => prev.filter((id) => id !== deletingSource.id));
      if (previewSource?.id === deletingSource.id) setPreviewSource(null);
      setDeletingSource(null);
      fetchSources();
    } catch (err: any) {
      addToast(err.message || 'Delete failed.', 'error');
    }
  };

  const handleRetrySource = async (sourceId: string) => {
    try {
      const res = await apiRequest<{ source: any }>(`/api/sources/${sourceId}/retry`, {
        method: 'POST',
      });
      addToast(`Reprocessed source: status is ${res.source.status}.`, 'info');
      fetchSources();
    } catch (err: any) {
      addToast(err.message || 'Retry failed.', 'error');
    }
  };

  const toggleSelectSource = (id: string) => {
    setSelectedSourceIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleAskGroundedQuestion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setAsking(true);
    try {
      const res = await apiRequest('/api/sources/ask', {
        method: 'POST',
        body: JSON.stringify({
          question: question.trim(),
          source_ids: selectedSourceIds.length > 0 ? selectedSourceIds : undefined,
        }),
      });
      setQaResult(res);
    } catch (err: any) {
      addToast(err.message || 'Grounded query failed.', 'error');
    } finally {
      setAsking(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div
        className="card card-elevated"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        <div>
          <span className="badge badge-blue" style={{ marginBottom: '6px' }}>
            Source Library
          </span>
          <h1 style={{ fontSize: '1.6rem' }}>My Study Sources</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
            Upload PDFs, DOCX, PPTX, Markdown, or text documents. Extract readable text, and ask
            grounded questions with navigable citations.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setShowUploadModal(true)}
          >
            <Upload size={16} />
            <span>Add / Upload Source</span>
          </button>
        </div>
      </div>

      {/* Grounded Question Answering & Citation Explorer */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
          <MessageSquare size={18} color="var(--accent-blue)" />
          <h2 style={{ fontSize: '1.15rem' }}>
            Source-Grounded Question Answering (with Verifiable Citations)
          </h2>
        </div>
        <form onSubmit={handleAskGroundedQuestion} style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <input
            type="text"
            className="form-input"
            style={{ flex: 1, minWidth: 260 }}
            placeholder={
              selectedSourceIds.length > 0
                ? `Ask a question grounded in your ${selectedSourceIds.length} selected source(s)...`
                : 'Ask a question across all your ready study sources...'
            }
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" disabled={asking}>
            <Sparkles size={15} />
            <span>{asking ? 'Retrieving Passages...' : 'Ask Sources'}</span>
          </button>
        </form>

        {qaResult && (
          <div
            style={{
              marginTop: '16px',
              padding: '18px',
              borderRadius: '12px',
              background: 'var(--bg-charcoal)',
              border: '1px solid var(--border-default)',
            }}
          >
            <div style={{ marginBottom: '12px', whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
              {qaResult.answer}
            </div>
            {qaResult.citations && qaResult.citations.length > 0 && (
              <div>
                <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '8px' }}>
                  VERIFIED SOURCE CITATIONS (CLICK TO INSPECT EXACT PASSAGE):
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {qaResult.citations.map((cit: any) => (
                    <button
                      key={cit.citation_number}
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => openSourcePreview(cit.source_id, cit.page_number)}
                    >
                      <BookOpen size={13} />
                      <span>
                        [#{cit.citation_number}] {cit.source_title} — Page {cit.page_number} (
                        {cit.section_title})
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Filters & Source List */}
      <div className="card">
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '18px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, maxWidth: 420 }}>
            <Search size={16} color="var(--text-muted)" />
            <input
              type="search"
              className="form-input"
              placeholder="Filter sources by title, filename, or content..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <select
              className="form-select"
              style={{ width: 'auto' }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter sources by status"
            >
              <option value="all">All Statuses</option>
              <option value="ready">Ready</option>
              <option value="processing">Processing</option>
              <option value="error">Error</option>
            </select>
          </div>
        </div>

        {loading ? (
          <p style={{ color: 'var(--text-muted)', padding: '20px 0' }}>Loading sources...</p>
        ) : sources.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <FolderOpen size={40} color="var(--text-subtle)" style={{ marginBottom: '12px' }} />
            <h3 style={{ marginBottom: '6px' }}>Your Source Library is Empty</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '18px' }}>
              Upload a PDF, DOCX, PPTX, Markdown, or text study guide to extract passages and ask
              source-grounded questions.
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setShowUploadModal(true)}
            >
              <Upload size={16} />
              <span>Upload Your First Document</span>
            </button>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: 42 }}>Select</th>
                  <th>Document Title & File</th>
                  <th>Format & Size</th>
                  <th>Extracted Stats</th>
                  <th>Status</th>
                  <th>Uploaded</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((src) => {
                  const isSelected = selectedSourceIds.includes(src.id);
                  return (
                    <tr key={src.id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectSource(src.id)}
                          disabled={src.status !== 'ready'}
                          aria-label={`Select ${src.title}`}
                        />
                      </td>
                      <td>
                        <div
                          style={{ fontWeight: 600, color: 'var(--text-primary)', cursor: 'pointer' }}
                          onClick={() => openSourcePreview(src.id)}
                        >
                          {src.title}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {src.original_filename}
                        </div>
                        {src.error_message && (
                          <div style={{ fontSize: '0.75rem', color: 'var(--status-danger)', marginTop: 4 }}>
                            {src.error_message}
                          </div>
                        )}
                      </td>
                      <td>
                        <span className="badge badge-indigo">{src.file_type.toUpperCase()}</span>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
                          {formatBytes(src.file_size)}
                        </div>
                      </td>
                      <td>
                        <div style={{ fontSize: '0.82rem' }}>{src.word_count} words</div>
                        <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                          {src.page_count} page(s) / section(s)
                        </div>
                      </td>
                      <td>
                        <span
                          className={`badge ${
                            src.status === 'ready'
                              ? 'badge-success'
                              : src.status === 'error'
                              ? 'badge-danger'
                              : 'badge-warning'
                          }`}
                        >
                          {src.status}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {new Date(src.created_at).toLocaleDateString()}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: '6px' }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => openSourcePreview(src.id)}
                            title="Preview extracted content"
                          >
                            <Eye size={14} />
                            <span>Preview</span>
                          </button>
                          {src.status === 'error' && (
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleRetrySource(src.id)}
                              title="Retry extraction"
                            >
                              <RefreshCw size={14} />
                            </button>
                          )}
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setRenamingSource(src);
                              setRenameTitle(src.title);
                            }}
                            title="Rename source"
                            aria-label={`Rename ${src.title}`}
                          >
                            <Edit3 size={14} />
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => setDeletingSource(src)}
                            title="Delete source"
                            aria-label={`Delete ${src.title}`}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Source Extracted Content & Chunk Preview Drawer/Modal */}
      {previewSource && (
        <div className="modal-backdrop" onClick={() => setPreviewSource(null)}>
          <div
            className="modal-panel"
            style={{ maxWidth: 820 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
              <div>
                <span className="badge badge-success" style={{ marginBottom: 6 }}>
                  {previewSource.status.toUpperCase()} • {previewSource.word_count} words •{' '}
                  {previewSource.page_count} sections
                </span>
                <h2 style={{ fontSize: '1.35rem' }}>{previewSource.title}</h2>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  File: {previewSource.original_filename}
                </div>
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setPreviewSource(null)}
              >
                Close
              </button>
            </div>

            {previewSource.chunks && previewSource.chunks.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '60vh', overflowY: 'auto' }}>
                {previewSource.chunks.map((ch: any) => {
                  const isHighlighted = highlightedPage === ch.page_number;
                  return (
                    <div
                      key={ch.id}
                      style={{
                        padding: '14px',
                        borderRadius: '10px',
                        background: isHighlighted
                          ? 'rgba(56, 189, 248, 0.14)'
                          : 'var(--bg-charcoal)',
                        border: isHighlighted
                          ? '1px solid var(--accent-blue)'
                          : '1px solid var(--border-subtle)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.78rem', color: 'var(--accent-blue)' }}>
                        <strong>
                          Page / Section {ch.page_number}: {ch.section_title}
                        </strong>
                        <span>Passage #{ch.chunk_index + 1}</span>
                      </div>
                      <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
                        {ch.content}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="code-block" style={{ maxHeight: '55vh', overflowY: 'auto' }}>
                {previewSource.extracted_text || previewSource.error_message || 'No text content.'}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Upload / Add Source Modal */}
      {showUploadModal && (
        <div className="modal-backdrop" onClick={() => setShowUploadModal(false)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ fontSize: '1.3rem', marginBottom: '12px' }}>Add Study Source</h2>
            <div className="tabs-bar" style={{ marginBottom: '18px' }}>
              <button
                type="button"
                className={`tab-btn ${uploadMode === 'file' ? 'active' : ''}`}
                style={{ flex: 1, justifyContent: 'center' }}
                onClick={() => setUploadMode('file')}
              >
                Upload Document File
              </button>
              <button
                type="button"
                className={`tab-btn ${uploadMode === 'text' ? 'active' : ''}`}
                style={{ flex: 1, justifyContent: 'center' }}
                onClick={() => setUploadMode('text')}
              >
                Paste Study Notes / Markdown
              </button>
            </div>

            <form onSubmit={handleUploadSubmit}>
              <div className="form-group">
                <label className="form-label" htmlFor="source-title-input">
                  Document Title {uploadMode === 'file' ? '(Optional)' : '(Required)'}
                </label>
                <input
                  id="source-title-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g., Operating Systems Lecture Notes — Virtual Memory"
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  required={uploadMode === 'text'}
                />
              </div>

              {uploadMode === 'file' ? (
                <div className="form-group">
                  <label className="form-label" htmlFor="source-file-input">
                    Select Document (.pdf, .md, .txt, .csv, .json, .py, .js, .ts, .html)
                  </label>
                  <input
                    id="source-file-input"
                    type="file"
                    className="form-input"
                    accept=".pdf,.txt,.md,.markdown,.csv,.json,.py,.js,.ts,.tsx,.html"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    required
                  />
                  <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                    Note: Text-searchable PDFs and text documents are extracted and indexed
                    immediately. Scanned image-only PDFs without a text layer will display an OCR
                    limitation notice.
                  </span>
                </div>
              ) : (
                <div className="form-group">
                  <label className="form-label" htmlFor="source-text-content">
                    Study Material Content (Markdown or Plain Text)
                  </label>
                  <textarea
                    id="source-text-content"
                    className="form-textarea"
                    style={{ minHeight: 200 }}
                    placeholder="# Topic Heading&#10;Paste lecture notes, textbook excerpts, or technical documentation here..."
                    value={textContent}
                    onChange={(e) => setTextContent(e.target.value)}
                    required
                  />
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '18px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowUploadModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={uploading}>
                  {uploading ? 'Processing & Indexing...' : 'Extract & Save Source'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Rename Modal */}
      {renamingSource && (
        <div className="modal-backdrop" onClick={() => setRenamingSource(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '12px' }}>Rename Source Document</h3>
            <form onSubmit={handleRenameSubmit}>
              <div className="form-group">
                <label className="form-label" htmlFor="rename-source-input">
                  New Title
                </label>
                <input
                  id="rename-source-input"
                  type="text"
                  className="form-input"
                  value={renameTitle}
                  onChange={(e) => setRenameTitle(e.target.value)}
                  required
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setRenamingSource(null)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Title
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingSource && (
        <div className="modal-backdrop" onClick={() => setDeletingSource(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '8px' }}>Delete Source Document?</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '18px' }}>
              Are you sure you want to permanently delete <strong>"{deletingSource.title}"</strong>{' '}
              and its indexed passages?
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setDeletingSource(null)}
              >
                Cancel
              </button>
              <button type="button" className="btn btn-danger" onClick={handleDeleteConfirm}>
                Delete Source
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

