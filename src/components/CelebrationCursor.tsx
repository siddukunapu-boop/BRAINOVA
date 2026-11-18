import React, { useEffect, useRef, useState } from 'react';

const SPARKLE_POOL_SIZE = 24;
const MOVE_SPARKLE_DISTANCE_PX = 16;
const MOVE_SPARKLE_COOLDOWN_MS = 32;
const CLICK_BURST_COUNT = 5;

const TEXT_INPUT_TYPES = new Set([
  'text',
  'email',
  'password',
  'search',
  'url',
  'tel',
  'number',
]);

const SPECIAL_CURSORS = new Set([
  'grab',
  'grabbing',
  'col-resize',
  'row-resize',
  'ew-resize',
  'ns-resize',
  'nesw-resize',
  'nwse-resize',
  'move',
  'not-allowed',
  'wait',
  'progress',
  'crosshair',
]);

const SPARKLE_TONES = ['gold', 'champagne', 'ivory'] as const;

function isTextEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  if (target.closest('textarea, [contenteditable="true"], [contenteditable=""]')) {
    return true;
  }
  const input = target.closest('input');
  if (input instanceof HTMLInputElement) {
    const t = (input.type || 'text').toLowerCase();
    return TEXT_INPUT_TYPES.has(t);
  }
  return false;
}

function isInteractiveTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  return Boolean(
    target.closest(
      'a, button, [role="button"], [role="tab"], summary, label[for], select, .btn, .nav-item, .mfs-focus-card, .auth-mode-tab'
    )
  );
}

function hasSpecializedNativeCursor(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  if (target.closest('[draggable="true"]')) return true;
  try {
    const cursor = window.getComputedStyle(target).cursor;
    return SPECIAL_CURSORS.has(cursor);
  } catch {
    return false;
  }
}

