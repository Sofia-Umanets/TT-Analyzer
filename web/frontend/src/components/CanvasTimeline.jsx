import React, { useRef, useEffect, useCallback } from 'react'

const PHASE_COLORS = ['#9ca3af', '#7dd3fc', '#f87171', '#86efac']
const PHASE_NAMES = ['idle', 'backswing', 'contact', 'follow_through']

/**
 * Canvas-таймлайн с покадровой отрисовкой фаз.
 * Каждый пиксель = кадр (или группа кадров).
 */
export default function CanvasTimeline({
  currentFrame, totalFrames, fps,
  phases, strokes, onSeek,
  activeStrokeId,
  markers,  // { start, contact, end }
}) {
  const canvasRef = useRef(null)

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || totalFrames <= 0) return

    const ctx = canvas.getContext('2d')
    const w = canvas.width
    const h = canvas.height

    ctx.clearRect(0, 0, w, h)

    // Фон
    ctx.fillStyle = '#1f2937'
    ctx.fillRect(0, 0, w, h)

    // Фазы — покадрово
    if (phases && phases.length > 0) {
      const framesPerPixel = totalFrames / w
      for (let px = 0; px < w; px++) {
        const frame = Math.floor(px * framesPerPixel)
        const phase = phases[Math.min(frame, phases.length - 1)]
        ctx.fillStyle = PHASE_COLORS[phase] || '#666'
        ctx.globalAlpha = 0.6
        ctx.fillRect(px, 0, 1, h * 0.6)
      }
      ctx.globalAlpha = 1
    }

    // Удары — полоски
    if (strokes) {
      for (const s of strokes) {
        const x1 = Math.floor((s.start_frame / totalFrames) * w)
        const x2 = Math.floor((s.end_frame / totalFrames) * w)
        const isActive = s.id === activeStrokeId

        ctx.strokeStyle = isActive ? '#facc15' : 'rgba(255,255,255,0.4)'
        ctx.lineWidth = isActive ? 2 : 1
        ctx.strokeRect(x1, h * 0.62, Math.max(x2 - x1, 2), h * 0.18)

        if (isActive) {
          ctx.fillStyle = 'rgba(250,204,21,0.15)'
          ctx.fillRect(x1, h * 0.62, Math.max(x2 - x1, 2), h * 0.18)
        }

        // Номер удара
        if (x2 - x1 > 15) {
          ctx.fillStyle = isActive ? '#facc15' : '#9ca3af'
          ctx.font = '9px monospace'
          ctx.fillText(`#${s.id}`, x1 + 2, h * 0.62 + 12)
        }
      }
    }

    // Маркеры разметки
    if (markers) {
      const drawMarker = (frame, color) => {
        if (frame == null) return
        const x = Math.floor((frame / totalFrames) * w)
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, h)
        ctx.stroke()
      }
      drawMarker(markers.start, '#4ade80')   // зелёный
      drawMarker(markers.contact, '#facc15') // жёлтый
      drawMarker(markers.end, '#f87171')     // красный
    }

    // Курсор текущего кадра
    const cx = Math.floor((currentFrame / totalFrames) * w)
    ctx.strokeStyle = '#ffffff'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(cx, 0)
    ctx.lineTo(cx, h)
    ctx.stroke()

    // Кружок курсора
    ctx.fillStyle = '#ffffff'
    ctx.beginPath()
    ctx.arc(cx, 4, 4, 0, Math.PI * 2)
    ctx.fill()

  }, [currentFrame, totalFrames, phases, strokes, activeStrokeId, markers])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    // Подгоняем размер canvas под контейнер
    const rect = canvas.parentElement.getBoundingClientRect()
    canvas.width = rect.width
    canvas.height = 60
    draw()
  }, [draw])

  // Перерисовка при ресайзе
  useEffect(() => {
    const handler = () => {
      const canvas = canvasRef.current
      if (!canvas) return
      const rect = canvas.parentElement.getBoundingClientRect()
      canvas.width = rect.width
      canvas.height = 60
      draw()
    }
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [draw])

  const handleClick = useCallback((e) => {
    const canvas = canvasRef.current
    if (!canvas || totalFrames <= 0) return
    const rect = canvas.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const frame = Math.round(x * totalFrames)
    onSeek(Math.max(0, Math.min(frame, totalFrames - 1)))
  }, [totalFrames, onSeek])

  return (
    <div className="space-y-1">
      <div className="w-full cursor-pointer" onClick={handleClick}>
        <canvas ref={canvasRef} className="w-full rounded" style={{ height: 60 }} />
      </div>
      {phases && phases.length > 0 && (
        <div className="flex gap-3 text-xs text-gray-400">
          {PHASE_NAMES.map((name, i) => (
            <span key={name} className="flex items-center gap-1">
              <span className="w-3 h-2 rounded-sm inline-block" style={{ backgroundColor: PHASE_COLORS[i] }} />
              {name}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}