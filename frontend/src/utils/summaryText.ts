import type { SummaryCard } from '../types/api'

export type Lang = 'bn' | 'en'

/** Plain-text rendering of the summary for the clipboard. */
export function summaryToText(s: SummaryCard, lang: Lang): string {
  const bn = lang === 'bn'
  const lines: string[] = []
  lines.push(bn ? s.label_bn : s.label_en)
  lines.push(`${bn ? 'সময়' : 'Generated'}: ${new Date(s.generated_at).toLocaleString(bn ? 'bn-BD' : 'en-GB')}`)
  if (s.mode === 'demo') lines.push(bn ? 'ডেমো: প্রস্তুত নমুনা, লাইভ এআই নয়' : 'DEMO: prepared sample, not live AI output')
  lines.push('')
  if (s.red_flags.length) {
    lines.push(bn ? '!! লাল পতাকা (নিয়মভিত্তিক) !!' : '!! RED FLAGS (rule-based) !!')
    for (const r of s.red_flags) {
      lines.push(`- ${bn ? r.name_bn : r.name_en}: ${bn ? r.explanation_bn : r.explanation_en} ${bn ? r.recommended_action_bn : r.recommended_action_en}`)
    }
    lines.push('')
  }
  for (const sec of s.sections) {
    lines.push(`${bn ? sec.title_bn : sec.title_en}:`)
    for (const v of bn ? sec.bn : sec.en) lines.push(`  - ${v}`)
  }
  lines.push('')
  lines.push(`${bn ? 'রোগীর মূল বক্তব্য' : 'Original patient statement'}: ${s.original_statement}`)
  lines.push(`${bn ? 'প্রমিত বাংলায়' : 'Normalized statement'}: ${s.normalized_statement}`)
  lines.push(`${bn ? 'নিশ্চিতকৃত বক্তব্য' : 'Confirmed statement'}: ${s.confirmed_statement || s.normalized_statement}`)
  lines.push('')
  lines.push(bn ? s.disclaimer_bn : s.disclaimer_en)
  return lines.join('\n')
}
