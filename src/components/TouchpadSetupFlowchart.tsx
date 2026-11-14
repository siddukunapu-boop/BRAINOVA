import React, { useState } from 'react';
import {
  Bluetooth,
  Check,
  ChevronDown,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  Info,
  Laptop,
  RotateCcw,
  Settings,
  ShieldCheck,
  Sparkles,
  Touchpad,
} from 'lucide-react';

interface StepMeta {
  id: number;
  code: string;
  badge: string;
  badgeTone: 'info' | 'important' | 'success';
  title: string;
  instruction: string;
}

const STEPS: StepMeta[] = [
  {
    id: 1,
    code: '01',
    badge: 'STEP 01',
    badgeTone: 'info',
    title: 'Open Windows Settings',
    instruction: 'Press the Windows key + I to open your system settings.',
  },
  {
    id: 2,
    code: '02',
    badge: 'STEP 02',
    badgeTone: 'info',
    title: 'Find Touchpad Settings',
    instruction: 'Open Bluetooth & devices, then select Touchpad.',
  },
  {
    id: 3,
    code: '03',
    badge: 'STEP 03',
    badgeTone: 'info',
    title: 'Locate Three-Finger Gestures',
    instruction: 'Find and expand the Three-finger gestures section.',
  },
  {
    id: 4,
    code: '04',
    badge: 'MOST IMPORTANT STEP',
    badgeTone: 'important',
    title: 'Set Swipes to Nothing',
    instruction: 'Find the Swipes setting and change its action to Nothing.',
  },
  {
    id: 5,
    code: '05',
    badge: 'STEP 05',
    badgeTone: 'success',
    title: 'Your Focus Environment Is Ready',
    instruction: 'Return to BRAINOVA and test your touchpad.',
  },
];

const VERIFICATION_ITEMS = [
  'Three-finger upward swipe no longer opens Task View.',
  'One-finger cursor movement and clicking still work.',
  'Two-finger scrolling still works.',
  'Four-finger gestures remain available.',
  'Normal keyboard typing and shortcuts remain unaffected.',
];

