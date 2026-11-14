export interface TechPulseSourceRef {
  name: string;
  url: string;
  is_official?: boolean;
  discovered_at?: string;
}

export interface TechPulseSummary {
  what_happened?: string;
  important_details?: string[];
  why_it_matters?: string;
  student_perspective?: string;
  technical_explanation?: string;
  what_happens_next?: string;
  is_ai_enriched?: boolean;
  fallback_notice?: string;
}

export interface TechPulseStory {
  id: string;
  title: string;
  category: string;
  verification_status:
    | 'Verified primary source'
    | 'Independently corroborated'
    | 'Unconfirmed report'
    | 'Corrected'
    | string;
  correction_note?: string;
  original_source_name: string;
  original_source_url: string;
  supporting_sources: TechPulseSourceRef[];
  published_at_utc: string;
  published_at_ist: string;
  discovered_at_utc: string;
  discovered_at_ist: string;
  processed_at_utc?: string;
  is_late_update: boolean;
  late_update_label: string;
  summary: TechPulseSummary;
  is_saved: boolean;
  ist_date: string;
  saved_at?: string;
}

export interface TechPulseFeedResponse {
  ist_date: string;
  ist_display_date: string;
  timezone: string;
  total: number;
  stories: TechPulseStory[];
  categories: string[];
  last_collection_at: string;
  last_collection_status: string;
  active_source_count: number;
}

export function isSafeExternalUrl(url: string | undefined | null): boolean {
  if (!url || typeof url !== 'string') return false;
  const trimmed = url.trim();
  if (!trimmed) return false;
  try {
    const parsed = new URL(trimmed);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export function getVerificationBadgeTone(status: string): 'verified' | 'corroborated' | 'unconfirmed' | 'corrected' {
  if (status === 'Verified primary source') return 'verified';
  if (status === 'Independently corroborated') return 'corroborated';
  if (status === 'Corrected') return 'corrected';
  return 'unconfirmed';
}

export function filterTechPulseStories(
  stories: TechPulseStory[],
  options: {
    category?: string;
    verifiedOnly?: boolean;
    query?: string;
  }
): TechPulseStory[] {
  const cat = options.category || 'All';
  const verifiedOnly = Boolean(options.verifiedOnly);
  const q = (options.query || '').trim().toLowerCase();

  return stories.filter((story) => {
    if (cat !== 'All' && story.category !== cat) return false;
    if (
      verifiedOnly &&
      story.verification_status !== 'Verified primary source' &&
      story.verification_status !== 'Independently corroborated'
    ) {
      return false;
    }
    if (q) {
      const hay = [
        story.title,
        story.original_source_name,
        story.category,
        story.summary?.what_happened || '',
        story.summary?.why_it_matters || '',
      ]
        .join(' ')
        .toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

