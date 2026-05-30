import React, { useState, useEffect, useRef, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  getVideo, getAnalysisResult, getAnalysisProgress,
  runAnalysis, getStrokeAttention, getStrokeFeatures, getFeatureImportance,
} from '../api/client'
import useVideo from '../hooks/useVideo'
import VideoPlayer from '../components/VideoPlayer'
import Timeline from '../components/Timeline'
import PoseOverlay from '../components/PoseOverlay'
import PhaseStrip from '../components/PhaseStrip'
import ErrorHeatmap from '../components/ErrorHeatmap'
import FeatureChart from '../components/FeatureChart'
import AttentionView from '../components/AttentionView'
import ErrorSaliencyChart from '../components/ErrorSaliencyChart'

const TYPE_NAMES = {
  drive_forehand: 'Drive FH', topspin_forehand: 'Topspin FH',
  slice_forehand: 'Slice FH', drive_backhand: 'Drive BH',
  topspin_backhand: 'Topspin BH', slice_backhand: 'Slice BH',
  other: 'Другой',
}

const ERROR_NAMES_RU = {
  arm_far:                   'Рука далеко от корпуса',
  big_swing:                 'Слишком большой замах',
  left_hand_up:              'Левая рука поднята',
  low_backswing:             'Замах снизу',
  low_elbow_end:             'Локоть низко в конце',
  no_forearm:                'Нет работы предплечья',
  no_rotation:               'Нет вращения корпуса',
  raised_elbow:              'Поднят локоть',
  raised_shoulder:           'Поднято плечо',
  sideways_finish:           'Концовка вбок',
  straight_arm:              'Прямая рука в конце',
  straight_body:             'Прямой корпус',
  straight_legs:             'Прямые ноги',
  straight_line:             'Движение по прямой',
  wrist_bent_back:           'Кисть выгнута назад',
  wrist_bent_fwd:            'Кисть согнута вперёд',
  wrist_up:                  'Кисть вверх в конце',
  incomplete_follow_through: 'Неполное сопровождение',
  left_hand_behind_body:     'Левая рука за корпусом',
  vertical_swing:            'Вертикальный замах',
}

