import { useEffect, useState } from 'react';

export type BrainovaLogoVariant = 'sidebar' | 'topbar' | 'auth';

interface BrainovaLogoProps {
  size?: number;
  variant?: BrainovaLogoVariant;
  alt?: string;
}

// Track initial application load so entrance animation does not replay on route changes or rerenders.
let initialEntranceCompleted = false;

const GOLD_MOTES = [1, 2, 3, 4, 5, 6] as const;
const GOLD_SPARKS = [1, 2, 3, 4, 5, 6, 7, 8] as const;

export function BrainovaLogo({
  size = 38,
  variant = 'sidebar',
  alt = 'BRAINOVA Logo',
}: BrainovaLogoProps) {
  const [shouldAnimateEntrance] = useState(() => !initialEntranceCompleted);

  useEffect(() => {
    if (initialEntranceCompleted) return;
    const timer = window.setTimeout(() => {
      initialEntranceCompleted = true;
    }, 650);
    return () => window.clearTimeout(timer);
  }, []);

  const radius = variant === 'auth' ? 12 : 10;

  return (
    <span
      className={`brainova-logo-stage brainova-logo-stage--${variant}${shouldAnimateEntrance ? ' is-entering' : ''}`}
      style={{ width: size, height: size }}
    >
      <span className="brainova-logo-ambient" aria-hidden="true">
        {GOLD_MOTES.map((mote) => (
          <span key={mote} className={`brainova-gold-mote brainova-gold-mote--${mote}`} />
        ))}
      </span>

      <span className="brainova-logo-sparks" aria-hidden="true">
        {GOLD_SPARKS.map((spark) => (
          <span key={spark} className={`brainova-gold-spark brainova-gold-spark--${spark}`} />
        ))}
      </span>

      <span
        className={`brainova-logo-wrap brainova-logo-wrap--${variant}`}
        style={{ borderRadius: radius }}
      >
        <img
          src="/brainova-logo.jpg"
          alt={alt}
          className="brainova-logo-img"
          draggable={false}
        />
      </span>
    </span>
  );
}
