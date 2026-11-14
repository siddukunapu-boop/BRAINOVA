import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Check,
  Copy,
  Download,
  Edit3,
  Image as ImageIcon,
  Maximize2,
  MessageSquare,
  Plus,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  Square,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  X,
} from 'lucide-react';
import { apiRequest, getStoredToken, resolveApiUrl } from '../services/api';
import { BrainovaLogo } from './BrainovaLogo';
import { MentorMarkdownRenderer } from './MentorMarkdownRenderer';

export interface MentorImageAttachment {
  id: string;
  url: string;
  prompt: string;
  mime_type: string;
  illustrative_only?: boolean;
}

export interface MentorMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  provider?: string;
  feedback?: 'up' | 'down' | null;
  image?: MentorImageAttachment;
  timestamp?: string;
}

const MentorImageCard: React.FC<{
  image: MentorImageAttachment;
  onRegenerate: (prompt: string) => void;
  disabled: boolean;
}> = ({ image, onRegenerate, disabled }) => {
  const [blobUrl, setBlobUrl] = useState<string>('');
  const [imgError, setImgError] = useState<string>('');
  const [expanded, setExpanded] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl = '';
    const load = async () => {
      try {
        const token = getStoredToken();
        const resp = await fetch(resolveApiUrl(image.url), {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!resp.ok) {
          throw new Error(`Failed to load illustration (${resp.status})`);
        }
        const blob = await resp.blob();
        objectUrl = URL.createObjectURL(blob);
        if (active) setBlobUrl(objectUrl);
      } catch (err: any) {
        if (active) setImgError(err?.message || 'Unable to load generated image.');
      }
    };
    load();
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [image.url]);

  const handleCopyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(image.prompt);
      setCopiedPrompt(true);
      window.setTimeout(() => setCopiedPrompt(false), 1800);
    } catch {
      // ignore
    }
  };

  const handleDownload = () => {
    if (!blobUrl) return;
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = `brainova-illustration-${image.id}.png`;
    a.click();
  };

  return (
    <>
      <div className="bnv-mentor-image-card">
        <div className="bnv-mermaid-toolbar">
          <span className="bnv-mermaid-badge">AI Educational Illustration (Illustrative Only)</span>
          <div className="bnv-mermaid-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={handleCopyPrompt}>
              {copiedPrompt ? <Check size={13} /> : <Copy size={13} />}
              <span>{copiedPrompt ? 'Copied' : 'Prompt'}</span>
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => onRegenerate(image.prompt)}
              disabled={disabled}
            >
              <RefreshCw size={13} />
              <span>Regenerate</span>
            </button>
            {blobUrl && (
              <>
                <button type="button" className="btn btn-ghost btn-sm" onClick={handleDownload}>
                  <Download size={13} />
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setExpanded(true)}>
                  <Maximize2 size={13} />
                </button>
              </>
            )}
          </div>
        </div>
        <div className="bnv-mentor-image-body">
          {imgError ? (
            <p className="bnv-mermaid-error">{imgError}</p>
          ) : blobUrl ? (
            <img src={blobUrl} alt={image.prompt} className="bnv-mentor-image-img" />
          ) : (
            <span className="bnv-mentor-typing">Loading illustration…</span>
          )}
        </div>
      </div>

      {expanded && blobUrl && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={() => setExpanded(false)}>
          <div className="bnv-mermaid-modal" onClick={(e) => e.stopPropagation()}>
            <div className="bnv-mermaid-toolbar">
              <span className="bnv-mermaid-badge">AI Educational Illustration</span>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setExpanded(false)}>
                <X size={14} />
                <span>Close</span>
              </button>
            </div>
            <div className="bnv-mermaid-modal-body">
              <img src={blobUrl} alt={image.prompt} className="bnv-mentor-image-img-full" />
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export interface MentorConversationSummary {
  id: string;
  title: string;
  message_count: number;
  last_preview: string;
  created_at: string;
  updated_at: string;
}

const TOPIC_CATEGORIES = [
  'Programming & DSA',
  'System Design & Diagrams',
  'Math & Core CS',
  'Career & Writing',
];