export default function AnalysisPage() {
  const { videoId } = useParams()
  const [videoInfo, setVideoInfo]         = useState(null)
  const [analysis, setAnalysis]           = useState(null)
  const [analysisError, setAnalysisError] = useState(null)
  const [selectedStroke, setSelectedStroke] = useState(null)
  const [showSkeleton, setShowSkeleton]   = useState(true)
  const [attention, setAttention]         = useState(null)
  const [strokeFeatures, setStrokeFeatures] = useState(null)
  const [running, setRunning]             = useState(false)
  const [progressMsg, setProgressMsg]     = useState('')
  const [selectedFeature, setSelectedFeature] = useState(null)
  const [globalImportance, setGlobalImportance] = useState(null)
  const [selectedError, setSelectedError]   = useState(null)
  const [attentionLoading, setAttentionLoading] = useState(false)
  const [attentionError, setAttentionError]     = useState(null)

  const pollRef = useRef(null)
  const video   = useVideo()

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  useEffect(() => {
    if (!videoId) return
    getVideo(videoId).then(info => { setVideoInfo(info); video.waitAndLoad(videoId) }).catch(() => {})
  }, [videoId])

  useEffect(() => {
    if (!videoId) return
    setAnalysisError(null)
    getAnalysisResult(videoId)
      .then(result => { setAnalysis(result); setAnalysisError(null) })
      .catch(err => {
        if (err?.response?.status !== 404) setAnalysisError('Не удалось загрузить результат анализа')
        setAnalysis(null)
      })
  }, [videoId])

  // Block 2: загружаем глобальную важность признаков при первом рендере
  useEffect(() => {
    getFeatureImportance().then(setGlobalImportance).catch(() => {})
  }, [])

  useEffect(() => {
    setSelectedFeature(null)
    setSelectedError(null)
  }, [selectedStroke?.id])

  // Block 2: когда attention пришёл — авто-выбираем топ-признак
  useEffect(() => {
    if (attention?.feature_importance && !selectedFeature) {
      const top = Object.entries(attention.feature_importance).sort((a, b) => b[1] - a[1])[0]?.[0]
      if (top) setSelectedFeature(top)
    }
  }, [attention])

  useEffect(() => {
    if (!videoId || !selectedStroke) return
    setAttention(null)
    setStrokeFeatures(null)
    setAttentionError(null)
    setAttentionLoading(true)
    getStrokeAttention(videoId, selectedStroke.id)
      .then(data => { setAttention(data); setAttentionLoading(false) })
      .catch(e => {
        setAttentionLoading(false)
        setAttentionError(e?.response?.data?.detail || e.message || 'Ошибка загрузки данных внимания')
      })
    getStrokeFeatures(videoId, selectedStroke.id).then(setStrokeFeatures).catch(() => {})
  }, [videoId, selectedStroke])

  const handleRun = async () => {
    setRunning(true)
    setProgressMsg('Запуск...')
    try {
      await runAnalysis(videoId)
      pollRef.current = setInterval(async () => {
        try {
          const p = await getAnalysisProgress(videoId)
          setProgressMsg(`${p.message} (${Math.round(p.progress)}%)`)
          if (p.status === 'done') {
            clearInterval(pollRef.current)
            setRunning(false)
            setProgressMsg('')
            setAnalysis(await getAnalysisResult(videoId))
          } else if (p.status === 'error') {
            clearInterval(pollRef.current)
            setRunning(false)
            setProgressMsg('Ошибка: ' + p.message)
          }
        } catch { clearInterval(pollRef.current); setRunning(false) }
      }, 2000)
    } catch (e) { setRunning(false); setProgressMsg('Ошибка: ' + e.message) }
  }

  // Block 2: динамические featureNames для графика
  const featureNamesForChart = useMemo(() => {
    const src = attention?.feature_importance ?? globalImportance
    if (!src) return ['right_wrist_speed', 'right_elbow_angle', 'right_shoulder_angle']
    const sorted = Object.entries(src).sort((a, b) => b[1] - a[1]).map(([n]) => n)
    if (selectedFeature && !sorted.slice(0, 3).includes(selectedFeature)) {
      return [selectedFeature, ...sorted.slice(0, 2)]
    }
    return sorted.slice(0, 3)
  }, [attention?.feature_importance, globalImportance, selectedFeature])

  const strokes = analysis?.strokes || []
  const phases  = analysis?.phases  || null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <Link to="/videos" className="text-gray-400 hover:text-white text-sm">← Видео</Link>
          <h1 className="text-xl font-bold truncate">{videoInfo?.original_name || videoId}</h1>
        </div>
        <div className="flex gap-2">
          <button onClick={handleRun} disabled={running} className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-600 rounded text-xs">
            {running ? '⏳ Анализ...' : '🔍 Запустить анализ'}
          </button>
          <label className="flex items-center gap-1 text-xs text-gray-400">
            <input type="checkbox" checked={showSkeleton} onChange={e => setShowSkeleton(e.target.checked)} />
            Скелет
          </label>
          <Link to={`/annotate/${videoId}`} className="px-3 py-1.5 bg-gray-600 hover:bg-gray-500 rounded text-xs">✏ Разметка</Link>
        </div>
      </div>

      {video.converting && (
        <div className="text-sm px-3 py-2 rounded bg-yellow-900/40 text-yellow-300 border border-yellow-800">
          ⏳ Подготовка видео…
        </div>
      )}
      {progressMsg && (
        <div className={`text-sm px-3 py-2 rounded ${progressMsg.startsWith('Ошибка') ? 'bg-red-900/50 text-red-300' : 'bg-blue-900/50 text-blue-300'}`}>
          {progressMsg}
        </div>
      )}
      {analysisError && (
        <div className="text-sm px-3 py-2 rounded bg-red-900/50 text-red-300">⚠ {analysisError}</div>
      )}
      {!analysis && !running && !analysisError && (
        <div className="text-center py-12">
          <p className="text-gray-400 text-lg mb-4">Анализ ещё не выполнен</p>
          <button onClick={handleRun} className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-3 rounded">
            Запустить анализ
          </button>
        </div>
      )}

      {analysis && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <div className="lg:col-span-3 space-y-3">
            <VideoPlayer
              videoRef={video.videoRef}
              videoUrl={video.videoUrl}
              playing={video.playing}
              currentFrame={video.currentFrame}
              totalFrames={video.totalFrames}
              fps={video.fps}
              currentTime={video.currentTime}
              duration={video.duration}
              loaded={video.loaded}
              error={video.error}
              togglePlay={video.togglePlay}
              stepFrames={video.stepFrames}
              seekToFrame={video.seekToFrame}
            >
              {/* Block 3: PoseOverlay теперь самостоятельно загружает landmarks через rVFC */}
              {showSkeleton && (
                <PoseOverlay
                  videoId={videoId}
                  videoRef={video.videoRef}
                  fps={video.fps}
                  visible={showSkeleton}
                  videoReady={video.loaded}
                />
              )}
            </VideoPlayer>

            <Timeline
              totalFrames={video.totalFrames}
              currentFrame={video.currentFrame}
              fps={video.fps}
              phases={phases}
              strokes={strokes}
              onSeek={video.seekToFrame}
            />

            {/* Block 2: динамические featureNames + подсветка выбранного */}
            {strokeFeatures && (
              <FeatureChart
                data={strokeFeatures.frames}
                featureNames={featureNamesForChart}
                highlightedFeature={selectedFeature}
                contactFrame={selectedStroke?.contact_frame}
                title="Признаки удара"
              />
            )}

            {attention && (
              <AttentionView
                attention={attention}
                selectedFeature={selectedFeature}
                onFeatureClick={setSelectedFeature}
              />
            )}

            {/* Покадровый анализ выбранной ошибки */}
            {selectedError && attention?.error_saliency?.[selectedError] && strokeFeatures && (
              <ErrorSaliencyChart
                strokeFrames={strokeFeatures.frames}
                saliency={attention.error_saliency[selectedError]}
                contactFrame={selectedStroke?.contact_frame}
                errorName={ERROR_NAMES_RU[selectedError] ?? selectedError}
              />
            )}
          </div>

          <div className="space-y-3">
            <div className="bg-gray-800 rounded-lg p-3">
              <h3 className="text-sm font-bold mb-2">Удары: {strokes.length}</h3>
              <div className="text-xs text-gray-500 mb-3">
                Детекция: {analysis.detection_rate != null ? `${analysis.detection_rate}%` : '—'} | Кадров: {analysis.total_frames ?? '—'}
              </div>
              <div className="space-y-2 max-h-[500px] overflow-y-auto">
                {strokes.map(s => (
                  <div
                    key={s.id}
                    className={`p-3 rounded cursor-pointer border transition-colors ${
                      selectedStroke?.id === s.id ? 'bg-blue-900/50 border-blue-500' : 'bg-gray-750 border-gray-700 hover:border-gray-600'
                    }`}
                    onClick={() => { setSelectedStroke(s); video.seekToFrame(s.start_frame) }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium">#{s.id} {TYPE_NAMES[s.predicted_type] || s.predicted_type}</span>
                      {s.quality != null && (
                        <span className={`text-xs px-1.5 rounded ${s.quality >= 7 ? 'bg-green-800 text-green-200' : s.quality >= 4 ? 'bg-yellow-800 text-yellow-200' : 'bg-red-800 text-red-200'}`}>
                          {s.quality.toFixed(1)}/10
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500">
                      {s.start_time?.toFixed(2) ?? '?'}с → {s.contact_time?.toFixed(2) ?? '?'}с → {s.end_time?.toFixed(2) ?? '?'}с
                    </div>
                    <PhaseStrip phases={phases} startFrame={s.start_frame} endFrame={s.end_frame} />
                    {s.errors?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {s.errors.map(err => (
                          <span key={err} className="text-xs bg-red-900/50 text-red-300 px-1 rounded">{err}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {selectedStroke && (
              <div className="bg-gray-800 rounded-lg p-3 space-y-3">
                <h3 className="text-sm font-bold">Ошибки #{selectedStroke.id}</h3>
                <ErrorHeatmap
                  errorProbabilities={selectedStroke.error_probabilities}
                  errors={selectedStroke.errors}
                />
                {/* Кнопки выбора ошибки для детального анализа */}
                {selectedStroke.errors?.length > 0 && (
                  <div>
                    <div className="text-xs text-gray-500 mb-1.5">
                      {attentionError
                        ? <span className="text-red-400">⚠ {attentionError}</span>
                        : attentionLoading
                          ? '⏳ Считаем градиенты... (~5–15 сек)'
                          : attention?.error_saliency
                            ? 'Выбери ошибку — увидишь по каким параметрам и кадрам модель её нашла:'
                            : 'Нет данных внимания'}
                    </div>
                    <div className="flex flex-col gap-1">
                      {selectedStroke.errors.map(err => (
                        <button
                          key={err}
                          disabled={!attention?.error_saliency || attentionLoading}
                          onClick={() => setSelectedError(selectedError === err ? null : err)}
                          className={`text-xs px-2 py-1.5 rounded text-left transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                            selectedError === err
                              ? 'bg-red-700 text-white'
                              : 'bg-gray-700 text-red-300 hover:bg-gray-600'
                          }`}
                        >
                          {selectedError === err ? '▼ ' : '▶ '}
                          {ERROR_NAMES_RU[err] ?? err}
                        </button>
                      ))}
                    </div>
                    {selectedError && (
                      <div className="text-xs text-gray-600 mt-1">
                        Нажми ещё раз — скроет график
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
