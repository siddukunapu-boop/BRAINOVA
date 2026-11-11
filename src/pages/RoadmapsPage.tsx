import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Compass,
  Sparkles,
  Plus,
  Trash2,
  Edit3,
  ChevronDown,
  ChevronUp,
  ArrowUp,
  ArrowDown,
  Save,
  Clock,
  CheckCircle2,
  FolderPlus,
} from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp } from '../context/AppContext';

const ROLE_PRESETS = [
  'Full Stack Developer',
  'Backend Developer',
  'Frontend Developer',
  'Data Scientist',
  'Machine Learning Engineer',
  'Competitive Programming',
];

export const RoadmapsPage: React.FC = () => {
  const { user, addToast } = useApp();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [roadmaps, setRoadmaps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Conversational AI Roadmap Agent States
  const [showAgent, setShowAgent] = useState(false);
  const [targetRole, setTargetRole] = useState(user?.target_role || 'Full Stack Developer');
  const [skillLevel, setSkillLevel] = useState(
    user?.preferences?.default_skill_level || 'Intermediate'
  );
  const [hoursPerWeek, setHoursPerWeek] = useState(
    user?.preferences?.study_hours_per_week || 12
  );
  const [preferredStack, setPreferredStack] = useState('React, TypeScript, FastAPI / Node.js, SQL');
  const [existingKnowledge, setExistingKnowledge] = useState('');
  const [targetDate, setTargetDate] = useState('');
  const [priorities, setPriorities] = useState('Hands-on projects & 20-MCQ mastery exams');
  const [examGoals, setExamGoals] = useState('Technical interviews & college field evaluation');
  const [showAdvancedPrefs, setShowAdvancedPrefs] = useState(false);

  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [agentMessage, setAgentMessage] = useState('');
  const [followUps, setFollowUps] = useState<string[]>([]);
  const [draftRoadmap, setDraftRoadmap] = useState<any | null>(null);
  const [generationPolicy, setGenerationPolicy] = useState('all_async');
  const [expandedDraftPhases, setExpandedDraftPhases] = useState<Record<number, boolean>>({});

  // Delete Roadmap Confirmation Modal
  const [deletingRoadmap, setDeletingRoadmap] = useState<any | null>(null);

  const loadRoadmaps = async () => {
    setLoading(true);
    try {
      const res = await apiRequest<{ roadmaps: any[] }>('/api/roadmaps');
      setRoadmaps(res.roadmaps || []);
      if ((res.roadmaps || []).length === 0 || searchParams.get('new') === '1') {
        setShowAgent(true);
      }
    } catch (err: any) {
      addToast(err.message || 'Failed to load roadmaps.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRoadmaps();
  }, []);

  const handleGenerateDraft = async (customFollowUp?: string) => {
    if (!targetRole.trim()) {
      addToast('Please enter a career role or learning goal.', 'error');
      return;
    }
    setGenerating(true);
    try {
      const res = await apiRequest('/api/roadmaps/generate', {
        method: 'POST',
        body: JSON.stringify({
          target_role: targetRole.trim(),
          skill_level: skillLevel,
          hours_per_week: Number(hoursPerWeek) || 10,
          preferred_stack: preferredStack,
          existing_knowledge: existingKnowledge,
          target_completion_date: targetDate,
          priorities: customFollowUp ? `${priorities}. ${customFollowUp}` : priorities,
          exam_goals: examGoals,
          conversation_message: customFollowUp,
        }),
      });
      setDraftRoadmap(res.draft_roadmap);
      setAgentMessage(res.agent_message);
      setFollowUps(res.follow_up_suggestions || []);
      const exp: Record<number, boolean> = {};
      (res.draft_roadmap?.phases || []).forEach((_: any, i: number) => {
        exp[i] = true;
      });
      setExpandedDraftPhases(exp);
      addToast('Generated editable AI Roadmap preview!', 'success');
    } catch (err: any) {
      addToast(err.message || 'Roadmap generation failed.', 'error');
    } finally {
      setGenerating(false);
    }
  };

  // Draft Preview Manipulation Helpers
  const updateDraftPhase = (pIdx: number, field: string, value: any) => {
    if (!draftRoadmap) return;
    const phases = [...draftRoadmap.phases];
    phases[pIdx] = { ...phases[pIdx], [field]: value };
    setDraftRoadmap({ ...draftRoadmap, phases });
  };

  const moveDraftPhase = (pIdx: number, direction: -1 | 1) => {
    if (!draftRoadmap) return;
    const targetIdx = pIdx + direction;
    if (targetIdx < 0 || targetIdx >= draftRoadmap.phases.length) return;
    const phases = [...draftRoadmap.phases];
    const temp = phases[pIdx];
    phases[pIdx] = phases[targetIdx];
    phases[targetIdx] = temp;
    setDraftRoadmap({ ...draftRoadmap, phases });
  };

  const addDraftPhase = () => {
    if (!draftRoadmap) return;
    const newPhase = {
      phase_order: draftRoadmap.phases.length + 1,
      title: `Phase ${draftRoadmap.phases.length + 1}: Advanced Specialization`,
      description: 'Custom learning phase added in preview editor.',
      estimated_hours: 10,
      completion_criteria: 'Complete all topics and pass the 20-MCQ exams.',
      topics: [
        {
          topic_order: 1,
          title: `${targetRole} Capstone & Architecture Review`,
          description: 'End-to-end synthesis and practical implementation.',
          subtopics: ['System architecture', 'Implementation', 'Testing & verification'],
          prerequisites: ['Previous phases'],
          difficulty: skillLevel,
          estimated_hours: 10,
          learning_objectives: ['Deliver a complete project'],
          practical_exercises: ['Build and test the module'],
          project_checkpoint: 'Capstone Deliverable',
          completion_criteria: 'Pass the 20-MCQ exam.',
        },
      ],
    };
    const nextIdx = draftRoadmap.phases.length;
    setDraftRoadmap({
      ...draftRoadmap,
      phases: [...draftRoadmap.phases, newPhase],
    });
    setExpandedDraftPhases((prev) => ({ ...prev, [nextIdx]: true }));
  };

  const removeDraftPhase = (pIdx: number) => {
    if (!draftRoadmap || draftRoadmap.phases.length <= 1) {
      addToast('A roadmap must contain at least one phase.', 'error');
      return;
    }
    const phases = draftRoadmap.phases.filter((_: any, i: number) => i !== pIdx);
    setDraftRoadmap({ ...draftRoadmap, phases });
  };

  const updateDraftTopic = (pIdx: number, tIdx: number, field: string, value: any) => {
    if (!draftRoadmap) return;
    const phases = [...draftRoadmap.phases];
    const topics = [...phases[pIdx].topics];
    topics[tIdx] = { ...topics[tIdx], [field]: value };
    phases[pIdx] = { ...phases[pIdx], topics };
    setDraftRoadmap({ ...draftRoadmap, phases });
  };

  const moveDraftTopic = (pIdx: number, tIdx: number, direction: -1 | 1) => {
    if (!draftRoadmap) return;
    const phases = [...draftRoadmap.phases];
    const topics = [...phases[pIdx].topics];
    const targetIdx = tIdx + direction;
    if (targetIdx < 0 || targetIdx >= topics.length) return;
    const temp = topics[tIdx];
    topics[tIdx] = topics[targetIdx];
    topics[targetIdx] = temp;
    phases[pIdx] = { ...phases[pIdx], topics };
    setDraftRoadmap({ ...draftRoadmap, phases });
  };

  const addDraftTopic = (pIdx: number) => {
    if (!draftRoadmap) return;
    const phases = [...draftRoadmap.phases];
    const topics = [...phases[pIdx].topics];
    topics.push({
      topic_order: topics.length + 1,
      title: 'New Custom Study Topic',
      description: 'Focused study module with tutorial, reading guide, and 20-MCQ assessment.',
      subtopics: ['Core theory', 'Practical patterns', 'Edge-case testing'],
      prerequisites: ['Foundational concepts'],
      difficulty: skillLevel,
      estimated_hours: 8,
      learning_objectives: ['Master the topic mechanics'],
      practical_exercises: ['Implement a working solution'],
      project_checkpoint: 'Practical Milestone',
      completion_criteria: 'Pass the 20-MCQ exam.',
    });
    phases[pIdx] = { ...phases[pIdx], topics };
    setDraftRoadmap({ ...draftRoadmap, phases });
  };

  const removeDraftTopic = (pIdx: number, tIdx: number) => {
    if (!draftRoadmap) return;
    const phases = [...draftRoadmap.phases];
    if (phases[pIdx].topics.length <= 1) {
      addToast('Each phase must have at least one topic.', 'error');
      return;
    }
    phases[pIdx] = {
      ...phases[pIdx],
      topics: phases[pIdx].topics.filter((_: any, i: number) => i !== tIdx),
    };
    setDraftRoadmap({ ...draftRoadmap, phases });
  };

  const handleSaveRoadmap = async () => {
    if (!draftRoadmap || saving) return;
    setSaving(true);
    try {
      const res = await apiRequest<{ roadmap: any }>('/api/roadmaps', {
        method: 'POST',
        body: JSON.stringify({
          title: draftRoadmap.title,
          target_role: draftRoadmap.target_role || targetRole,
          description: draftRoadmap.description,
          skill_level: draftRoadmap.skill_level || skillLevel,
          existing_knowledge: existingKnowledge,
          target_completion_date: targetDate,
          hours_per_week: Number(hoursPerWeek) || 10,
          preferred_stack: preferredStack,
          priorities,
          exam_goals: examGoals,
          generation_policy: generationPolicy,
          run_sync_for_first_topic: true,
          phases: draftRoadmap.phases,
        }),
      });
      addToast(
        `Saved roadmap "${res.roadmap.title}"! Topic 1 resources are ready and remaining jobs are queued.`,
        'success'
      );
      navigate(`/roadmaps/${res.roadmap.id}`);
    } catch (err: any) {
      addToast(err.message || 'Failed to save roadmap.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleConfirmDeleteRoadmap = async () => {
    if (!deletingRoadmap) return;
    try {
      await apiRequest(`/api/roadmaps/${deletingRoadmap.id}`, { method: 'DELETE' });
      addToast(`Deleted roadmap "${deletingRoadmap.title}".`, 'info');
      setDeletingRoadmap(null);
      loadRoadmaps();
    } catch (err: any) {
      addToast(err.message || 'Delete failed.', 'error');
    }
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
          <span className="badge badge-indigo" style={{ marginBottom: '6px' }}>
            Intelligent AI Roadmap System
          </span>
          <h1 style={{ fontSize: '1.65rem' }}>AI Career & Learning Roadmaps</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
            Plan your career goal with the conversational AI Roadmap Agent, customize phases and
            topics before saving, and study every module with tutorials, reading guides, and 20-MCQ
            exams.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setShowAgent((s) => !s)}
        >
          <Sparkles size={16} />
          <span>{showAgent ? 'Hide AI Roadmap Agent' : 'Launch AI Roadmap Agent'}</span>
        </button>
      </div>

      {/* Conversational AI Roadmap Agent & Interactive Preview Editor */}
      {showAgent && (
        <div className="card" style={{ border: '1px solid var(--border-strong)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
            <Compass size={22} color="var(--accent-blue)" />
            <div>
              <h2 style={{ fontSize: '1.25rem' }}>Conversational AI Roadmap Agent</h2>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Choose a career preset or enter any custom learning goal. Sensible defaults are
                pre-filled so you can generate immediately.
              </span>
            </div>
          </div>

          {/* Quick Role Presets */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
            {ROLE_PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                className={`btn btn-sm ${
                  targetRole === preset ? 'btn-primary' : 'btn-secondary'
                }`}
                onClick={() => setTargetRole(preset)}
              >
                {preset}
              </button>
            ))}
          </div>

          <div className="grid-3" style={{ marginBottom: '12px' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="rm-role-input">
                Target Career Role or Custom Goal
              </label>
              <input
                id="rm-role-input"
                type="text"
                className="form-input"
                placeholder="e.g., Full Stack Developer, AI Systems Engineer..."
                value={targetRole}
                onChange={(e) => setTargetRole(e.target.value)}
              />
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="rm-skill-select">
                Current Skill Level
              </label>
              <select
                id="rm-skill-select"
                className="form-select"
                value={skillLevel}
                onChange={(e) => setSkillLevel(e.target.value)}
              >
                <option value="Beginner">Beginner</option>
                <option value="Intermediate">Intermediate</option>
                <option value="Advanced">Advanced</option>
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="rm-hours-input">
                Available Study Hours / Week
              </label>
              <input
                id="rm-hours-input"
                type="number"
                min={2}
                max={60}
                className="form-input"
                value={hoursPerWeek}
                onChange={(e) => setHoursPerWeek(Number(e.target.value))}
              />
            </div>
          </div>

          <div style={{ marginBottom: '16px' }}>
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={() => setShowAdvancedPrefs((p) => !p)}
            >
              {showAdvancedPrefs ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              <span>
                {showAdvancedPrefs
                  ? 'Hide Optional Preferences'
                  : 'Configure Optional Stack, Prior Knowledge & Exam Goals'}
              </span>
            </button>

            {showAdvancedPrefs && (
              <div className="grid-2" style={{ marginTop: '12px' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Preferred Technology Stack</label>
                  <input
                    type="text"
                    className="form-input"
                    value={preferredStack}
                    onChange={(e) => setPreferredStack(e.target.value)}
                    placeholder="e.g., React, TypeScript, Python, PostgreSQL"
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Existing Knowledge / Prerequisites</label>
                  <input
                    type="text"
                    className="form-input"
                    value={existingKnowledge}
                    onChange={(e) => setExistingKnowledge(e.target.value)}
                    placeholder="e.g., Basic programming in Python/C++"
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Target Completion Date</label>
                  <input
                    type="date"
                    className="form-input"
                    value={targetDate}
                    onChange={(e) => setTargetDate(e.target.value)}
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Interview or Examination Goals</label>
                  <input
                    type="text"
                    className="form-input"
                    value={examGoals}
                    onChange={(e) => setExamGoals(e.target.value)}
                  />
                </div>
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleGenerateDraft()}
              disabled={generating}
            >
              <Sparkles size={16} />
              <span>
                {generating ? 'Designing Structured Curriculum...' : 'Generate AI Roadmap Plan'}
              </span>
            </button>
          </div>

          {/* Agent Conversational Response & Interactive Preview Editor */}
          {draftRoadmap && (
            <div
              style={{
                marginTop: '24px',
                paddingTop: '24px',
                borderTop: '1px solid var(--border-default)',
              }}
            >
              {agentMessage && (
                <div
                  style={{
                    padding: '14px 18px',
                    borderRadius: '12px',
                    background: 'rgba(56, 189, 248, 0.1)',
                    border: '1px solid rgba(56, 189, 248, 0.3)',
                    marginBottom: '16px',
                  }}
                >
                  <div style={{ fontSize: '0.92rem', marginBottom: '10px' }}>{agentMessage}</div>
                  {followUps.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                      {followUps.map((f, i) => (
                        <button
                          key={i}
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleGenerateDraft(f)}
                          disabled={generating}
                        >
                          <Sparkles size={12} />
                          <span>{f}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Editable Roadmap Header */}
              <div className="grid-2" style={{ marginBottom: '16px' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Roadmap Title (Editable before saving)</label>
                  <input
                    type="text"
                    className="form-input"
                    value={draftRoadmap.title}
                    onChange={(e) =>
                      setDraftRoadmap({ ...draftRoadmap, title: e.target.value })
                    }
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">Resource Generation Strategy on Save</label>
                  <select
                    className="form-select"
                    value={generationPolicy}
                    onChange={(e) => setGenerationPolicy(e.target.value)}
                  >
                    <option value="all_async">
                      Generate Topic 1 immediately + queue all remaining topics asynchronously
                    </option>
                    <option value="phase_1_only">
                      Generate Phase 1 resources first (save bandwidth on later phases)
                    </option>
                    <option value="on_demand">
                      Generate Topic 1 now + generate others on-demand when opened
                    </option>
                  </select>
                </div>
              </div>

              {/* Phases & Topics Preview Editor */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '20px' }}>
                {draftRoadmap.phases.map((phase: any, pIdx: number) => {
                  const isExpanded = expandedDraftPhases[pIdx] !== false;
                  return (
                    <div
                      key={pIdx}
                      style={{
                        borderRadius: '12px',
                        background: 'var(--bg-charcoal)',
                        border: '1px solid var(--border-default)',
                        padding: '16px',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          flexWrap: 'wrap',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          gap: '10px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() =>
                              setExpandedDraftPhases((prev) => ({
                                ...prev,
                                [pIdx]: !isExpanded,
                              }))
                            }
                          >
                            {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                          </button>
                          <input
                            type="text"
                            className="form-input"
                            style={{ fontWeight: 700, maxWidth: 480 }}
                            value={phase.title}
                            onChange={(e) => updateDraftPhase(pIdx, 'title', e.target.value)}
                          />
                          <span className="badge badge-indigo">
                            {phase.topics.length} topics
                          </span>
                        </div>

                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => moveDraftPhase(pIdx, -1)}
                            disabled={pIdx === 0}
                            title="Move phase up"
                          >
                            <ArrowUp size={14} />
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => moveDraftPhase(pIdx, 1)}
                            disabled={pIdx === draftRoadmap.phases.length - 1}
                            title="Move phase down"
                          >
                            <ArrowDown size={14} />
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => addDraftTopic(pIdx)}
                          >
                            <Plus size={14} />
                            <span>Add Topic</span>
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => removeDraftPhase(pIdx)}
                            title="Remove phase"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>

                      {isExpanded && (
                        <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                          {phase.topics.map((topic: any, tIdx: number) => (
                            <div
                              key={tIdx}
                              style={{
                                padding: '12px',
                                borderRadius: '10px',
                                background: 'var(--surface-1)',
                                border: '1px solid var(--border-subtle)',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '8px',
                              }}
                            >
                              <div
                                style={{
                                  display: 'flex',
                                  flexWrap: 'wrap',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  gap: '10px',
                                }}
                              >
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
                                  <span className="badge badge-blue">
                                    {pIdx + 1}.{tIdx + 1}
                                  </span>
                                  <input
                                    type="text"
                                    className="form-input"
                                    style={{ fontWeight: 600 }}
                                    value={topic.title}
                                    onChange={(e) =>
                                      updateDraftTopic(pIdx, tIdx, 'title', e.target.value)
                                    }
                                  />
                                </div>

                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <input
                                    type="number"
                                    min={1}
                                    max={60}
                                    className="form-input"
                                    style={{ width: 76 }}
                                    value={topic.estimated_hours}
                                    onChange={(e) =>
                                      updateDraftTopic(
                                        pIdx,
                                        tIdx,
                                        'estimated_hours',
                                        Number(e.target.value)
                                      )
                                    }
                                    title="Estimated study hours"
                                  />
                                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                                    hrs
                                  </span>
                                  <button
                                    type="button"
                                    className="btn btn-secondary btn-sm"
                                    onClick={() => moveDraftTopic(pIdx, tIdx, -1)}
                                    disabled={tIdx === 0}
                                  >
                                    <ArrowUp size={13} />
                                  </button>
                                  <button
                                    type="button"
                                    className="btn btn-secondary btn-sm"
                                    onClick={() => moveDraftTopic(pIdx, tIdx, 1)}
                                    disabled={tIdx === phase.topics.length - 1}
                                  >
                                    <ArrowDown size={13} />
                                  </button>
                                  <button
                                    type="button"
                                    className="btn btn-danger btn-sm"
                                    onClick={() => removeDraftTopic(pIdx, tIdx)}
                                  >
                                    <Trash2 size={13} />
                                  </button>
                                </div>
                              </div>

                              <input
                                type="text"
                                className="form-input"
                                style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}
                                value={topic.description}
                                onChange={(e) =>
                                  updateDraftTopic(pIdx, tIdx, 'description', e.target.value)
                                }
                              />
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '12px',
                }}
              >
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={addDraftPhase}
                >
                  <FolderPlus size={16} />
                  <span>Add Custom Phase</span>
                </button>

                <button
                  type="button"
                  className="btn btn-primary btn-lg"
                  onClick={handleSaveRoadmap}
                  disabled={saving}
                >
                  <Save size={18} />
                  <span>
                    {saving
                      ? 'Saving Roadmap & Provisioning Topic Workspaces...'
                      : 'Save Roadmap & Provision Learning Resources'}
                  </span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Saved Roadmaps List */}
      <div className="card">
        <h2 style={{ fontSize: '1.25rem', marginBottom: '16px' }}>Your Saved Roadmaps</h2>

        {loading ? (
          <p style={{ color: 'var(--text-muted)' }}>Loading saved roadmaps...</p>
        ) : roadmaps.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '36px 16px' }}>
            <Compass size={42} color="var(--text-subtle)" style={{ marginBottom: '10px' }} />
            <h3 style={{ marginBottom: '6px' }}>No Saved Roadmaps Yet</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '16px' }}>
              Use the AI Roadmap Agent above to generate, preview, and save your first structured
              learning roadmap.
            </p>
          </div>
        ) : (
          <div className="grid-2">
            {roadmaps.map((rm) => (
              <div
                key={rm.id}
                className="card card-interactive"
                style={{
                  background: 'var(--bg-charcoal)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '14px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', marginBottom: '8px' }}>
                    <span className="badge badge-indigo">{rm.target_role}</span>
                    <span className="badge badge-blue">{rm.skill_level}</span>
                  </div>
                  <h3
                    style={{ fontSize: '1.2rem', marginBottom: '6px', cursor: 'pointer' }}
                    onClick={() => navigate(`/roadmaps/${rm.id}`)}
                  >
                    {rm.title}
                  </h3>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '14px' }}>
                    {rm.description}
                  </p>
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', marginBottom: '6px' }}>
                    <span>
                      Progress: {rm.completed_topics} / {rm.total_topics} topics
                    </span>
                    <strong>{rm.progress_percent}%</strong>
                  </div>
                  <div className="progress-track" style={{ marginBottom: '14px' }}>
                    <div className="progress-fill" style={{ width: `${rm.progress_percent}%` }} />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      <Clock size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                      {rm.total_estimated_hours}h • {rm.phases?.length || 0} phases
                    </span>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={() => navigate(`/roadmaps/${rm.id}`)}
                      >
                        Open Roadmap
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => setDeletingRoadmap(rm)}
                        title="Delete roadmap"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete Roadmap Confirmation Modal */}
      {deletingRoadmap && (
        <div className="modal-backdrop" onClick={() => setDeletingRoadmap(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: '10px' }}>Delete Roadmap "{deletingRoadmap.title}"?</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '14px' }}>
              Deleting this roadmap will permanently remove:
            </p>
            <ul style={{ color: 'var(--text-secondary)', fontSize: '0.86rem', paddingLeft: '20px', marginBottom: '20px' }}>
              <li>All {deletingRoadmap.phases?.length || 0} phases and {deletingRoadmap.total_topics || 0} topics in this roadmap</li>
              <li>Associated topic tutorials, generated reading materials, and 20-MCQ sets</li>
              <li>Personal topic notes and recorded quiz attempts attached to this roadmap</li>
            </ul>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setDeletingRoadmap(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleConfirmDeleteRoadmap}
              >
                Confirm Permanent Deletion
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