const STARTER_PROMPTS = [
  {
    category: 'Programming & DSA',
    title: 'QuickSort & Partition Walkthrough',
    prompt:
      'Explain QuickSort with clean Python code, dry-run example input/output, time & space complexity, edge cases, and a Mermaid flowchart.',
  },
  {
    category: 'System Design & Diagrams',
    title: 'URL Shortener Architecture',
    prompt:
      'Design a scalable URL Shortener service. Include a Mermaid architecture diagram, database ER diagram, and API trade-offs.',
  },
  {
    category: 'Math & Core CS',
    title: 'ACID & Database Indexing',
    prompt:
      'Explain ACID isolation levels and B-Tree indexing trade-offs with a comparison table and clear SQL examples.',
  },
  {
    category: 'Math & Core CS',
    title: 'Bayes Theorem Derivation',
    prompt:
      'Explain Bayes Theorem step-by-step with mathematical equations and a practical machine learning example.',
  },
  {
    category: 'Career & Writing',
    title: 'Fresher SWE Resume & Interview Prep',
    prompt:
      'Review how a fresher software engineer should structure a backend project bullet on a resume using measurable impact.',
  },
  {
    category: 'Programming & DSA',
    title: 'Debug Async Race Condition',
    prompt:
      'Explain how stale React fetch responses cause race conditions and show how to fix them with AbortController in TypeScript.',
  },
];

