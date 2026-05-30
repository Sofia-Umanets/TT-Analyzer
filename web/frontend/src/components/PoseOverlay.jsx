import React, { useRef, useEffect, useCallback } from 'react'
import { getAllLandmarks } from '../api/client'

const CONNECTIONS = [
  ['left_shoulder', 'right_shoulder'],
  ['left_shoulder', 'left_elbow'],   ['left_elbow', 'left_wrist'],
  ['right_shoulder', 'right_elbow'], ['right_elbow', 'right_wrist'],
  ['left_shoulder', 'left_hip'],     ['right_shoulder', 'right_hip'],
  ['left_hip', 'right_hip'],
  ['left_hip', 'left_knee'],   ['left_knee', 'left_ankle'],
  ['right_hip', 'right_knee'], ['right_knee', 'right_ankle'],
]

const JOINT_COLORS = {
  left_shoulder: '#22c55e', right_shoulder: '#3b82f6',
  left_elbow:    '#22c55e', right_elbow:    '#3b82f6',
  left_wrist:    '#22c55e', right_wrist:    '#3b82f6',
  left_hip:      '#22c55e', right_hip:      '#3b82f6',
  left_knee:     '#22c55e', right_knee:     '#3b82f6',
  left_ankle:    '#22c55e', right_ankle:    '#3b82f6',
}

export default function PoseOverlay({ videoId, videoRef, fps, visible = true, videoReady }) {
  const canvasRef     = useRef(null)
  const landmarksRef  = useRef(null)   // массив по кадрам после загрузки
  const lastFrameRef  = useRef(-1)
  const rvcHandleRef  = useRef(null)

  // ── загружаем все landmarks при смене videoId ─────────────────────────────
  useEffect(() => {
    landmarksRef.current = null
    lastFrameRef.current = -1
    if (!videoId) return
    getAllLandmarks(videoId)
      .then(data => { landmarksRef.current = data.landmarks })
      .catch(() => {})
  }, [videoId])

  // ── функция отрисовки одного кадра ────────────────────────────────────────
  const drawFrame = useCallback((frame) => {
    const canvas  = canvasRef.current
    const video   = videoRef?.current
    const allLm   = landmarksRef.current
    if (!canvas || !video) return
    if (!videoReady || video.videoWidth === 0 || video.videoHeight === 0) return

    const rect = video.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return

    const dpr  = window.devicePixelRatio || 1
    const newW = Math.round(rect.width  * dpr)
    const newH = Math.round(rect.height * dpr)
    if (canvas.width !== newW || canvas.height !== newH) {
      canvas.width  = newW
      canvas.height = newH
      canvas.style.width  = rect.width  + 'px'
      canvas.style.height = rect.height + 'px'
    }

    const ctx = canvas.getContext('2d')
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, rect.width, rect.height)

    if (!visible || !allLm) return

    const lm = allLm[frame]
    if (!lm) return   // кадр без позы

    // letterbox-aware координаты
    const W = rect.width
    const H = rect.height
    const scale = Math.min(W / video.videoWidth, H / video.videoHeight)
    const drawW = video.videoWidth  * scale
    const drawH = video.videoHeight * scale
    const ox = (W - drawW) / 2
    const oy = (H - drawH) / 2

    const toPixel = (name) => {
      const p = lm[name]
      if (!p) return null
      return { x: ox + p[0] * drawW, y: oy + p[1] * drawH, vis: p[3] ?? 0 }
    }

    ctx.lineWidth = 2
    for (const [a, b] of CONNECTIONS) {
      const pa = toPixel(a), pb = toPixel(b)
      if (!pa || !pb || pa.vis < 0.3 || pb.vis < 0.3) continue
      ctx.strokeStyle = 'rgba(255,255,255,0.6)'
      ctx.beginPath(); ctx.moveTo(pa.x, pa.y); ctx.lineTo(pb.x, pb.y); ctx.stroke()
    }

    for (const [name, color] of Object.entries(JOINT_COLORS)) {
      const p = toPixel(name)
      if (!p || p.vis < 0.3) continue
      ctx.fillStyle = color
      ctx.beginPath(); ctx.arc(p.x, p.y, 4, 0, Math.PI * 2); ctx.fill()
      ctx.strokeStyle = 'white'; ctx.lineWidth = 1; ctx.stroke()
    }
  }, [videoRef, visible, videoReady])

  // ── requestVideoFrameCallback ─────────────────────────────────────────────
  useEffect(() => {
    const video = videoRef?.current
    if (!video || !videoReady || !videoId || !fps) return

    const onFrame = (_now, metadata) => {
      const frame = fps > 0 ? Math.round(metadata.mediaTime * fps) : 0
      if (frame !== lastFrameRef.current) {
        lastFrameRef.current = frame
        drawFrame(frame)
      }
      rvcHandleRef.current = video.requestVideoFrameCallback(onFrame)
    }

    if ('requestVideoFrameCallback' in HTMLVideoElement.prototype) {
      rvcHandleRef.current = video.requestVideoFrameCallback(onFrame)
    } else {
      // Fallback: timeupdate
      const onTimeUpdate = () => {
        const frame = fps > 0 ? Math.round(video.currentTime * fps) : 0
        if (frame !== lastFrameRef.current) {
          lastFrameRef.current = frame
          drawFrame(frame)
        }
      }
      video.addEventListener('timeupdate', onTimeUpdate)
      return () => video.removeEventListener('timeupdate', onTimeUpdate)
    }

    return () => {
      if (rvcHandleRef.current != null && 'cancelVideoFrameCallback' in HTMLVideoElement.prototype) {
        video.cancelVideoFrameCallback(rvcHandleRef.current)
        rvcHandleRef.current = null
      }
    }
  }, [videoRef, videoReady, videoId, fps, drawFrame])

  // ── перерисовка при resize контейнера ────────────────────────────────────
  useEffect(() => {
    const video = videoRef?.current
    if (!video) return
    const ro = new ResizeObserver(() => drawFrame(lastFrameRef.current))
    ro.observe(video)
    return () => ro.disconnect()
  }, [drawFrame, videoRef])

  return (
    <canvas
      ref={canvasRef}
      className="absolute top-0 left-0 pointer-events-none"
      style={{ width: '100%', height: '100%' }}
    />
  )
}
