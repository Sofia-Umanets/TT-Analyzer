import React, { useRef, useEffect, useCallback } from 'react'

const PHASE_COLORS = {
  0: '#9ca3af',
  1: '#7dd3fc',
  2: '#f87171',
  3: '#86efac',
}

/**
 * Двухслойный canvas-таймлайн.
 *
 * bgCanvas — фазы, удары, маркеры S/C/E. Рисуется только при смене данных.
 * fgCanvas — линия текущего кадра. Обновляется через RAF, читая v.currentTime
 *            напрямую — без React-рендеров при каждом кадре.
 *
 * Props: videoRef + fps вместо currentFrame (так же как в web1, где _annCurrentFrame
 * обновляется прямо в _onSeeked/_startRVFC, минуя React).
 */
export default function Timeline({
  totalFrames,
  videoRef,       // прямая ссылка на <video> — для RAF
  fps,            // для вычисления кадра из currentTime
  phases,
  strokes,
  currentStroke,
  onSeek,
}) {
  const bgCanvasRef     = useRef(null)
  const fgCanvasRef     = useRef(null)
  const containerRef    = useRef(null)
  const lastDrawnFrame  = useRef(-1)  // локальный трекер для RAF, не вызывает ре-рендер

  // ── helpers ──────────────────────────────────────────────────────────────

  const getSize = () => {
    const container = containerRef.current
    if (!container) return null
    const rect = container.getBoundingClientRect()
    const dpr  = window.devicePixelRatio || 1
    return { W: rect.width, H: 60, dpr,
             newW: Math.round(rect.width * dpr), newH: Math.round(60 * dpr) }
  }

  const syncSize = (canvas, sz) => {
    if (!canvas || !sz) return
    if (canvas.width !== sz.newW || canvas.height !== sz.newH) {
      canvas.width        = sz.newW
      canvas.height       = sz.newH
      canvas.style.width  = sz.W + 'px'
      canvas.style.height = sz.H + 'px'
    }
  }

  // ── bg: фазы + удары + маркеры S/C/E ────────────────────────────────────

  const drawBg = useCallback(() => {
    const bg  = bgCanvasRef.current
    const sz  = getSize()
    if (!bg || !sz || totalFrames <= 0) return
    syncSize(bg, sz)
    syncSize(fgCanvasRef.current, sz)

    const { W, H, dpr } = sz
    const ctx = bg.getContext('2d')
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.fillStyle = '#1f2937'
    ctx.fillRect(0, 0, W, H)

    const fx = (f) => (f / totalFrames) * W

    if (phases?.length > 0) {
      let blockStart = 0, blockPhase = phases[0] || 0
      for (let i = 1; i <= phases.length; i++) {
        const p = i < phases.length ? (phases[i] || 0) : -1
        if (p !== blockPhase || i === phases.length) {
          ctx.fillStyle = PHASE_COLORS[blockPhase] || '#4b5563'
          ctx.fillRect(fx(blockStart), 2, Math.max(fx(i) - fx(blockStart), 1), 16)
          blockStart = i; blockPhase = p
        }
      }
    }

    if (strokes?.length > 0) {
      for (const s of strokes) {
        const x1 = fx(s.start_frame), x2 = fx(s.end_frame), w = Math.max(x2 - x1, 3)
        ctx.fillStyle = s.errors?.length > 0 ? 'rgba(251,146,60,.5)' : 'rgba(74,222,128,.5)'
        ctx.fillRect(x1, 22, w, 14)
        if (s.contact_frame != null) {
          const cx = fx(s.contact_frame)
          ctx.strokeStyle = '#fbbf24'; ctx.lineWidth = 2
          ctx.beginPath(); ctx.moveTo(cx, 22); ctx.lineTo(cx, 36); ctx.stroke()
        }
        ctx.strokeStyle = 'rgba(255,255,255,.3)'; ctx.lineWidth = 1
        ctx.strokeRect(x1, 22, w, 14)
      }
    }

    if (currentStroke) {
      const mark = (frame, color, label) => {
        if (frame == null) return
        const x = fx(frame)
        ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.setLineDash([4, 2])
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
        ctx.setLineDash([])
        ctx.fillStyle = color; ctx.font = '10px monospace'
        ctx.fillText(label, x + 2, 52)
      }
      mark(currentStroke.start_frame,   '#22c55e', 'S')
      mark(currentStroke.contact_frame, '#eab308', 'C')
      mark(currentStroke.end_frame,     '#ef4444', 'E')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [totalFrames, phases, strokes, currentStroke])

  // ── fg: только линия позиции ──────────────────────────────────────────────

  const drawFg = useCallback((frame) => {
    const fg = fgCanvasRef.current
    const bg = bgCanvasRef.current
    if (!fg || !bg || totalFrames <= 0) return
    if (fg.width !== bg.width || fg.height !== bg.height) {
      fg.width = bg.width; fg.height = bg.height
      fg.style.width = bg.style.width; fg.style.height = bg.style.height
    }
    const dpr = window.devicePixelRatio || 1
    const W   = fg.width / dpr
    const H   = fg.height / dpr
    const ctx = fg.getContext('2d')
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, W, H)
    const curX = (frame / totalFrames) * W
    ctx.strokeStyle = '#ef4444'; ctx.lineWidth = 2; ctx.setLineDash([])
    ctx.beginPath(); ctx.moveTo(curX, 0); ctx.lineTo(curX, H); ctx.stroke()
    ctx.fillStyle = '#ef4444'
    ctx.beginPath(); ctx.arc(curX, H - 4, 4, 0, Math.PI * 2); ctx.fill()
  }, [totalFrames])

  // ── effects ───────────────────────────────────────────────────────────────

  useEffect(() => { drawBg() }, [drawBg])

  useEffect(() => {
    const ro = new ResizeObserver(() => {
      drawBg()
      drawFg(lastDrawnFrame.current < 0 ? 0 : lastDrawnFrame.current)
    })
    const container = containerRef.current
    if (container) ro.observe(container)
    return () => ro.disconnect()
  }, [drawBg, drawFg])

  // RAF-цикл: читает v.currentTime напрямую, рисует fg без React-рендеров.
  // Это ключевое отличие от предыдущей версии, где useEffect([currentFrame])
  // триггерил React-рендер при каждом кадре.
  useEffect(() => {
    let rafId
    const tick = () => {
      const v = videoRef?.current
      if (v && fps > 0 && totalFrames > 0) {
        const frame = Math.min(Math.round(v.currentTime * fps), totalFrames - 1)
        if (frame !== lastDrawnFrame.current) {
          lastDrawnFrame.current = frame
          drawFg(frame)
        }
      }
      rafId = requestAnimationFrame(tick)
    }
    rafId = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafId)
  }, [videoRef, fps, totalFrames, drawFg])

  const handleClick = useCallback((e) => {
    const fg = fgCanvasRef.current
    if (!fg || totalFrames <= 0 || !onSeek) return
    const rect  = fg.getBoundingClientRect()
    const frame = Math.round(((e.clientX - rect.left) / rect.width) * totalFrames)
    onSeek(Math.max(0, Math.min(frame, totalFrames - 1)))
  }, [totalFrames, onSeek])

  return (
    <div ref={containerRef} className="w-full">
      <div className="relative w-full rounded overflow-hidden" style={{ height: 60 }}>
        <canvas ref={bgCanvasRef} className="absolute inset-0 w-full" style={{ height: 60 }} />
        <canvas
          ref={fgCanvasRef}
          className="absolute inset-0 w-full cursor-pointer"
          style={{ height: 60 }}
          onClick={handleClick}
        />
      </div>
      <div className="flex gap-3 mt-1 text-xs text-gray-500">
        {[['#9ca3af','idle'],['#7dd3fc','замах'],['#f87171','контакт'],['#86efac','завершение']].map(([c,n]) => (
          <span key={n} className="flex items-center gap-1">
            <span className="w-3 h-2 rounded" style={{ background: c }} /> {n}
          </span>
        ))}
      </div>
    </div>
  )
}
