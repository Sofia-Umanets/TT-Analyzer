import { useState, useRef, useCallback, useEffect, useMemo } from 'react'

export default function useVideo() {
  const pollingRef = useRef(false)

  // Refs — источник правды для горячего пути, не вызывают React-рендеры
  const fpsRef          = useRef(30)
  const currentFrameRef = useRef(0)
  const totalFramesRef  = useRef(0)

  const seekingRef    = useRef(false)
  const seekTimerRef  = useRef(null)
  const debounceTimerRef = useRef(null)

  // videoNode нужен только как зависимость useEffect — чтобы он перезапустился
  // когда <video> появляется в DOM (conditional render в AnalysisPage/AnnotatePage).
  const [videoNode, _setVideoNode] = useState(null)

  // "Умный ref": снаружи выглядит как обычный { current } — PoseOverlay, Skeleton3D,
  // AnalysisPage работают без изменений. Внутри сеттер .current вызывает _setVideoNode,
  // что триггерит useEffect → слушатели навешиваются на элемент при его монтировании.
  // useState-сеттеры гарантированно стабильны (React не меняет ссылку), поэтому
  // useMemo с [] безопасен — _setVideoNode в замыкании всегда актуален.
  const videoRef = useMemo(() => {
    let _node = null
    return {
      get current() { return _node },
      set current(node) {
        _node = node
        _setVideoNode(node)
      },
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const [state, setState] = useState({
    playing:      false,
    currentTime:  0,
    currentFrame: 0,
    duration:     0,
    totalFrames:  0,
    fps:          30,
    loaded:       false,
    error:        null,
    videoUrl:     null,
    converting:   false,
  })

  const scheduleFrameUpdate = useCallback((v) => {
    clearTimeout(debounceTimerRef.current)
    debounceTimerRef.current = setTimeout(() => {
      debounceTimerRef.current = null
      setState(s => ({
        ...s,
        currentTime:  v.currentTime,
        currentFrame: currentFrameRef.current,
      }))
    }, 100)
  }, [])

  // videoNode в deps: эффект перезапустится когда <video> смонтируется/отмонтируется.
  // Это решает гонку когда VideoPlayer рендерится условно (videoUrl не задан при монтировании
  // страницы), и к моменту первого запуска эффекта videoRef.current был null.
  useEffect(() => {
    const v = videoRef.current
    if (!v) return

    const onLoaded = () => {
      setState(s => ({ ...s, duration: v.duration, loaded: true, error: null }))
    }

    const onTimeUpdate = () => {
      if (seekingRef.current) return
      const fps     = fpsRef.current
      const total   = totalFramesRef.current
      const frame   = Math.round(v.currentTime * fps)
      const clamped = total > 0 ? Math.min(frame, total - 1) : frame
      currentFrameRef.current = clamped
      scheduleFrameUpdate(v)
    }

    const onSeeked = () => {
      clearTimeout(seekTimerRef.current)
      seekTimerRef.current = null
      const fps     = fpsRef.current
      const total   = totalFramesRef.current
      const frame   = Math.round(v.currentTime * fps)
      const clamped = total > 0 ? Math.min(frame, total - 1) : frame
      currentFrameRef.current = clamped
      seekingRef.current = false
      scheduleFrameUpdate(v)
    }

    const onPlay  = () => setState(s => ({ ...s, playing: true }))
    const onPause = () => setState(s => ({ ...s, playing: false }))
    const onError = () => setState(s => ({
      ...s, error: v.error?.message || 'Ошибка загрузки видео', loaded: false,
    }))

    v.addEventListener('loadeddata',  onLoaded)
    v.addEventListener('timeupdate',  onTimeUpdate)
    v.addEventListener('seeked',      onSeeked)
    v.addEventListener('play',        onPlay)
    v.addEventListener('pause',       onPause)
    v.addEventListener('error',       onError)

    // Видео уже готово к моменту запуска эффекта (браузерный кэш, быстрая сеть)
    if (v.readyState >= 2) {
      setState(s => ({ ...s, duration: v.duration, loaded: true, error: null }))
    }

    return () => {
      v.removeEventListener('loadeddata',  onLoaded)
      v.removeEventListener('timeupdate',  onTimeUpdate)
      v.removeEventListener('seeked',      onSeeked)
      v.removeEventListener('play',        onPlay)
      v.removeEventListener('pause',       onPause)
      v.removeEventListener('error',       onError)
    }
  }, [scheduleFrameUpdate, videoNode])

  const setVideoUrl = useCallback((url) => {
    const v = videoRef.current
    setState(s => ({ ...s, videoUrl: url, loaded: false, error: null, playing: false }))
    if (v && url) { v.pause(); v.src = url; v.load() }
  }, [videoRef])

  const setFps = useCallback((fps) => {
    fpsRef.current = fps
    setState(s => ({
      ...s, fps,
      totalFrames: s.duration > 0 ? Math.round(s.duration * fps) : s.totalFrames,
    }))
  }, [])

  const setTotalFrames = useCallback((total) => {
    totalFramesRef.current = total
    setState(s => ({ ...s, totalFrames: total }))
  }, [])

  const togglePlay = useCallback(() => {
    const v = videoRef.current
    if (!v || !v.src || v.readyState < 2) return
    if (v.paused) v.play().catch(e => console.warn('[useVideo] play:', e))
    else v.pause()
  }, [videoRef])

  const seekToFrame = useCallback((frame) => {
    const v = videoRef.current
    if (!v || fpsRef.current <= 0 || !v.duration) return
    const maxFrame = totalFramesRef.current > 0 ? totalFramesRef.current - 1 : Infinity
    const clamped  = Math.max(0, Math.min(frame, maxFrame))
    currentFrameRef.current = clamped
    clearTimeout(seekTimerRef.current)
    seekTimerRef.current = null
    seekingRef.current = false
    v.currentTime = Math.min(clamped / fpsRef.current, v.duration)
  }, [videoRef])

  const stepFrames = useCallback((delta) => {
    if (seekingRef.current) return
    const v = videoRef.current
    if (!v || fpsRef.current <= 0 || !v.duration) return
    const fps        = fpsRef.current
    const maxFrame   = (totalFramesRef.current || 1) - 1
    const newFrame   = Math.max(0, Math.min(currentFrameRef.current + delta, maxFrame))
    const targetTime = newFrame / fps

    if (Math.abs(v.currentTime - targetTime) < 0.5 / fps) {
      currentFrameRef.current = newFrame
      return
    }

    currentFrameRef.current = newFrame
    seekingRef.current = true

    clearTimeout(seekTimerRef.current)
    seekTimerRef.current = setTimeout(() => {
      seekTimerRef.current = null
      if (seekingRef.current) {
        seekingRef.current = false
        currentFrameRef.current = Math.round(v.currentTime * fpsRef.current)
      }
    }, 500)

    v.currentTime = Math.min(targetTime, v.duration)
  }, [videoRef])

  const waitAndLoad = useCallback(async (videoId) => {
    if (pollingRef.current) return
    pollingRef.current = true
    setState(s => ({ ...s, loaded: false, error: null, videoUrl: null, converting: true }))
    try {
      let ready = false
      for (let i = 0; i < 60; i++) {
        const res  = await fetch(`/api/videos/${videoId}/status`)
        if (!res.ok) throw new Error(`status ${res.status}`)
        const data = await res.json()
        if (data.status === 'ready') { ready = true; break }
        if (data.status === 'error') throw new Error(data.message || 'Ошибка конвертации')
        await new Promise(r => setTimeout(r, 2000))
      }
      if (!ready) throw new Error('Конвертация заняла слишком много времени')

      const res  = await fetch(`/api/videos/${videoId}/web_url`)
      if (!res.ok) throw new Error(`web_url ${res.status}`)
      const { url, fps, total_frames } = await res.json()

      fpsRef.current         = fps || 30
      totalFramesRef.current = total_frames || 0

      // loaded остаётся false — его поднимет обработчик loadeddata в useEffect.
      // setState с новым videoUrl вызовет ре-рендер VideoPlayer → умный ref получит
      // элемент (или уже имеет его) → useEffect перезапустится → loadeddata навешан.
      setState(s => ({
        ...s, videoUrl: url, fps: fps || 30, totalFrames: total_frames || 0,
        loaded: false, error: null, playing: false, converting: false,
      }))

      // Явная инициализация загрузки если элемент уже существует в DOM
      const v = videoRef.current
      if (v) { v.pause(); v.src = url; v.load() }
    } catch (e) {
      setState(s => ({ ...s, error: e.message, converting: false }))
    } finally {
      pollingRef.current = false
    }
  }, [videoRef])

  return {
    videoRef,           // { current } — передаётся в <video ref={videoRef}> и в PoseOverlay/Skeleton3D
    currentFrameRef,
    ...state,
    setVideoUrl, setFps, setTotalFrames,
    togglePlay, seekToFrame, stepFrames, waitAndLoad,
  }
}