export const CareerMentorPanel: React.FC = () => {
  const [conversations, setConversations] = useState<MentorConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [activeTitle, setActiveTitle] = useState<string>('New Mentor Conversation');
  const [messages, setMessages] = useState<MentorMessage[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [composerText, setComposerText] = useState('');

  const [loadingList, setLoadingList] = useState(true);
  const [loadingConv, setLoadingConv] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [streamingProvider, setStreamingProvider] = useState('');
  const [generatingImage, setGeneratingImage] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [needsKeyHint, setNeedsKeyHint] = useState(false);

  const [editingConvId, setEditingConvId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const activeConvRef = useRef<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    activeConvRef.current = activeConvId;
  }, [activeConvId]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const fetchConversations = useCallback(async (q = '') => {
    setLoadingList(true);
    try {
      const qs = q.trim() ? `?q=${encodeURIComponent(q.trim())}` : '';
      const res = await apiRequest<{ conversations: MentorConversationSummary[] }>(
        `/api/mentor/conversations${qs}`
      );
      setConversations(res.conversations || []);
    } catch (err: any) {
      setErrorMsg(err.message || 'Unable to load mentor conversations.');
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchConversations(searchQuery);
    }, 180);
    return () => window.clearTimeout(timer);
  }, [searchQuery, fetchConversations]);

  const openConversation = async (convId: string) => {
    abortRef.current?.abort();
    setStreaming(false);
    setStreamingText('');
    setErrorMsg('');
    setNeedsKeyHint(false);
    setLoadingConv(true);
    setActiveConvId(convId);
    try {
      const res = await apiRequest<{
        conversation: { id: string; title: string; messages: MentorMessage[] };
      }>(`/api/mentor/conversations/${convId}`);
      if (activeConvRef.current === convId) {
        setActiveTitle(res.conversation.title);
        setMessages(res.conversation.messages || []);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to open conversation.');
    } finally {
      setLoadingConv(false);
    }
  };

  const handleNewConversation = async (): Promise<string | null> => {
    abortRef.current?.abort();
    setStreaming(false);
    setStreamingText('');
    setErrorMsg('');
    setNeedsKeyHint(false);
    try {
      const res = await apiRequest<{
        conversation: { id: string; title: string; messages: MentorMessage[] };
      }>('/api/mentor/conversations', {
        method: 'POST',
        body: JSON.stringify({ title: 'New Mentor Conversation' }),
      });
      const conv = res.conversation;
      setActiveConvId(conv.id);
      setActiveTitle(conv.title);
      setMessages([]);
      await fetchConversations(searchQuery);
      return conv.id;
    } catch (err: any) {
      setErrorMsg(err.message || 'Unable to create conversation.');
      return null;
    }
  };

  const handleRenameSubmit = async (convId: string) => {
    const clean = editingTitle.trim();
    if (!clean) {
      setEditingConvId(null);
      return;
    }
    try {
      await apiRequest(`/api/mentor/conversations/${convId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: clean }),
      });
      if (activeConvId === convId) {
        setActiveTitle(clean);
      }
      setEditingConvId(null);
      await fetchConversations(searchQuery);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to rename conversation.');
    }
  };

  const handleDeleteConversation = async (convId: string) => {
    try {
      await apiRequest(`/api/mentor/conversations/${convId}`, { method: 'DELETE' });
      if (activeConvId === convId) {
        setActiveConvId(null);
        setActiveTitle('New Mentor Conversation');
        setMessages([]);
      }
      await fetchConversations(searchQuery);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to delete conversation.');
    }
  };

  const runStreamTurn = async (textToSend: string, regenerate = false) => {
    if (streaming) return;
    setErrorMsg('');
    setNeedsKeyHint(false);

    let convId = activeConvId;
    if (!convId) {
      convId = await handleNewConversation();
      if (!convId) return;
    }

    const optimisticUser: MentorMessage | null = regenerate
      ? null
      : {
          id: `temp-u-${Date.now()}`,
          role: 'user',
          content: textToSend,
        };

    setMessages((prev) => {
      const base = regenerate && prev.length > 0 && prev[prev.length - 1].role === 'assistant'
        ? prev.slice(0, -1)
        : prev;
      return optimisticUser ? [...base, optimisticUser] : base;
    });

    if (!regenerate) {
      setComposerText('');
    }

    setStreaming(true);
    setStreamingText('');
    setStreamingProvider('');

    let accumulated = '';
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const token = getStoredToken();
      const resp = await fetch(resolveApiUrl(`/api/mentor/conversations/${convId}/stream`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: textToSend, regenerate }),
        signal: controller.signal,
      });

      if (!resp.ok || !resp.body) {
        let errText = `Mentor request failed (${resp.status})`;
        try {
          const payload = await resp.json();
          if (payload?.detail) errText = String(payload.detail);
        } catch {
          // ignore
        }
        setErrorMsg(errText);
        setStreaming(false);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const rawEvt of events) {
          const dataLine = rawEvt
            .split('\n')
            .find((l) => l.startsWith('data:'));
          if (!dataLine) continue;
          const jsonStr = dataLine.slice(5).trim();
          if (!jsonStr) continue;
          try {
            const evt = JSON.parse(jsonStr);
            if (evt.type === 'meta' && evt.provider) {
              setStreamingProvider(evt.provider);
            } else if (evt.type === 'delta' && evt.text) {
              accumulated += evt.text;
              setStreamingText(accumulated);
            } else if (evt.type === 'done' && evt.message) {
              setMessages((prev) => [...prev, evt.message as MentorMessage]);
              setStreamingText('');
              if (evt.title) setActiveTitle(evt.title);
              await fetchConversations(searchQuery);
            } else if (evt.type === 'error') {
              setErrorMsg(evt.message || 'AI provider error.');
              if (evt.code === 'provider_not_configured') {
                setNeedsKeyHint(true);
              }
            }
          } catch {
            // ignore malformed SSE chunk
          }
        }
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        if (accumulated.trim()) {
          setMessages((prev) => [
            ...prev,
            {
              id: `stopped-${Date.now()}`,
              role: 'assistant',
              content: `${accumulated}\n\n*(Generation stopped)*`,
            },
          ]);
        }
      } else {
        setErrorMsg(err?.message || 'Connection interrupted while streaming response.');
      }
    } finally {
      setStreaming(false);
      setStreamingText('');
      abortRef.current = null;
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleStopGeneration = () => {
    abortRef.current?.abort();
  };

  const handleFeedback = async (msgId: string, feedback: 'up' | 'down') => {
    if (!activeConvId || msgId.startsWith('temp-') || msgId.startsWith('stopped-')) return;
    const current = messages.find((m) => m.id === msgId)?.feedback;
    const nextFeedback = current === feedback ? 'none' : feedback;
    try {
      await apiRequest(`/api/mentor/conversations/${activeConvId}/feedback`, {
        method: 'POST',
        body: JSON.stringify({ message_id: msgId, feedback: nextFeedback }),
      });
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId ? { ...m, feedback: nextFeedback === 'none' ? null : nextFeedback } : m
        )
      );
    } catch {
      // ignore non-blocking feedback error
    }
  };

  const handleCopyMessage = async (msgId: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMsgId(msgId);
      window.setTimeout(() => setCopiedMsgId(null), 1800);
    } catch {
      // ignore clipboard errors
    }
  };

  const handleGenerateIllustration = async (promptText: string) => {
    if (generatingImage || streaming) return;
    let convId = activeConvId;
    if (!convId) {
      try {
        const created = await apiRequest<{ conversation: { id: string } }>('/api/mentor/conversations', {
          method: 'POST',
          body: JSON.stringify({ title: 'AI Illustration' }),
        });
        convId = created.conversation?.id || null;
        if (convId) setActiveConvId(convId);
      } catch (err: any) {
        setErrorMsg(err?.message || 'Unable to start conversation for illustration.');
        return;
      }
      if (!convId) return;
    }
    setGeneratingImage(true);
    setErrorMsg('');
    try {
      const res = await apiRequest<{ message: MentorMessage }>(
        `/api/mentor/conversations/${convId}/image`,
        {
          method: 'POST',
          body: JSON.stringify({ prompt: promptText.slice(0, 900) }),
        }
      );
      if (res.message) {
        setMessages((prev) => [...prev, res.message]);
        await fetchConversations(searchQuery);
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Unable to generate educational illustration right now.');
    } finally {
      setGeneratingImage(false);
    }
  };

  const visiblePrompts =
    selectedCategory === 'All'
      ? STARTER_PROMPTS
      : STARTER_PROMPTS.filter((p) => p.category === selectedCategory);

  return (
    <div className="bnv-mentor-shell">
      {/* Left Conversation History Sidebar */}
      <aside className="bnv-mentor-sidebar" aria-label="AI Mentor Conversations">
        <button
          type="button"
          className="btn btn-primary bnv-mentor-new-btn"
          onClick={handleNewConversation}
        >
          <Plus size={16} />
          <span>New Conversation</span>
        </button>

        <div className="bnv-mentor-search-wrap">
          <Search size={14} className="bnv-mentor-search-icon" />
          <input
            type="search"
            className="bnv-mentor-search-input"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search mentor conversations"
          />
        </div>

        <div className="bnv-mentor-conv-list">
          {loadingList ? (
            <div className="bnv-mentor-empty-list">Loading history…</div>
          ) : conversations.length === 0 ? (
            <div className="bnv-mentor-empty-list">
              No saved conversations yet. Start a new chat or pick a prompt.
            </div>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className={`bnv-mentor-conv-item ${activeConvId === conv.id ? 'active' : ''}`}
              >
                {editingConvId === conv.id ? (
                  <div className="bnv-mentor-rename-row">
                    <input
                      type="text"
                      className="bnv-mentor-rename-input"
                      value={editingTitle}
                      onChange={(e) => setEditingTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleRenameSubmit(conv.id);
                        if (e.key === 'Escape') setEditingConvId(null);
                      }}
                      autoFocus
                    />
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => handleRenameSubmit(conv.id)}
                      aria-label="Save title"
                    >
                      <Check size={13} />
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => setEditingConvId(null)}
                      aria-label="Cancel rename"
                    >
                      <X size={13} />
                    </button>
                  </div>
                ) : (
                  <>
                    <button
                      type="button"
                      className="bnv-mentor-conv-select"
                      onClick={() => openConversation(conv.id)}
                    >
                      <MessageSquare size={14} className="bnv-mentor-conv-icon" />
                      <span className="bnv-mentor-conv-title">{conv.title}</span>
                    </button>
                    <div className="bnv-mentor-conv-actions">
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => {
                          setEditingConvId(conv.id);
                          setEditingTitle(conv.title);
                        }}
                        aria-label={`Rename ${conv.title}`}
                        title="Rename"
                      >
                        <Edit3 size={13} />
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => handleDeleteConversation(conv.id)}
                        aria-label={`Delete ${conv.title}`}
                        title="Delete"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Main Chat Canvas */}
      <div className="bnv-mentor-main">
        <div className="bnv-mentor-topbar">
          <div className="bnv-mentor-topbar-title">
            <Sparkles size={16} className="bnv-gold-accent-icon" />
            <span>{activeTitle}</span>
          </div>
          {streamingProvider && (
            <span className="bnv-mentor-provider-pill">{streamingProvider}</span>
          )}
        </div>

        <div className="bnv-mentor-messages">
          {loadingConv ? (
            <div className="bnv-mentor-loading">Loading conversation…</div>
          ) : messages.length === 0 && !streaming ? (
            <div className="bnv-mentor-welcome">
              <div className="bnv-mentor-welcome-brand">
                <BrainovaLogo size={48} variant="auth" alt="BRAINOVA AI Mentor" />
                <div>
                  <h3>BRAINOVA AI Mentor</h3>
                  <p>
                    General-purpose AI assistant for programming, DSA, mathematics, architecture
                    diagrams, academic concepts, and career preparation.
                  </p>
                </div>
              </div>

              <div className="bnv-mentor-cat-pills" role="group" aria-label="Topic categories">
                {['All', ...TOPIC_CATEGORIES].map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    className={`focus-chip-btn ${selectedCategory === cat ? 'active' : ''}`}
                    onClick={() => setSelectedCategory(cat)}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              <div className="bnv-mentor-starter-grid">
                {visiblePrompts.map((item) => (
                  <button
                    key={item.title}
                    type="button"
                    className="bnv-mentor-starter-card"
                    onClick={() => runStreamTurn(item.prompt)}
                  >
                    <span className="bnv-mentor-starter-cat">{item.category}</span>
                    <span className="bnv-mentor-starter-title">{item.title}</span>
                    <span className="bnv-mentor-starter-desc">{item.prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, idx) => {
                const isLastAssistant =
                  msg.role === 'assistant' && idx === messages.length - 1 && !streaming;
                return (
                  <div
                    key={msg.id || idx}
                    className={`bnv-mentor-msg bnv-mentor-msg--${msg.role}`}
                  >
                    <div className="bnv-mentor-msg-role">
                      {msg.role === 'user' ? 'You' : 'BRAINOVA AI Mentor'}
                    </div>
                    <div className="bnv-mentor-msg-bubble">
                      {msg.role === 'assistant' ? (
                        <>
                          <MentorMarkdownRenderer content={msg.content} />
                          {msg.image && (
                            <MentorImageCard
                              image={msg.image}
                              onRegenerate={handleGenerateIllustration}
                              disabled={generatingImage || streaming}
                            />
                          )}
                        </>
                      ) : (
                        <p className="bnv-user-msg-text">{msg.content}</p>
                      )}
                    </div>
                    {msg.role === 'assistant' && (
                      <div className="bnv-mentor-msg-actions">
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => handleCopyMessage(msg.id, msg.content)}
                          aria-label="Copy response"
                        >
                          {copiedMsgId === msg.id ? <Check size={13} /> : <Copy size={13} />}
                          <span>{copiedMsgId === msg.id ? 'Copied' : 'Copy'}</span>
                        </button>
                        {!msg.image && (
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => {
                              const prevUser = [...messages.slice(0, idx)].reverse().find((m) => m.role === 'user');
                              handleGenerateIllustration(
                                prevUser?.content || msg.content.slice(0, 300)
                              );
                            }}
                            disabled={generatingImage || streaming}
                            title="Generate an AI educational illustration"
                          >
                            <ImageIcon size={13} />
                            <span>{generatingImage ? 'Generating…' : 'Illustrate'}</span>
                          </button>
                        )}
                        {isLastAssistant && (
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => runStreamTurn('', true)}
                          >
                            <RefreshCw size={13} />
                            <span>Regenerate</span>
                          </button>
                        )}
                        <button
                          type="button"
                          className={`btn btn-ghost btn-sm ${msg.feedback === 'up' ? 'bnv-fb-active' : ''}`}
                          onClick={() => handleFeedback(msg.id, 'up')}
                          aria-label="Helpful response"
                        >
                          <ThumbsUp size={13} />
                        </button>
                        <button
                          type="button"
                          className={`btn btn-ghost btn-sm ${msg.feedback === 'down' ? 'bnv-fb-active' : ''}`}
                          onClick={() => handleFeedback(msg.id, 'down')}
                          aria-label="Unhelpful response"
                        >
                          <ThumbsDown size={13} />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}

              {streaming && (
                <div className="bnv-mentor-msg bnv-mentor-msg--assistant">
                  <div className="bnv-mentor-msg-role">
                    BRAINOVA AI Mentor · Generating…
                  </div>
                  <div className="bnv-mentor-msg-bubble">
                    {streamingText ? (
                      <MentorMarkdownRenderer content={streamingText} />
                    ) : (
                      <span className="bnv-mentor-typing-dots" aria-label="Thinking">
                        <span />
                        <span />
                        <span />
                      </span>
                    )}
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {errorMsg && (
          <div className="bnv-mentor-error-banner" role="alert">
            <span>{errorMsg}</span>
            {needsKeyHint && (
              <Link to="/settings" className="btn btn-secondary btn-sm">
                Configure API Key in Settings
              </Link>
            )}
          </div>
        )}

        <form
          className="bnv-mentor-composer"
          onSubmit={(e) => {
            e.preventDefault();
            if (composerText.trim() && !streaming) {
              runStreamTurn(composerText.trim());
            }
          }}
        >
          <div className={`bnv-mentor-composer-box${composerText.trim() ? ' is-active' : ''}`}>
            <textarea
              className="bnv-mentor-textarea"
              rows={1}
              aria-label="Ask anything"
              placeholder="Ask anything ..."
              value={composerText}
              onChange={(e) => setComposerText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  if (composerText.trim() && !streaming) {
                    runStreamTurn(composerText.trim());
                  }
                }
              }}
              disabled={streaming}
            />
            <div className="bnv-mentor-composer-actions">
              {streaming ? (
                <button
                  type="button"
                  className="btn btn-danger bnv-mentor-stop-btn"
                  onClick={handleStopGeneration}
                  aria-label="Stop generation"
                >
                  <Square size={14} />
                  <span>Stop</span>
                </button>
              ) : (
                <button
                  type="submit"
                  className="btn btn-primary bnv-mentor-send-btn"
                  disabled={!composerText.trim()}
                  aria-label="Send message"
                >
                  <Send size={14} />
                  <span>Send</span>
                </button>
              )}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

