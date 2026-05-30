import React from 'react'

const PHASE_COLORS = ['#9ca3af', '#7dd3fc', '#f87171', '#86efac']
const PHASE_NAMES = ['idle', 'замах', 'контакт', 'завершение']

/**
 * Полоска фаз для одного удара.
 */
export default function PhaseStrip({ phases, startFrame, endFrame }) {
  if (!phases || startFrame == null || endFrame == null) return null

  const strokePhases = phases.slice(startFrame, endFrame + 1)
  if (strokePhases.length === 0) return null

  return (
    <div className="space-y-1">
      <div className="flex h-4 rounded overflow-hidden">
        {strokePhases.map((p, i) => (
          <div
            key={i}
            className="h-full"
            style={{
              backgroundColor: PHASE_COLORS[p] || '#4b5563',
              flex: 1,
              minWidth: 1,
            }}
            title={`Кадр ${startFrame + i}: ${PHASE_NAMES[p] || '?'}`}
          />
        ))}
      </div>
      <div className="flex justify-between text-xs text-gray-500">
        <span>{startFrame}</span>
        <span>{endFrame}</span>
      </div>
    </div>
  )
}