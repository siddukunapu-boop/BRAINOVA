import React from 'react';
import { BookOpen } from 'lucide-react';
import '../styles/notebook-cover.css';

export const NotebookCoverArtwork: React.FC<{ idPrefix?: string }> = ({ idPrefix = 'nb' }) => (
  <svg
    viewBox="0 0 360 480"
    preserveAspectRatio="xMidYMid slice"
    className="brainova-cover-artwork-svg"
    aria-hidden="true"
  >
    <defs>
      <linearGradient id={`${idPrefix}-navy`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#09102b" />
        <stop offset="55%" stopColor="#070d24" />
        <stop offset="100%" stopColor="#040818" />
      </linearGradient>

      <linearGradient id={`${idPrefix}-crimson-frame`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#ef4444" />
        <stop offset="45%" stopColor="#dc2626" />
        <stop offset="80%" stopColor="#be123c" />
        <stop offset="100%" stopColor="#9333ea" />
      </linearGradient>

      <linearGradient id={`${idPrefix}-trunk`} x1="0.5" y1="1" x2="0.5" y2="0">
        <stop offset="0%" stopColor="#cbd5e1" />
        <stop offset="45%" stopColor="#f8fafc" />
        <stop offset="100%" stopColor="#ffffff" />
      </linearGradient>

      <linearGradient id={`${idPrefix}-gold`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#fde047" />
        <stop offset="55%" stopColor="#f59e0b" />
        <stop offset="100%" stopColor="#ea580c" />
      </linearGradient>

      <linearGradient id={`${idPrefix}-orange`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#fb923c" />
        <stop offset="60%" stopColor="#f97316" />
        <stop offset="100%" stopColor="#dc2626" />
      </linearGradient>

      <linearGradient id={`${idPrefix}-magenta`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#f43f5e" />
        <stop offset="55%" stopColor="#db2777" />
        <stop offset="100%" stopColor="#9333ea" />
      </linearGradient>

      <linearGradient id={`${idPrefix}-green`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#a3e635" />
        <stop offset="55%" stopColor="#22c55e" />
        <stop offset="100%" stopColor="#059669" />
      </linearGradient>

      <linearGradient id={`${idPrefix}-cyan`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#22d3ee" />
        <stop offset="55%" stopColor="#0284c7" />
        <stop offset="100%" stopColor="#1d4ed8" />
      </linearGradient>

      <radialGradient id={`${idPrefix}-center-glow`} cx="50%" cy="54%" r="44%">
        <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.24" />
        <stop offset="55%" stopColor="#f59e0b" stopOpacity="0.08" />
        <stop offset="100%" stopColor="#070d24" stopOpacity="0" />
      </radialGradient>
    </defs>

    {/* Deep Midnight Navy Hardcover Base */}
    <rect width="360" height="480" fill={`url(#${idPrefix}-navy)`} />

    {/* Crimson / Magenta Outer Hardcover Frame */}
    <rect
      x="10"
      y="10"
      width="340"
      height="460"
      rx="14"
      fill="none"
      stroke={`url(#${idPrefix}-crimson-frame)`}
      strokeWidth="9"
    />
    <rect
      x="20"
      y="20"
      width="320"
      height="440"
      rx="9"
      fill="none"
      stroke="rgba(244, 63, 94, 0.35)"
      strokeWidth="1.5"
    />

    {/* Subtle Cosmic Glow Behind Tree */}
    <circle cx="180" cy="250" r="165" fill={`url(#${idPrefix}-center-glow)`} />

    {/* Cosmic Stars & Sparkles */}
    <g>
      {/* 5-point stars */}
      <polygon
        points="58,125 61,132 69,132 63,137 65,144 58,140 51,144 53,137 47,132 55,132"
        fill="#f8fafc"
      />
      <polygon
        points="304,132 307,139 315,139 309,144 311,151 304,147 297,151 299,144 293,139 301,139"
        fill="#fde047"
      />
      <polygon
        points="62,365 65,373 74,373 67,378 69,386 62,381 55,386 57,378 50,373 59,373"
        fill="#fb923c"
      />
      <polygon
        points="292,374 295,382 304,382 297,387 299,395 292,390 285,395 287,387 280,382 289,382"
        fill="#f97316"
      />
      <polygon
        points="52,258 54,264 60,264 55,268 57,274 52,270 47,274 49,268 44,264 50,264"
        fill="#e2e8f0"
      />
      <polygon
        points="310,270 312,276 318,276 313,280 315,286 310,282 305,286 307,280 302,276 308,276"
        fill="#38bdf8"
      />

      {/* Glowing dots & tiny cosmic sparkles */}
      <circle cx="92" cy="108" r="2.2" fill="#fde047" />
      <circle cx="268" cy="108" r="2.2" fill="#f43f5e" />
      <circle cx="44" cy="182" r="2" fill="#38bdf8" />
      <circle cx="318" cy="195" r="2" fill="#a3e635" />
      <circle cx="82" cy="402" r="2.3" fill="#38bdf8" />
      <circle cx="275" cy="408" r="2.3" fill="#fde047" />
      <circle cx="132" cy="96" r="1.8" fill="#f8fafc" />
      <circle cx="232" cy="98" r="1.8" fill="#fb923c" />
      <circle cx="180" cy="84" r="2.5" fill="#fde047" />
      <circle cx="98" cy="240" r="1.8" fill="#22d3ee" />
      <circle cx="264" cy="242" r="1.8" fill="#f472b6" />
      <circle cx="118" cy="414" r="1.8" fill="#06b6d4" />
      <circle cx="242" cy="414" r="1.8" fill="#06b6d4" />
    </g>

    {/* Open Book at Lower Center (Crimson/Blue Cover + White/Silver Curved Pages) */}
    <g transform="translate(0, 12)">
      {/* Cyan & Blue Cosmic Swirls Beneath Book */}
      <path
        d="M 55 348 Q 110 385 180 386 Q 250 385 305 348"
        fill="none"
        stroke="#0284c7"
        strokeWidth="5"
        strokeLinecap="round"
        opacity="0.85"
      />
      <path
        d="M 75 362 Q 130 396 180 397 Q 230 396 285 362"
        fill="none"
        stroke="#06b6d4"
        strokeWidth="3"
        strokeLinecap="round"
        opacity="0.7"
      />

      {/* Crimson Book Outer Binding */}
      <path
        d="M 62 328 Q 120 344 176 370 L 184 370 Q 240 344 298 328 L 292 340 Q 236 358 180 382 Q 124 358 68 340 Z"
        fill="#dc2626"
      />
      {/* Gold Spine Clasp */}
      <polygon points="170,364 190,364 194,378 180,384 166,378" fill={`url(#${idPrefix}-gold)`} />

      {/* Left Book Pages (White & Silver Layered Curves) */}
      <path
        d="M 178 360 C 145 332 105 316 62 316 L 80 280 C 122 282 156 306 178 342 Z"
        fill="#f8fafc"
      />
      <path
        d="M 176 355 C 142 325 104 307 68 306"
        fill="none"
        stroke="#94a3b8"
        strokeWidth="2.5"
      />
      <path
        d="M 176 347 C 144 316 108 296 74 295"
        fill="none"
        stroke="#cbd5e1"
        strokeWidth="2.5"
      />
      <path
        d="M 176 339 C 146 306 112 287 82 286"
        fill="none"
        stroke="#94a3b8"
        strokeWidth="2"
      />

      {/* Right Book Pages (White & Silver Layered Curves) */}
      <path
        d="M 182 360 C 215 332 255 316 298 316 L 280 280 C 238 282 204 306 182 342 Z"
        fill="#f8fafc"
      />
      <path
        d="M 184 355 C 218 325 256 307 292 306"
        fill="none"
        stroke="#94a3b8"
        strokeWidth="2.5"
      />
      <path
        d="M 184 347 C 216 316 252 296 286 295"
        fill="none"
        stroke="#cbd5e1"
        strokeWidth="2.5"
      />
      <path
        d="M 184 339 C 214 306 248 287 278 286"
        fill="none"
        stroke="#94a3b8"
        strokeWidth="2"
      />

      {/* Blue Sky/Page Accents Inside Open Book */}
      <path
        d="M 102 276 C 128 264 156 278 172 316 C 144 294 122 284 102 276 Z"
        fill={`url(#${idPrefix}-cyan)`}
      />
      <path
        d="M 258 276 C 232 264 204 278 188 316 C 216 294 238 284 258 276 Z"
        fill={`url(#${idPrefix}-cyan)`}
      />
      <circle cx="136" cy="282" r="2.2" fill="#ffffff" />
      <circle cx="224" cy="282" r="2.2" fill="#ffffff" />
    </g>

    {/* White & Silver Tree Trunk Growing From Center of Open Book */}
    <path
      d="M 176 358 C 175 315 170 278 152 246 C 166 255 175 268 178 286 C 180 245 186 205 212 162 C 198 205 190 244 190 282 C 202 262 216 248 232 240 C 210 264 196 294 192 332 L 184 360 Z"
      fill={`url(#${idPrefix}-trunk)`}
    />
    {/* Secondary Graceful Branches */}
    <path
      d="M 178 258 C 160 232 138 214 118 206 C 140 220 158 238 175 266 Z"
      fill="#e2e8f0"
    />
    <path
      d="M 188 248 C 208 224 232 208 252 202 C 230 218 208 236 190 262 Z"
      fill="#e2e8f0"
    />

    {/* Vibrant Colourful Leaf Canopy */}
    <g>
      {/* Top Crown — Golden Yellow & Bright Orange */}
      <path d="M 180 96 C 168 118 168 142 180 156 C 192 142 192 118 180 96 Z" fill={`url(#${idPrefix}-gold)`} />
      <path d="M 152 106 C 146 130 154 152 170 164 C 174 144 168 122 152 106 Z" fill={`url(#${idPrefix}-orange)`} />
      <path d="M 208 106 C 214 130 206 152 190 164 C 186 144 192 122 208 106 Z" fill={`url(#${idPrefix}-gold)`} />

      {/* Outer Upper Canopy — Crimson & Magenta */}
      <path d="M 124 122 C 122 146 136 168 156 176 C 154 154 142 134 124 122 Z" fill={`url(#${idPrefix}-magenta)`} />
      <path d="M 236 122 C 238 146 224 168 204 176 C 206 154 218 134 236 122 Z" fill={`url(#${idPrefix}-magenta)`} />
      <path d="M 96 146 C 102 170 122 186 144 188 C 136 168 118 152 96 146 Z" fill={`url(#${idPrefix}-orange)`} />
      <path d="M 264 146 C 258 170 238 186 216 188 C 224 168 242 152 264 146 Z" fill={`url(#${idPrefix}-orange)`} />

      {/* Mid Canopy — Warm Gold, Orange & Coral */}
      <path d="M 164 148 C 152 168 154 192 168 206 C 178 188 178 166 164 148 Z" fill={`url(#${idPrefix}-gold)`} />
      <path d="M 196 148 C 208 168 206 192 192 206 C 182 188 182 166 196 148 Z" fill={`url(#${idPrefix}-orange)`} />
      <path d="M 134 168 C 128 190 140 212 158 218 C 160 198 150 178 134 168 Z" fill={`url(#${idPrefix}-gold)`} />
      <path d="M 226 168 C 232 190 220 212 202 218 C 200 198 210 178 226 168 Z" fill={`url(#${idPrefix}-gold)`} />
      <path d="M 76 178 C 88 198 110 208 134 206 C 122 188 100 178 76 178 Z" fill={`url(#${idPrefix}-magenta)`} />
      <path d="M 284 178 C 272 198 250 208 226 206 C 238 188 260 178 284 178 Z" fill={`url(#${idPrefix}-magenta)`} />

      {/* Lower-Mid Canopy — Emerald & Lime Green */}
      <path d="M 70 212 C 88 228 114 232 138 224 C 120 208 94 204 70 212 Z" fill={`url(#${idPrefix}-green)`} />
      <path d="M 290 212 C 272 228 246 232 222 224 C 240 208 266 204 290 212 Z" fill={`url(#${idPrefix}-green)`} />
      <path d="M 102 228 C 114 246 138 252 158 244 C 144 226 122 220 102 228 Z" fill={`url(#${idPrefix}-green)`} />
      <path d="M 258 228 C 246 246 222 252 202 244 C 216 226 238 220 258 228 Z" fill={`url(#${idPrefix}-green)`} />
      <path d="M 142 208 C 138 228 150 246 168 250 C 168 232 158 216 142 208 Z" fill={`url(#${idPrefix}-green)`} />
      <path d="M 218 208 C 222 228 210 246 192 250 C 192 232 202 216 218 208 Z" fill={`url(#${idPrefix}-green)`} />

      {/* Lower Canopy — Rich Cyan & Royal Blue */}
      <path d="M 78 248 C 98 260 124 260 144 250 C 124 240 98 240 78 248 Z" fill={`url(#${idPrefix}-cyan)`} />
      <path d="M 282 248 C 262 260 236 260 216 250 C 236 240 262 240 282 248 Z" fill={`url(#${idPrefix}-cyan)`} />
      <path d="M 118 262 C 134 274 156 274 170 264 C 154 252 134 252 118 262 Z" fill={`url(#${idPrefix}-cyan)`} />
      <path d="M 242 262 C 226 274 204 274 190 264 C 206 252 226 252 242 262 Z" fill={`url(#${idPrefix}-cyan)`} />
    </g>
  </svg>
);

interface SharedNotebookCoverProps {
  badge: string;
  title: string;
  subtitle: string;
  ariaLabel: string;
  idPrefix: string;
  onOpen: () => void;
}

export const SharedNotebookCover: React.FC<SharedNotebookCoverProps> = ({
  badge,
  title,
  subtitle,
  ariaLabel,
  idPrefix,
  onOpen,
}) => (
  <div className="brainova-cover-stage">
    <button
      type="button"
      className="brainova-closed-book"
      onClick={onOpen}
      aria-label={ariaLabel}
    >
      <div className="brainova-cover-artwork-layer">
        <NotebookCoverArtwork idPrefix={idPrefix} />
      </div>

      <div className="brainova-cover-top-bar">
        <div className="brainova-cover-badge">{badge}</div>
        <h2 className="brainova-cover-title">{title}</h2>
        <p className="brainova-cover-subtitle">{subtitle}</p>
      </div>

      <div className="brainova-cover-bottom-bar">
        <span className="brainova-cover-cta">
          <BookOpen size={16} className="shrink-0" />
          <span>Open Notebook</span>
        </span>
      </div>

      <div className="brainova-ribbon-bookmark" aria-hidden="true" />
    </button>
  </div>
);

export const SharedNotebookOpeningFlap: React.FC<{ idPrefix: string }> = ({ idPrefix }) => (
  <div className="brainova-opening-flap" aria-hidden="true">
    <NotebookCoverArtwork idPrefix={`${idPrefix}-flap`} />
  </div>
);

