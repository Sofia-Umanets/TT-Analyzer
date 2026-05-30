import React, { useState, useEffect, useCallback } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  getVideo, runAnalysis, getAnalysisProgress,
  exportAnnotation, getPhases,
} from '../api/client'
import useVideo from '../hooks/useVideo'
import useAnnotation from '../hooks/useAnnotation'
import VideoPlayer from '../components/VideoPlayer'
import Timeline from '../components/Timeline'
import StrokeList from '../components/StrokeList'
import AnnotationPanel from '../components/AnnotationPanel'

export default function AnnotatePage() {
  const { videoId } = useParams()
  const navigate = useNavigate()

  const [videoInfo,     setVideoInfo]     = useState(null)
  const [editingStroke, setEditingStroke] = useState(null)
  // currentMarks передаётся в Timeline для отображения S/C/E маркеров
  const [currentMarks,  setCurrentMarks]  = useState({ start_frame: null, contact_frame: null, end_frame: null })
  const [analysisRunning,  setAnalysisRunning]  = useState(false)
  const [analysisMsg,      setAnalysisMsg]      = useState('')
  const [analysisProgress, setAnalysisProgress] = useState(0)
  const [analysisError,    setAnalysisError]    = useState(false)
  const [phases,        setPhases]        = useState(null)

  const video = useVideo()
  const ann   = useAnnotation(videoId)

  // Загружаем видео: ждём конвертации, затем берём MP4 с корректным FPS
  useEffect(() => {
    if (!videoId) return
    getVideo(videoId)
      .then(info => {
        setVideoInfo(info)
        video.waitAndLoad(videoId)
      })
      .catch(e => console.error('[AnnotatePage] getVideo:', e))
  }, [videoId])

  // Загружаем фазы если анализ уже есть
  useEffect(() => {
    if (!videoId || !videoInfo?.has_analysis) return
    getPhases(videoId).then(d => setPhases(d.phases)).catch(() => {})
  }, [videoId, videoInfo])

  // Сохранение или обновление удара
  const handleSave = useCallback(async (marks, type, quality, errors, editingId) => {
    const strokeData = {
      start_frame:   marks.start,
      contact_frame: marks.contact,
      end_frame:     marks.end,
      type,
      quality,
      errors,
    }
    if (editingId) {
      await ann.updateStroke(editingId, strokeData)
    } else {
      await ann.addStroke({ id: 0, ...strokeData })
    }
    setEditingStroke(null)
    // Авто-переход к следующему кадру после конца удара (как в web1)
    if (marks.end != null) {
      video.seekToFrame(marks.end + 1)
    }
  }, [ann, video])

  const handleCancelEdit = useCallback(() => {
    setEditingStroke(null)
  }, [])

  // Клик на ✎ в StrokeList: загружаем данные в панель и переходим к start_frame
  const handleEdit = useCallback((stroke) => {
    setEditingStroke(stroke)
    video.seekToFrame(stroke.start_frame)
  }, [video])

  const handleDeleteLast = useCallback(async () => {
    const strokes = ann.annotation?.strokes
    if (!strokes?.length) return
    const last = strokes[strokes.length - 1]
    if (window.confirm(`Удалить удар #${last.id}?`)) {
      await ann.removeStroke(last.id)
    }
  }, [ann])

  const handleRunAnalysis = async () => {
    setAnalysisRunning(true)
    setAnalysisError(false)
    setAnalysisProgress(0)
    setAnalysisMsg('Запуск...')
    try {
      await runAnalysis(videoId)
      const poll = setInterval(async () => {
        try {
          const p = await getAnalysisProgress(videoId)
          setAnalysisProgress(Math.round(p.progress))
          setAnalysisMsg(p.message)
          if (p.status === 'done') {
            clearInterval(poll)
            setAnalysisRunning(false)
            setAnalysisProgress(100)
            setAnalysisMsg('Анализ завершён! Переход к результатам…')
            const info = await getVideo(videoId)
            setVideoInfo(info)
            getPhases(videoId).then(d => setPhases(d.phases)).catch(() => {})
            setTimeout(() => navigate(`/analysis/${videoId}`), 1500)
          } else if (p.status === 'error') {
            clearInterval(poll)
            setAnalysisRunning(false)
            setAnalysisError(true)
            setAnalysisMsg('Ошибка: ' + p.message)
          }
        } catch {
          clearInterval(poll)
          setAnalysisRunning(false)
          setAnalysisError(true)
          setAnalysisMsg('Ошибка соединения с сервером')
        }
      }, 2000)
    } catch (e) {
      setAnalysisRunning(false)
      setAnalysisError(true)
      setAnalysisMsg('Ошибка: ' + (e.response?.data?.detail || e.message))
    }
  }

  const handleImportAuto = async () => {
    if (!window.confirm('Импортировать авто-разметку? Текущая будет заменена.')) return
    try { await ann.importAuto() } catch (e) { alert('Ошибка: ' + e.message) }
  }

  const strokes = ann.annotation?.strokes || []

  return (
    <div className="space-y-3">

      {/* Шапка */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <Link to="/videos" className="text-gray-400 hover:text-white shrink-0">← Видео</Link>
          <h1 className="text-lg font-bold truncate">{videoInfo?.filename || videoId}</h1>
          {videoInfo && (
            <span className="text-sm text-gray-500 shrink-0">
              {videoInfo.fps} fps · {videoInfo.total_frames} кадров
            </span>
          )}
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={handleRunAnalysis}
            disabled={analysisRunning}
            className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-600 rounded text-sm flex items-center gap-2"
          >
            {analysisRunning
              ? <span className="inline-block w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              : '🔍'}
            Авто-анализ
          </button>
          {videoInfo?.has_analysis && (
            <button
              onClick={handleImportAuto}
              className="px-3 py-1.5 bg-yellow-700 hover:bg-yellow-600 rounded text-sm"
            >
              📥 Импорт авто
            </button>
          )}
          <a
            href={exportAnnotation(videoId)}
            className="px-3 py-1.5 bg-green-700 hover:bg-green-600 rounded text-sm inline-block"
            download
          >
            📤 Экспорт
          </a>
          <Link
            to={`/analysis/${videoId}`}
            className="px-3 py-1.5 bg-gray-600 hover:bg-gray-500 rounded text-sm"
          >
            📊 Анализ
          </Link>
        </div>
      </div>

      {/* Баннер конвертации */}
      {video.converting && (
        <div className="text-sm px-4 py-2 rounded bg-yellow-900/40 text-yellow-300 border border-yellow-800">
          ⏳ Конвертация видео для точной покадровки…
        </div>
      )}

      {/* Статус анализа */}
      {analysisMsg && (
        <div className={`px-4 py-3 rounded border ${
          analysisError
            ? 'bg-red-900/50 text-red-300 border-red-700'
            : analysisMsg.includes('завершён')
              ? 'bg-green-900/50 text-green-300 border-green-700'
              : 'bg-blue-900/50 text-blue-300 border-blue-700'
        }`}>
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm">{analysisMsg}</span>
            {analysisError && (
              <button
                onClick={handleRunAnalysis}
                className="shrink-0 text-xs px-2 py-1 bg-red-700 hover:bg-red-600 rounded"
              >
                Повторить
              </button>
            )}
          </div>
          {analysisRunning && (
            <div className="mt-2 space-y-1">
              <div className="w-full bg-blue-950 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-blue-400 h-1.5 rounded-full transition-all duration-500"
                  style={{ width: `${analysisProgress}%` }}
                />
              </div>
              <div className="text-xs text-blue-400">{analysisProgress}%</div>
            </div>
          )}
        </div>
      )}

      {/* Основная сетка */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-3">

        {/* Левая колонка: видео + таймлайн */}
        <div className="xl:col-span-3 space-y-2">
          <VideoPlayer
            videoRef={video.videoRef}
            videoUrl={video.videoUrl}
            playing={video.playing}
            totalFrames={video.totalFrames}
            fps={video.fps}
            loaded={video.loaded}
            error={video.error}
            togglePlay={video.togglePlay}
            stepFrames={video.stepFrames}
            seekToFrame={video.seekToFrame}
            onDeleteLast={handleDeleteLast}
          />
          <Timeline
            totalFrames={video.totalFrames}
            videoRef={video.videoRef}
            fps={video.fps}
            phases={phases}
            strokes={strokes}
            currentStroke={currentMarks}
            onSeek={video.seekToFrame}
          />
        </div>

        {/* Правая колонка: панель разметки + список ударов */}
        <div className="space-y-3">
          <AnnotationPanel
            frameRef={video.currentFrameRef}
            editingStroke={editingStroke}
            onSave={handleSave}
            onCancel={handleCancelEdit}
            onMarksChange={setCurrentMarks}
          />

          <div className="bg-gray-800 border border-gray-700 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-bold text-white">
                Удары
              </span>
              <span className="text-xs text-gray-400 bg-gray-700 px-2 py-0.5 rounded-full">
                {strokes.length}
              </span>
            </div>
            <StrokeList
              strokes={strokes}
              editingId={editingStroke?.id}
              onEdit={handleEdit}
              onDelete={(id) => ann.removeStroke(id)}
              onSeek={video.seekToFrame}
            />
          </div>
        </div>

      </div>
    </div>
  )
}
