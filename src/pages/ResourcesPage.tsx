import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BookMarked,
  FileText,
  Video,
  Plus,
  Trash2,
  Edit3,
  Search,
  ExternalLink,
  Save,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';

export const ResourcesPage: React.FC = () => {
  const { addToast } = useApp();
  const navigate = useNavigate();

  const [activeCategory, setActiveCategory] = useState<
    'notes' | 'tutorials' | 'readings'
  >('notes');
  const [searchQuery, setSearchQuery] = useState('');
  const [data, setData] = useState<any>({
    notes: [],
    tutorials: [],
    readings: [],
  });
  const [loading, setLoading] = useState(true);

  // Standalone / Custom Note Modal
  const [editingNote, setEditingNote] = useState<any | null>(null);
  const [noteTitle, setNoteTitle] = useState('');
  const [noteContent, setNoteContent] = useState('');

  const loadResources = async () => {
    setLoading(true);
    try {
      const res = await apiRequest(
        `/api/resources?search=${encodeURIComponent(searchQuery.trim())}`
      );
      setData(res);
    } catch (err: any) {
      addToast(err.message || 'Failed to load learning resources.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadResources();
  }, [searchQuery]);

  const handleSaveNoteModal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteTitle.trim()) return;
    try {
      if (editingNote?.id) {
        await apiRequest(`/api/notes/${editingNote.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            title: noteTitle.trim(),
            content: noteContent,
          }),
        });
        addToast('Updated personal note.', 'success');
      } else {
        await apiRequest('/api/notes', {
          method: 'POST',
          body: JSON.stringify({
            title: noteTitle.trim(),
            content: noteContent,
          }),
        });
        addToast('Created personal note.', 'success');
      }
      setEditingNote(null);
      loadResources();
    } catch (err: any) {
      addToast(err.message || 'Failed to save note.', 'error');
    }
  };

  const handleDeleteNote = async (noteId: string) => {
    try {
      await apiRequest(`/api/notes/${noteId}`, { method: 'DELETE' });
      addToast('Deleted personal note.', 'info');
      loadResources();
    } catch (err: any) {
      addToast(err.message || 'Delete failed.', 'error');
    }
  };

  const handleDeleteTutorial = async (tutId: string) => {
    try {
      await apiRequest(`/api/tutorials/${tutId}`, { method: 'DELETE' });
      addToast('Removed tutorial link.', 'info');
      loadResources();
    } catch (err: any) {
      addToast(err.message || 'Delete failed.', 'error');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
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
          <span className="badge badge-indigo" style={{ marginBottom: '6px' }}>
            Unified Resource Hub
          </span>
          <h1 style={{ fontSize: '1.65rem' }}>My Learning Resources</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
            Manage all your personal notes, saved video tutorials, and generated topic reading guides
            in one place.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            setEditingNote({});
            setNoteTitle('');
            setNoteContent('');
          }}
        >
          <Plus size={16} />
          <span>Create Personal Note</span>
        </button>
      </div>

      {/* Category Tabs & Search */}
      <div className="card">
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '12px',
            marginBottom: '20px',
          }}
        >
          <div className="tabs-bar">
            <button
              type="button"
              className={`tab-btn ${activeCategory === 'notes' ? 'active' : ''}`}
              onClick={() => setActiveCategory('notes')}
            >
              <FileText size={15} />
              <span>Personal Notes ({data.notes?.length || 0})</span>
            </button>
            <button
              type="button"
              className={`tab-btn ${activeCategory === 'tutorials' ? 'active' : ''}`}
              onClick={() => setActiveCategory('tutorials')}
            >
              <Video size={15} />
              <span>Tutorials ({data.tutorials?.length || 0})</span>
            </button>
            <button
              type="button"
              className={`tab-btn ${activeCategory === 'readings' ? 'active' : ''}`}
              onClick={() => setActiveCategory('readings')}
            >
              <BookMarked size={15} />
              <span>Reading Materials ({data.readings?.length || 0})</span>
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 260 }}>
            <Search size={16} color="var(--text-muted)" />
            <input
              type="search"
              className="form-input"
              placeholder="Search resources..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {loading ? (
          <p style={{ color: 'var(--text-muted)' }}>Loading resources...</p>
        ) : activeCategory === 'notes' ? (
          (data.notes || []).length === 0 ? (
            <p style={{ color: 'var(--text-muted)', padding: '20px 0' }}>
              No personal notes found. Click "Create Personal Note" or write notes inside any Topic
              Reading Workspace.
            </p>
          ) : (
            <div className="grid-2">
              {data.notes.map((n: any) => (
                <div
                  key={n.id}
                  style={{
                    padding: '16px',
                    borderRadius: '12px',
                    background: 'var(--bg-charcoal)',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '12px',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <span className="badge badge-blue">
                        {n.topic_title || 'General Study Note'}
                      </span>
                      <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                        {new Date(n.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                    <h3 style={{ fontSize: '1.08rem', marginBottom: '6px' }}>{n.title}</h3>
                    <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
                      {n.content.slice(0, 260)}
                      {n.content.length > 260 ? '...' : ''}
                    </p>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                    {n.roadmap_id && n.topic_id && (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() =>
                          navigate(`/roadmaps/${n.roadmap_id}/topics/${n.topic_id}?tab=reading`)
                        }
                      >
                        Open Topic
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        setEditingNote(n);
                        setNoteTitle(n.title);
                        setNoteContent(n.content);
                      }}
                    >
                      <Edit3 size={14} />
                      <span>Edit</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
                      onClick={() => handleDeleteNote(n.id)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : activeCategory === 'tutorials' ? (
          (data.tutorials || []).length === 0 ? (
            <p style={{ color: 'var(--text-muted)', padding: '20px 0' }}>
              No saved tutorials yet. Generate a roadmap or add custom YouTube links in any topic.
            </p>
          ) : (
            <div className="grid-2">
              {data.tutorials.map((tut: any) => (
                <div
                  key={tut.id}
                  style={{
                    padding: '14px',
                    borderRadius: '12px',
                    background: 'var(--bg-charcoal)',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    gap: '14px',
                    alignItems: 'center',
                  }}
                >
                  {tut.thumbnail_url && (
                    <img
                      src={tut.thumbnail_url}
                      alt={tut.title}
                      style={{ width: 120, height: 68, objectFit: 'cover', borderRadius: '8px' }}
                    />
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <span
                      className={
                        tut.is_user_added || tut.source_badge === 'CUSTOMIZED'
                          ? 'badge-customized'
                          : 'badge-original'
                      }
                      style={{ marginBottom: 4 }}
                    >
                      {tut.is_user_added || tut.source_badge === 'CUSTOMIZED'
                        ? 'CUSTOMIZED'
                        : 'ORIGINAL'}
                    </span>
                    <div style={{ fontWeight: 700, fontSize: '0.92rem' }}>{tut.title}</div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                      Topic: {tut.topic_title} • {tut.channel || tut.channel_name}
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <a
                        href={tut.url || tut.video_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-primary btn-sm"
                      >
                        <ExternalLink size={13} />
                        <span>Watch Tutorial</span>
                      </a>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() =>
                          navigate(`/roadmaps/${tut.roadmap_id}?expand=${tut.topic_id}&tab=tutorial`)
                        }
                      >
                        Open on Roadmap
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDeleteTutorial(tut.id)}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          (data.readings || []).length === 0 ? (
            <p style={{ color: 'var(--text-muted)', padding: '20px 0' }}>
              No topic reading materials generated yet.
            </p>
          ) : (
            <div className="grid-2">
              {data.readings.map((rd: any) => (
                <div
                  key={rd.id}
                  style={{
                    padding: '16px',
                    borderRadius: '12px',
                    background: 'var(--bg-charcoal)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <span className="badge badge-indigo">{rd.roadmap_title}</span>
                    <span
                      className={
                        rd.has_custom_reading || rd.source_badge === 'CUSTOMIZED'
                          ? 'badge-customized'
                          : 'badge-original'
                      }
                    >
                      {rd.has_custom_reading || rd.source_badge === 'CUSTOMIZED'
                        ? 'CUSTOMIZED'
                        : 'ORIGINAL'}
                    </span>
                  </div>
                  <h3 style={{ fontSize: '1.08rem', marginBottom: '6px' }}>
                    {rd.has_custom_reading && rd.custom_title ? rd.custom_title : rd.title}
                  </h3>
                  <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                    {(rd.has_custom_reading && rd.custom_markdown
                      ? rd.custom_markdown
                      : rd.overview || ''
                    ).slice(0, 180)}
                    ...
                  </p>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={() =>
                      navigate(`/roadmaps/${rd.roadmap_id}?expand=${rd.topic_id}&tab=reading`)
                    }
                  >
                    Open Reading on Roadmap
                  </button>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* Note Create/Edit Modal */}
      {editingNote !== null && (
        <div className="modal-backdrop" onClick={() => setEditingNote(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '14px' }}>
              {editingNote.id ? 'Edit Personal Note' : 'Create Personal Note'}
            </h3>
            <form onSubmit={handleSaveNoteModal}>
              <div className="form-group">
                <label className="form-label">Note Title</label>
                <input
                  type="text"
                  className="form-input"
                  value={noteTitle}
                  onChange={(e) => setNoteTitle(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Note Content</label>
                <textarea
                  className="form-textarea"
                  style={{ minHeight: 180 }}
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setEditingNote(null)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  <Save size={15} />
                  <span>Save Note</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

