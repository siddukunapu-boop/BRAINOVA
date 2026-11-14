import React, { useState } from 'react';
import { Save, User, Sliders, Palette, Upload, Check } from 'lucide-react';
import { apiRequest } from '../services/api';
import { useApp, BRAINOVA_THEMES, BrainovaTheme } from '../context/AppContext';

export const SettingsPage: React.FC = () => {
  const { user, theme, setTheme, refreshUser, addToast } = useApp();
  const prefs = user?.preferences;

  // Profile States (Part 11)
  const [name, setName] = useState(user?.name || '');
  const [targetRole, setTargetRole] = useState(user?.target_role || 'Full Stack Developer');
  const [bio, setBio] = useState(user?.bio || '');
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url || '');
  const [savingProfile, setSavingProfile] = useState(false);


  const [preferredLanguage, setPreferredLanguage] = useState(
    prefs?.preferred_language || 'English'
  );
  const [defaultSkill, setDefaultSkill] = useState(prefs?.default_skill_level || 'Intermediate');
  const [hoursPerWeek, setHoursPerWeek] = useState(prefs?.study_hours_per_week || 12);
  const [savingPrefs, setSavingPrefs] = useState(false);

  // Convert uploaded avatar file into a compact data URL
  const handleAvatarFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      addToast('Please choose an image smaller than 2 MB.', 'error');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setAvatarUrl(reader.result);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    try {
      await apiRequest('/api/settings/profile', {
        method: 'PUT',
        body: JSON.stringify({
          name: name.trim(),
          target_role: targetRole.trim(),
          bio: bio.trim(),
          avatar_url: avatarUrl.trim(),
        }),
      });
      await refreshUser();
      addToast('Updated your BRAINOVA profile settings!', 'success');
    } catch (err: any) {
      addToast(err.message || 'Profile update failed.', 'error');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleSavePreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingPrefs(true);
    try {
      const payload: Record<string, any> = {
        default_skill_level: defaultSkill,
        study_hours_per_week: Number(hoursPerWeek) || 12,
        theme,
        preferred_language: preferredLanguage,
      };

      await apiRequest('/api/settings/preferences', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      await refreshUser();
      addToast('Saved language & theme preferences!', 'success');
    } catch (err: any) {
      addToast(err.message || 'Preferences update failed.', 'error');
    } finally {
      setSavingPrefs(false);
    }
  };

  const initials = (name || user?.name || 'B')
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="card card-elevated">
        <span className="badge badge-indigo" style={{ marginBottom: '6px' }}>
          BRAINOVA PROFILE & THEME SETTINGS
        </span>
        <h1 style={{ fontSize: '1.65rem', marginBottom: '6px' }}>
          Profile Settings & Theme Preferences
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
          Personalize your learner profile and avatar, switch between the 4 BRAINOVA visual themes,
          and choose your default Indian/Global output language.
        </p>
      </div>

      {/* Four-Theme System Selector Card (Part 12) */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <Palette size={18} color="var(--accent-blue)" />
          <h2 style={{ fontSize: '1.2rem', margin: 0 }}>
            BRAINOVA Four-Theme Visual Appearance System
          </h2>
        </div>
        <div className="grid-4">
          {BRAINOVA_THEMES.map((t) => {
            const isSelected = theme === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  setTheme(t.id as BrainovaTheme);
                  addToast(`Switched theme to ${t.name}`, 'info');
                }}
                style={{
                  textAlign: 'left',
                  padding: '14px',
                  borderRadius: '12px',
                  background: 'var(--bg-charcoal)',
                  border: isSelected
                    ? '2px solid var(--accent-blue)'
                    : '1px solid var(--border-subtle)',
                  cursor: 'pointer',
                  color: 'var(--text-primary)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: '8px',
                      background: `linear-gradient(135deg, ${t.swatches[0]} 0%, ${t.swatches[1]} 55%, ${t.swatches[2]} 100%)`,
                      border: '1px solid rgba(255,255,255,0.2)',
                    }}
                  />
                  {isSelected && <Check size={16} color="var(--accent-blue)" />}
                </div>
                <div style={{ fontWeight: 700, fontSize: '0.92rem', marginBottom: '4px' }}>
                  {t.name}
                </div>
                <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                  {t.description}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div>
        {/* Left: Learner Profile & Avatar Settings (Part 11) */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <User size={18} color="var(--accent-blue)" />
            <h2 style={{ fontSize: '1.2rem' }}>Profile Settings</h2>
          </div>

          <form onSubmit={handleSaveProfile}>
            {/* Profile Avatar Preview & Upload */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                padding: '14px',
                borderRadius: '12px',
                background: 'var(--bg-charcoal)',
                border: '1px solid var(--border-subtle)',
                marginBottom: '16px',
              }}
            >
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt={name}
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: '50%',
                    objectFit: 'cover',
                    border: '2px solid var(--accent-blue)',
                    flexShrink: 0,
                  }}
                />
              ) : (
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: '50%',
                    background: 'var(--gradient-brand)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1.35rem',
                    fontWeight: 800,
                    color: '#fff',
                    flexShrink: 0,
                  }}
                >
                  {initials}
                </div>
              )}

              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, fontSize: '0.9rem', marginBottom: '6px' }}>
                  Profile Image / Avatar
                </div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
                    <Upload size={13} />
                    <span>Upload Photo</span>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleAvatarFileUpload}
                      style={{ display: 'none' }}
                    />
                  </label>
                  {avatarUrl && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => setAvatarUrl('')}
                    >
                      Remove Photo
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Display Name</label>
              <input
                type="text"
                className="form-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Account Email (Verified)</label>
              <input
                type="email"
                className="form-input"
                value={user?.email || ''}
                disabled
                style={{ opacity: 0.7 }}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Primary Career / Learning Goal</label>
              <input
                type="text"
                className="form-input"
                value={targetRole}
                onChange={(e) => setTargetRole(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Academic / Engineering Bio</label>
              <textarea
                className="form-textarea"
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="Your current degree, target roles, or study focus..."
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={savingProfile}
            >
              <Save size={15} />
              <span>{savingProfile ? 'Saving Profile...' : 'Save Profile Settings'}</span>
            </button>
          </form>

          <hr style={{ border: 'none', borderTop: '1px solid var(--border-subtle)', margin: '24px 0' }} />

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Sliders size={18} color="var(--accent-indigo)" />
            <h2 style={{ fontSize: '1.2rem' }}>Language & Learning Preferences</h2>
          </div>

          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">Default Learning Language</label>
              <select
                className="form-select"
                value={preferredLanguage}
                onChange={(e) => setPreferredLanguage(e.target.value)}
              >
                <option value="English">English</option>
                <option value="Telugu">Telugu (తెలుగు)</option>
                <option value="Hindi">Hindi (हिन्दी)</option>
                <option value="Kannada">Kannada (ಕನ್ನಡ)</option>
                <option value="Tamil">Tamil (தமிழ்)</option>
                <option value="Marathi">Marathi (मराठी)</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Default Skill Level</label>
              <select
                className="form-select"
                value={defaultSkill}
                onChange={(e) => setDefaultSkill(e.target.value)}
              >
                <option value="Beginner">Beginner</option>
                <option value="Intermediate">Intermediate</option>
                <option value="Advanced">Advanced</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Default Study Hours / Week</label>
            <input
              type="number"
              min={2}
              max={60}
              className="form-input"
              value={hoursPerWeek}
              onChange={(e) => setHoursPerWeek(Number(e.target.value))}
            />
          </div>

          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSavePreferences}
            disabled={savingPrefs}
          >
            <Save size={15} />
            <span>Save Preferences</span>
          </button>
        </div>

      </div>
    </div>
  );
};
