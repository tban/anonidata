/**
 * Tipos para las detecciones de PII
 */

export interface Detection {
  index: number
  type: string
  text: string
  bbox: [number, number, number, number] // [x0, y0, x1, y1]
  page_num: number
  confidence: number
  source: string
  isApproved?: boolean
  isRejected?: boolean
}

export interface ReviewState {
  documentPath: string
  preAnonymizedPath: string
  detectionsPath: string
  detections: Detection[]
  approvedIndices: Set<number>
  rejectedIndices: Set<number>
  status: 'pending' | 'reviewing' | 'approved' | 'finalized'
}

export const DETECTION_COLORS: Record<string, string> = {
  DNI: '#ef4444', // red
  NIE: '#ef4444', // red
  PERSON: '#3b82f6', // blue
  NAME_PART: '#60a5fa', // light blue
  NOMBRES_CON_PREFIJO: '#3b82f6', // blue
  NOMBRES_CON_FIRMA: '#3b82f6', // blue
  ADDRESS: '#10b981', // green
  PHONE: '#f59e0b', // amber
  EMAIL: '#8b5cf6', // purple
  IBAN: '#ec4899', // pink
  SIGNATURE: '#6366f1', // indigo
  QR_CODE: '#14b8a6', // teal
  MANUAL: '#f59e0b', // amber - selección manual
  default: '#6b7280' // gray
}

export function getDetectionColor(type: string): string {
  return DETECTION_COLORS[type] || DETECTION_COLORS.default
}