export const TouchpadSetupFlowchart: React.FC = () => {
  // Step 04 is highlighted/open by default or Step 01? Let's open Step 01 by default so it's a guided journey,
  // while keeping Step 04 visually prominent in the flowchart and progress bar.
  const [expandedSteps, setExpandedSteps] = useState<Record<number, boolean>>({
    1: true,
    2: false,
    3: false,
    4: true,
    5: false,
  });
  const [activeStep, setActiveStep] = useState<number>(1);
  const [restoreOpen, setRestoreOpen] = useState<boolean>(false);

  const allExpanded = STEPS.every((s) => Boolean(expandedSteps[s.id]));

  const handleToggleStep = (stepId: number) => {
    setActiveStep(stepId);
    setExpandedSteps((prev) => ({
      ...prev,
      [stepId]: !prev[stepId],
    }));
  };

  const handleJumpToStep = (stepId: number) => {
    setActiveStep(stepId);
    setExpandedSteps((prev) => ({
      ...prev,
      [stepId]: true,
    }));
  };

  const handleToggleAll = () => {
    const next = !allExpanded;
    const updated: Record<number, boolean> = {};
    for (const s of STEPS) {
      updated[s.id] = next;
    }
    setExpandedSteps(updated);
  };

  return (
    <section
      className="focus-panel tpf-journey-panel"
      aria-label="Windows 11 Touchpad Setup Flowchart"
      data-testid="touchpad-setup-flowchart"
    >
      {/* Ambient cinematic backdrop glow */}
      <div className="tpf-ambient-glow" aria-hidden="true" />

      {/* Header */}
      <div className="tpf-header">
        <div className="tpf-kicker-row">
          <span className="tpf-category-label">WINDOWS 11 · TOUCHPAD CONFIGURATION</span>
          <span className="tpf-status-pill">
            <Sparkles size={12} aria-hidden="true" />
            <span>5 SIMPLE STEPS</span>
          </span>
        </div>

        <h2 className="tpf-main-heading">ELIMINATE TOUCHPAD DISTRACTIONS</h2>
        <p className="tpf-subtitle">
          Take control of your focus. Disable accidental three-finger app switching in a few simple
          steps.
        </p>
      </div>

      {/* Introductory Cinematic Visual */}
      <div className="tpf-intro-stage" aria-hidden="true">
        <div className="tpf-stage-grid-bg" />
        <div className="tpf-laptop-scene">
          {/* Task View problem preview floating above laptop */}
          <div className="tpf-taskview-preview">
            <span className="tpf-taskview-tag">Windows Task View</span>
            <div className="tpf-taskview-cards">
              <span className="tpf-tv-card" />
              <span className="tpf-tv-card tpf-tv-card-center" />
              <span className="tpf-tv-card" />
            </div>
          </div>

          {/* Laptop body */}
          <div className="tpf-laptop-screen">
            <div className="tpf-screen-bar">
              <span className="tpf-dot" />
              <span className="tpf-dot" />
              <span className="tpf-dot" />
            </div>
            <div className="tpf-screen-body">
              <Laptop size={20} className="tpf-screen-icon" />
              <span>BRAINOVA Focus</span>
            </div>
          </div>

          {/* Touchpad deck with 3 animated fingers */}
          <div className="tpf-laptop-deck">
            <div className="tpf-intro-touchpad">
              <div className="tpf-swipe-trail" />
              <div className="tpf-three-fingers">
                <span className="tpf-finger" />
                <span className="tpf-finger tpf-finger-mid" />
                <span className="tpf-finger" />
              </div>
              <span className="tpf-touchpad-caption">3-Finger Upward Swipe</span>
            </div>
          </div>
        </div>
      </div>

      {/* Progress & Controls Bar */}
      <div className="tpf-controls-bar">
        <div className="tpf-progress-track" role="tablist" aria-label="Setup steps progress">
          {STEPS.map((step, idx) => {
            const isCurrent = activeStep === step.id;
            const isOpen = Boolean(expandedSteps[step.id]);
            return (
              <React.Fragment key={step.id}>
                <button
                  type="button"
                  role="tab"
                  aria-selected={isCurrent}
                  aria-label={`Jump to Step ${step.code}: ${step.title}`}
                  className={`tpf-progress-node ${isCurrent ? 'is-current' : ''} ${
                    isOpen ? 'is-open' : ''
                  } ${step.badgeTone === 'important' ? 'is-important' : ''}`}
                  onClick={() => handleJumpToStep(step.id)}
                >
                  <span>{step.code}</span>
                </button>
                {idx < STEPS.length - 1 && (
                  <span
                    className={`tpf-progress-line ${
                      activeStep > step.id ? 'is-lit' : ''
                    }`}
                    aria-hidden="true"
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>

        <button
          type="button"
          className="tpf-toggle-all-btn"
          onClick={handleToggleAll}
          data-testid="tpf-toggle-all-btn"
        >
          {allExpanded ? (
            <>
              <ChevronsDownUp size={14} aria-hidden="true" />
              <span>Collapse all</span>
            </>
          ) : (
            <>
              <ChevronsUpDown size={14} aria-hidden="true" />
              <span>Show all steps</span>
            </>
          )}
        </button>
      </div>

      {/* Connected 5-Step Flowchart */}
      <ol className="tpf-flowchart" aria-label="Windows 11 Touchpad Configuration Steps">
        {STEPS.map((step, index) => {
          const isOpen = Boolean(expandedSteps[step.id]);
          const isCurrent = activeStep === step.id;
          const isLast = index === STEPS.length - 1;
          const isImportant = step.badgeTone === 'important';

          return (
            <li
              key={step.id}
              className={`tpf-step-item ${isOpen ? 'is-open' : ''} ${
                isCurrent ? 'is-current' : ''
              } ${isImportant ? 'is-important' : ''}`}
              data-testid={`tpf-step-${step.id}`}
            >
              {/* Left timeline rail & numbered node */}
              <div className="tpf-rail" aria-hidden="true">
                <span
                  className={`tpf-step-node ${isOpen ? 'is-lit' : ''} ${
                    isImportant ? 'is-important' : ''
                  }`}
                >
                  {step.code}
                </span>
                {!isLast && (
                  <span className={`tpf-connector-line ${isOpen ? 'is-lit' : ''}`} />
                )}
              </div>

              {/* Step Card */}
              <div className={`tpf-step-card ${isImportant ? 'tpf-step-card-important' : ''}`}>
                <button
                  type="button"
                  className="tpf-step-trigger"
                  aria-expanded={isOpen}
                  aria-controls={`tpf-step-body-${step.id}`}
                  onClick={() => handleToggleStep(step.id)}
                  data-testid={`tpf-step-trigger-${step.id}`}
                >
                  <div className="tpf-step-trigger-main">
                    <span className={`tpf-step-badge tpf-badge-${step.badgeTone}`}>
                      {step.badge}
                    </span>
                    <span className="tpf-step-title">{step.title}</span>
                    <span className="tpf-step-instruction">{step.instruction}</span>
                  </div>
                  <span className="tpf-step-chevron" aria-hidden="true">
                    {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  </span>
                </button>

                {isOpen && (
                  <div
                    id={`tpf-step-body-${step.id}`}
                    className="tpf-step-body"
                    data-testid={`tpf-step-body-${step.id}`}
                  >
                    {/* STEP 01 VISUAL */}
                    {step.id === 1 && (
                      <div className="tpf-visual-box tpf-visual-shortcut">
                        <div className="tpf-keys-row" aria-label="Windows key plus I shortcut">
                          <kbd className="tpf-key tpf-key-win">
                            <span className="tpf-win-grid" aria-hidden="true">
                              <span />
                              <span />
                              <span />
                              <span />
                            </span>
                            <span>WIN</span>
                          </kbd>
                          <span className="tpf-key-plus">+</span>
                          <kbd className="tpf-key tpf-key-i">I</kbd>
                        </div>
                        <div className="tpf-settings-badge">
                          <Settings size={20} className="tpf-settings-gear" aria-hidden="true" />
                          <span>Windows Settings</span>
                        </div>
                      </div>
                    )}

                    {/* STEP 02 VISUAL */}
                    {step.id === 2 && (
                      <div className="tpf-visual-box tpf-visual-navpath">
                        <div className="tpf-nav-node tpf-nav-node-1">
                          <Bluetooth size={16} aria-hidden="true" />
                          <span>Bluetooth &amp; devices</span>
                        </div>
                        <div className="tpf-nav-arrow" aria-hidden="true">
                          ↓
                        </div>
                        <div className="tpf-nav-node tpf-nav-node-2">
                          <Touchpad size={16} aria-hidden="true" />
                          <span>Touchpad</span>
                        </div>
                      </div>
                    )}

                    {/* STEP 03 VISUAL */}
                    {step.id === 3 && (
                      <div className="tpf-visual-box tpf-visual-gestures">
                        <div className="tpf-mini-touchpad" aria-hidden="true">
                          <div className="tpf-mini-swipe-glow" />
                          <div className="tpf-mini-fingers">
                            <span className="tpf-finger" />
                            <span className="tpf-finger tpf-finger-mid" />
                            <span className="tpf-finger" />
                          </div>
                        </div>
                        <p className="tpf-visual-caption">
                          Windows can use this gesture to open Task View or switch applications.
                        </p>
                      </div>
                    )}

                    {/* STEP 04 VISUAL (MOST IMPORTANT) */}
                    {step.id === 4 && (
                      <div className="tpf-visual-box tpf-visual-compare">
                        <div className="tpf-compare-grid">
                          <div className="tpf-compare-card tpf-compare-before">
                            <span className="tpf-compare-tag">BEFORE</span>
                            <div className="tpf-setting-label">Swipes</div>
                            <div className="tpf-setting-value">Switch apps and show desktop</div>
                          </div>

                          <div className="tpf-compare-card tpf-compare-after">
                            <span className="tpf-compare-tag tpf-tag-after">
                              <Check size={12} aria-hidden="true" />
                              <span>AFTER</span>
                            </span>
                            <div className="tpf-setting-label">Swipes</div>
                            <div className="tpf-setting-value tpf-value-nothing">
                              <span>Nothing</span>
                              <span className="tpf-selected-pill">Selected</span>
                            </div>
                          </div>
                        </div>

                        <p className="tpf-visual-caption tpf-caption-important">
                          Disabling this setting prevents the three-finger swipe from triggering
                          Windows app switching through that gesture. Only change{' '}
                          <strong>Swipes → Nothing</strong> (do not disable the entire touchpad or
                          confuse this with Three-finger taps).
                        </p>
                      </div>
                    )}

                    {/* STEP 05 VISUAL */}
                    {step.id === 5 && (
                      <div className="tpf-visual-box tpf-visual-verify">
                        <ul className="tpf-verify-list">
                          {VERIFICATION_ITEMS.map((item) => (
                            <li key={item}>
                              <span className="tpf-verify-icon" aria-hidden="true">
                                <Check size={13} />
                              </span>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>

                        <div className="tpf-final-reveal">
                          <div className="tpf-final-laptop" aria-hidden="true">
                            <ShieldCheck size={22} />
                            <span>BRAINOVA Focus Mode</span>
                          </div>
                          <div className="tpf-final-heading">FOCUS WITHOUT INTERRUPTIONS</div>
                          <p className="tpf-final-sub">
                            One small setting. A more distraction-free study experience.
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {/* Reversible Guide + Technical Accuracy */}
      <div className="tpf-restore-box">
        <button
          type="button"
          className="tpf-restore-trigger"
          aria-expanded={restoreOpen}
          aria-controls="tpf-restore-content"
          onClick={() => setRestoreOpen((v) => !v)}
          data-testid="tpf-restore-trigger"
        >
          <span className="tpf-restore-title">
            <RotateCcw size={15} aria-hidden="true" />
            <span>Want to restore your previous touchpad gestures?</span>
          </span>
          {restoreOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>

        {restoreOpen && (
          <div id="tpf-restore-content" className="tpf-restore-content">
            <p>
              Open <strong>Windows Settings → Bluetooth &amp; devices → Touchpad → Three-finger
              gestures → Swipes</strong> and select your previous action.
            </p>
            <p className="tpf-restore-note">
              <Info size={14} aria-hidden="true" />
              <span>
                This configuration changes a Windows system-wide setting. It affects other
                applications too, not only BRAINOVA.
              </span>
            </p>
            <p className="tpf-restore-note">
              <Info size={14} aria-hidden="true" />
              <span>
                Designed for Windows 11 devices with compatible Precision Touchpad drivers. Some
                laptops or drivers expose different options—if you cannot find Swipes or Nothing,
                your hardware or driver may not expose that setting. BRAINOVA cannot modify Windows
                Settings from Chrome.
              </span>
            </p>
          </div>
        )}
      </div>
    </section>
  );
};

