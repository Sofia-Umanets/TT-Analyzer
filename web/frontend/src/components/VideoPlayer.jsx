import React, { useEffect, useCallback, useRef, useState } from 'react'

export default function VideoPlayer({
  videoRef,
  videoUrl,
  playing,
  // currentFrame и currentTime намеренно убраны из props —
  // счётчик обновляется через RAF, минуя React-рендеры
  totalFrames,
  fps,
  loaded,
  error,
  togglePlay,
  stepFrames,
  seekToFrame,
  children,
  onDeleteLast,
}) {
  const [frameInput, setFrameInput] = useState('')

  // DOM-рефы для императивного обновления счётчика через RAF
  const frameCounterRef = useRef(null)
  const timeDisplayRef  = useRef(null)

  // RAF-цикл: читает v.currentTime напрямую и обновляет DOM без React-рендеров.
  // Обновляется до 60 раз в секунду, но только при реальном изменении значений.
  useEffect(() => {
    let rafId
    let lastFrame = -1
    let lastTimeSec = -1

    const formatTime = (t) => {
      if (!t || !isFinite(t)) return '0:00.00'
      const m  = Math.floor(t / 60)
      const s  = Math.floor(t % 60)
      const ms = Math.floor((t % 1) * 100)
      return `${m}:${String(s).padStart(2, '0')}.${String(ms).padStart(2, '0')}`
    }

    const tick = () => {
      const v = videoRef?.current
      if (v && fps > 0) {
        const frame   = Math.round(v.currentTime * fps)
        const timeSec = Math.floor(v.currentTime * 100)  // сотые секунды

        if (frame !== lastFrame) {
          lastFrame = frame
          if (frameCounterRef.current) {
            frameCounterRef.current.textContent = `Кадр: ${frame} / ${totalFrames}`
          }
        }
        if (timeSec !== lastTimeSec) {
          lastTimeSec = timeSec
          if (timeDisplayRef.current) {
            const dur = isFinite(v.duration) ? v.duration : 0
            timeDisplayRef.current.textContent = `${formatTime(v.currentTime)} / ${formatTime(dur)}`
          }
        }
      }
      rafId = requestAnimationFrame(tick)
    }
    rafId = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafId)
  }, [videoRef, fps, totalFrames])

  const handleKeyDown = useCallback((e) => {
    const tag = document.activeElement?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
    switch (e.key) {
      case ' ':          e.preventDefault(); togglePlay(); return
      case 'ArrowLeft':  e.preventDefault(); stepFrames(e.shiftKey ? -10 : -1); return
      case 'ArrowRight': e.preventDefault(); stepFrames(e.shiftKey ? 10  :  1); return
      case 'ArrowUp':    e.preventDefault(); stepFrames(-30); return
      case 'ArrowDown':  e.preventDefault(); stepFrames( 30); return
      case '[':          e.preventDefault(); stepFrames(-Math.round(fps)); return
      case ']':          e.preventDefault(); stepFrames( Math.round(fps)); return
      case ',':          e.preventDefault(); stepFrames(-1); return
      case '.':          e.preventDefault(); stepFrames( 1); return
    }
    if (e.key.toLowerCase() === 'x' && onDeleteLast) {
      e.preventDefault(); onDeleteLast()
    }
  }, [togglePlay, stepFrames, fps, onDeleteLast])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  const handleFrameInputSubmit = (e) => {
    e.preventDefault()
    const f = parseInt(frameInput)
    if (!isNaN(f) && f >= 0 && f < totalFrames) seekToFrame(f)
    setFrameInput('')
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="video-container relative bg-black rounded-lg overflow-hidden h-[70vh]">
        <video
          ref={videoRef}
          src={videoUrl}
          className="w-full h-full object-contain"
          preload="auto"
          playsInline
          onClick={togglePlay}
        />
        {!loaded && !error && videoUrl && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/80">
            <p className="text-gray-300 animate-pulse text-base">Загрузка видео...</p>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/80">
            <div className="text-center p-4">
              <p className="text-red-400 text-lg mb-2">⚠ Ошибка загрузки видео</p>
              <p className="text-gray-400 text-sm">{error}</p>
              <p className="text-gray-500 text-xs mt-2">URL: {videoUrl}</p>
            </div>
          </div>
        )}
        {children}
      </div>

      <div className="flex items-center gap-2 px-1 flex-wrap">
        <button onClick={() => stepFrames(-30)} className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm">-30</button>
        <button onClick={() => stepFrames(-10)} className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm">-10</button>
        <button onClick={() => stepFrames(-1)}  className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm">-1</button>
        <button onClick={togglePlay} className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-base font-bold min-w-[40px]">
          {playing ? '⏸' : '▶'}
        </button>
        <button onClick={() => stepFrames(1)}   className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm">+1</button>
        <button onClick={() => stepFrames(10)}  className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm">+10</button>
        <button onClick={() => stepFrames(30)}  className="px-2 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm">+30</button>

        <div className="flex-1" />

        {/* Обновляются через RAF, не через React state */}
        <span ref={timeDisplayRef}  className="text-base text-gray-300 font-mono">0:00.00 / 0:00.00</span>
        <span ref={frameCounterRef} className="text-base text-gray-400 font-mono">Кадр: 0 / 0</span>

        <form onSubmit={handleFrameInputSubmit} className="flex gap-1">
          <input
            type="number"
            value={frameInput}
            onChange={e => setFrameInput(e.target.value)}
            placeholder="→ кадр"
            className="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-white"
          />
          <button type="submit" className="px-2 py-1 bg-gray-600 hover:bg-gray-500 rounded text-sm">Перейти</button>
        </form>
      </div>

      <div className="text-sm text-gray-500 px-1">
        Пробел: ▶/⏸ | ←→: ±1 | Shift+←→: ±10 | ↑↓: ±30 | []: ±1с | S: начало | C: контакт | E: конец | Enter: тип | Esc: отмена | X: удалить
      </div>
    </div>
  )
}