export const CelebrationCursor: React.FC = () => {
  const [enabled, setEnabled] = useState<boolean>(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return !window.matchMedia('(pointer: coarse)').matches && !window.matchMedia('(hover: none)').matches;
  });

  const layerRef = useRef<HTMLDivElement | null>(null);
  const haloRef = useRef<HTMLDivElement | null>(null);
  const coreRef = useRef<HTMLDivElement | null>(null);
  const ringRef = useRef<HTMLDivElement | null>(null);
  const sparkleRefs = useRef<Array<HTMLSpanElement | null>>([]);

  const pointerRef = useRef({
    x: -100,
    y: -100,
    haloX: -100,
    haloY: -100,
    lastSparkleX: -100,
    lastSparkleY: -100,
    lastSparkleAt: 0,
    visible: false,
    dragging: false,
    poolIndex: 0,
  });

  const rafIdRef = useRef<number | null>(null);
  const reducedMotionRef = useRef<boolean>(false);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const coarseMql = window.matchMedia('(pointer: coarse)');
    const hoverNoneMql = window.matchMedia('(hover: none)');
    const motionMql = window.matchMedia('(prefers-reduced-motion: reduce)');

    const syncDevice = () => {
      setEnabled(!coarseMql.matches && !hoverNoneMql.matches);
    };
    const syncMotion = () => {
      const bodyReduced = document.body?.getAttribute('data-reduced-motion') === 'true';
      reducedMotionRef.current = motionMql.matches || bodyReduced;
    };

    syncDevice();
    syncMotion();

    coarseMql.addEventListener?.('change', syncDevice);
    hoverNoneMql.addEventListener?.('change', syncDevice);
    motionMql.addEventListener?.('change', syncMotion);

    const observer = new MutationObserver(syncMotion);
    if (document.body) {
      observer.observe(document.body, {
        attributes: true,
        attributeFilter: ['data-reduced-motion'],
      });
    }

    return () => {
      coarseMql.removeEventListener?.('change', syncDevice);
      hoverNoneMql.removeEventListener?.('change', syncDevice);
      motionMql.removeEventListener?.('change', syncMotion);
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    if (!enabled) return;

    const layer = layerRef.current;
    const halo = haloRef.current;
    const core = coreRef.current;
    if (!layer || !halo || !core) return;

    const spawnSparkle = (x: number, y: number, angle: number, dist: number, size: number, durationMs: number) => {
      if (reducedMotionRef.current) return;
      const idx = pointerRef.current.poolIndex % SPARKLE_POOL_SIZE;
      pointerRef.current.poolIndex = (idx + 1) % SPARKLE_POOL_SIZE;
      const el = sparkleRefs.current[idx];
      if (!el) return;

      const tone = SPARKLE_TONES[idx % SPARKLE_TONES.length];
      const isStar = idx % 2 === 0;
      const dx1 = Math.cos(angle) * (dist * 0.45);
      const dy1 = Math.sin(angle) * (dist * 0.45);
      const dx2 = Math.cos(angle) * dist;
      const dy2 = Math.sin(angle) * dist + 6;

      el.className = `sc-sparkle ${isStar ? 'sc-sparkle--star' : ''} sc-sparkle--${tone}`;
      el.style.width = `${size}px`;
      el.style.height = `${size}px`;
      el.style.marginLeft = `${-size / 2}px`;
      el.style.marginTop = `${-size / 2}px`;
      el.style.setProperty('--sc-dur', `${durationMs}ms`);
      el.style.setProperty('--sc-x0', `${x}px`);
      el.style.setProperty('--sc-y0', `${y}px`);
      el.style.setProperty('--sc-x1', `${x + dx1}px`);
      el.style.setProperty('--sc-y1', `${y + dy1}px`);
      el.style.setProperty('--sc-x2', `${x + dx2}px`);
      el.style.setProperty('--sc-y2', `${y + dy2}px`);

      // Force clean restart for pooled CSS animation
      void el.offsetWidth;
      el.classList.add('is-active');
    };

    const tick = () => {
      const p = pointerRef.current;
      if (reducedMotionRef.current) {
        p.haloX = p.x;
        p.haloY = p.y;
      } else {
        p.haloX += (p.x - p.haloX) * 0.24;
        p.haloY += (p.y - p.haloY) * 0.24;
      }

      halo.style.transform = `translate3d(${p.haloX}px, ${p.haloY}px, 0)`;

      if (
        p.visible &&
        !reducedMotionRef.current &&
        (Math.abs(p.x - p.haloX) > 0.25 || Math.abs(p.y - p.haloY) > 0.25)
      ) {
        rafIdRef.current = window.requestAnimationFrame(tick);
      } else {
        p.haloX = p.x;
        p.haloY = p.y;
        halo.style.transform = `translate3d(${p.haloX}px, ${p.haloY}px, 0)`;
        rafIdRef.current = null;
      }
    };

    const scheduleTick = () => {
      if (rafIdRef.current === null) {
        rafIdRef.current = window.requestAnimationFrame(tick);
      }
    };

    const onPointerMove = (e: PointerEvent) => {
      if (e.pointerType === 'touch') {
        layer.classList.remove('is-visible');
        return;
      }

      const p = pointerRef.current;
      const firstShow = !p.visible;
      p.x = e.clientX;
      p.y = e.clientY;
      p.visible = true;

      if (firstShow) {
        p.haloX = p.x;
        p.haloY = p.y;
        p.lastSparkleX = p.x;
        p.lastSparkleY = p.y;
        halo.style.transform = `translate3d(${p.haloX}px, ${p.haloY}px, 0)`;
      }

      core.style.transform = `translate3d(${p.x}px, ${p.y}px, 0)`;
      layer.classList.add('is-visible');

      const isText = isTextEditableTarget(e.target);
      const isSpecial = p.dragging || hasSpecializedNativeCursor(e.target);
      const isInteractive = !isText && !isSpecial && isInteractiveTarget(e.target);

      layer.classList.toggle('is-text-target', isText);
      layer.classList.toggle('is-native-priority', isSpecial);
      layer.classList.toggle('is-interactive', isInteractive);

      scheduleTick();

      if (!isText && !isSpecial && !reducedMotionRef.current) {
        const now = performance.now();
        const dist = Math.hypot(p.x - p.lastSparkleX, p.y - p.lastSparkleY);
        if (dist >= MOVE_SPARKLE_DISTANCE_PX && now - p.lastSparkleAt >= MOVE_SPARKLE_COOLDOWN_MS) {
          p.lastSparkleX = p.x;
          p.lastSparkleY = p.y;
          p.lastSparkleAt = now;
          const angle = Math.random() * Math.PI * 2;
          const size = 4 + (p.poolIndex % 3);
          spawnSparkle(p.x, p.y, angle, 12 + Math.random() * 10, size, 480);
        }
      }
    };

    const onPointerDown = (e: PointerEvent) => {
      if (e.pointerType === 'touch' || e.button !== 0) return;
      layer.classList.add('is-pressed');

      if (reducedMotionRef.current || isTextEditableTarget(e.target) || pointerRef.current.dragging) {
        return;
      }

      const ring = ringRef.current;
      if (ring) {
        ring.classList.remove('is-active');
        ring.style.setProperty('--sc-rx', `${e.clientX}px`);
        ring.style.setProperty('--sc-ry', `${e.clientY}px`);
        void ring.offsetWidth;
        ring.classList.add('is-active');
      }

      const baseAngle = Math.random() * Math.PI * 2;
      for (let i = 0; i < CLICK_BURST_COUNT; i += 1) {
        const angle = baseAngle + (i * Math.PI * 2) / CLICK_BURST_COUNT + (Math.random() - 0.5) * 0.35;
        const size = i % 2 === 0 ? 6 : 4;
        spawnSparkle(e.clientX, e.clientY, angle, 18 + Math.random() * 14, size, 520);
      }
    };

    const onPointerUp = () => {
      layer.classList.remove('is-pressed');
    };

    const hideCursor = () => {
      pointerRef.current.visible = false;
      layer.classList.remove('is-visible', 'is-pressed', 'is-interactive');
    };

    const onDragStart = () => {
      pointerRef.current.dragging = true;
      layer.classList.add('is-native-priority');
    };

    const onDragEnd = () => {
      pointerRef.current.dragging = false;
      layer.classList.remove('is-native-priority');
    };

    window.addEventListener('pointermove', onPointerMove, { passive: true });
    window.addEventListener('pointerdown', onPointerDown, { passive: true });
    window.addEventListener('pointerup', onPointerUp, { passive: true });
    window.addEventListener('blur', hideCursor);
    document.addEventListener('mouseleave', hideCursor);
    document.addEventListener('dragstart', onDragStart, { passive: true });
    document.addEventListener('dragend', onDragEnd, { passive: true });

    return () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('blur', hideCursor);
      document.removeEventListener('mouseleave', hideCursor);
      document.removeEventListener('dragstart', onDragStart);
      document.removeEventListener('dragend', onDragEnd);
      if (rafIdRef.current !== null) {
        window.cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
  }, [enabled]);

  if (!enabled) return null;

  return (
    <div
      ref={layerRef}
      className="sc-cursor-layer"
      aria-hidden="true"
      data-testid="studyos-celebration-cursor"
    >
      <div ref={haloRef} className="sc-cursor-halo" />
      <div ref={coreRef} className="sc-cursor-core" />
      <div
        ref={ringRef}
        className="sc-click-ring"
        onAnimationEnd={(e) => e.currentTarget.classList.remove('is-active')}
      />
      {Array.from({ length: SPARKLE_POOL_SIZE }).map((_, idx) => (
        <span
          key={idx}
          ref={(el) => {
            sparkleRefs.current[idx] = el;
          }}
          className="sc-sparkle"
          onAnimationEnd={(e) => e.currentTarget.classList.remove('is-active')}
        />
      ))}
    </div>
  );
};
