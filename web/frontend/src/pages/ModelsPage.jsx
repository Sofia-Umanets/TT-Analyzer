import React, { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import {
  runTraining, getTrainingProgress, getTrainingStats, getHealth,
  startFeatureExtraction, getFeatureExtractionProgress,
} from '../api/client'

const MODEL_META = {
  classifier: {
    title: 'Классификатор ударов',
    description: 'Attention + BiLSTM, 7 классов типов ударов',
    bridgeKey: 'stroke_classifier',
  },
  error_detector: {
    title: 'Детектор ошибок',
    description: 'Attention + BiLSTM, 20 ошибок + оценка качества',
    bridgeKey: 'error_detector',
  },
  phase_detector: {
    title: 'Детектор фаз',
    description: 'Conv1D + BiLSTM, 4 фазы: idle / backswing / contact / follow_through',
    bridgeKey: 'phase_detector',
  },
}

// ── helpers ───────────────────────────────────────────────────────────────────

function MetricBox({ label, value }) {
  return (
    <div className="bg-gray-700/60 rounded p-2.5 text-center">
      <div className="text-lg font-bold text-white">{value}</div>
      <div className="text-xs text-gray-400 mt-0.5">{label}</div>
    </div>
  )
}

function LogBox({ logs, open }) {
  const endRef = useRef(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [logs?.length])
  if (!logs?.length) return null
  return (
    <details open={open}>
      <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-300 select-none">
        Лог ({logs.length})
      </summary>
      <div className="mt-1.5 bg-gray-900 rounded p-2 max-h-40 overflow-y-auto font-mono text-xs space-y-px">
        {logs.map((line, i) => (
          <div key={i} className={line.startsWith('ОШИБКА') ? 'text-red-400' : 'text-green-400'}>
            {line}
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </details>
  )
}

function ProblemVideoRow({ video }) {
  const stem = video.video?.replace(/\.[^.]+$/, '') ?? video.video
  const hasPct = video.accuracy != null
  const badgeClass = hasPct
    ? video.accuracy < 50  ? 'bg-red-900 text-red-300'
    : video.accuracy < 70  ? 'bg-yellow-900 text-yellow-300'
    : 'bg-green-900 text-green-300'
    : 'bg-gray-700 text-gray-400'

  return (
    <div className="flex items-center justify-between bg-gray-750 border border-gray-700 rounded px-2.5 py-1.5 text-xs gap-2">
      <span className={`px-1.5 py-0.5 rounded shrink-0 ${badgeClass}`}>
        {hasPct ? `${video.accuracy}%` : '—'}
      </span>
      <span className="text-gray-300 truncate flex-1">{video.video}</span>
      <span className="text-gray-500 shrink-0">{video.n_strokes} уд.</span>
      <Link to={`/annotate/${stem}`} className="text-blue-400 hover:text-blue-300 shrink-0" title="Разметка">✏</Link>
    </div>
  )
}

function ProgressBar({ progress, done }) {
  return (
    <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-500 ${done ? 'bg-green-500' : 'bg-purple-500'}`}
        style={{ width: `${progress ?? 0}%` }}
      />
    </div>
  )
}

// ── ModelCard ─────────────────────────────────────────────────────────────────

function ModelCard({ modelKey, modelsAvailable }) {
  const meta = MODEL_META[modelKey]
  const [state, setState] = useState(null)
  const pollRef = useRef(null)
  const isLoaded = modelsAvailable?.[meta.bridgeKey] ?? false

  useEffect(() => {
    getTrainingProgress(modelKey)
      .then(prog => { setState(prog); if (prog.status === 'running') startPolling() })
      .catch(() => {})
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const prog = await getTrainingProgress(modelKey)
        setState(prog)
        if (prog.status !== 'running') { clearInterval(pollRef.current); pollRef.current = null }
      } catch { clearInterval(pollRef.current); pollRef.current = null }
    }, 2000)
  }

  const handleTrain = async () => {
    try {
      setState(await runTraining(modelKey))
      startPolling()
    } catch (e) {
      setState({ model: modelKey, status: 'error', message: e.message, logs: [], metrics: {}, problem_videos: [] })
    }
  }

  const isRunning = state?.status === 'running'
  const isDone    = state?.status === 'done'
  const isError   = state?.status === 'error'
  const metrics   = state?.metrics ?? {}

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">

      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-bold text-white truncate min-w-0">{meta.title}</h2>
          <span className={`text-xs px-2 py-0.5 rounded shrink-0 ${isLoaded ? 'bg-green-900/60 text-green-300' : 'bg-gray-700 text-gray-500'}`}>
            {isLoaded ? '● Загружена' : '○ Нет'}
          </span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-gray-400 min-w-0 truncate">{meta.description}</p>
          <button
            onClick={handleTrain}
            disabled={isRunning}
            className="px-3 py-1.5 text-xs rounded bg-purple-600 hover:bg-purple-500 disabled:bg-gray-600 disabled:cursor-not-allowed shrink-0"
          >
            {isRunning ? '⏳ Обучение...' : '▶ Запустить'}
          </button>
        </div>
      </div>

      {(isRunning || isDone) && (
        <div>
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>{state?.message}</span>
            <span>{Math.round(state?.progress ?? 0)}%</span>
          </div>
          <ProgressBar progress={state?.progress} done={isDone} />
        </div>
      )}

      {isError && (
        <div className="text-xs px-2 py-1.5 rounded bg-red-900/40 text-red-300 border border-red-800">
          ⚠ {state?.message}
        </div>
      )}

      {isDone && Object.keys(metrics).length > 0 && (
        <div className="grid grid-cols-2 gap-2">
          {metrics.best_val_acc    != null && <MetricBox label="Val Accuracy" value={`${metrics.best_val_acc}%`} />}
          {metrics.best_val_f1     != null && <MetricBox label="Val F1"       value={`${metrics.best_val_f1}%`} />}
          {metrics.overall_accuracy != null && <MetricBox label="Точность (данные)" value={`${metrics.overall_accuracy}%`} />}
          {metrics.total_epochs    != null && <MetricBox label="Эпохи"        value={metrics.total_epochs} />}
          {metrics.total_strokes   != null && <MetricBox label="Ударов"       value={metrics.total_strokes} />}
          {metrics.total_videos    != null && <MetricBox label="Видео"        value={metrics.total_videos} />}
        </div>
      )}

      <LogBox logs={state?.logs} open={isRunning} />

      {isDone && state?.problem_videos?.length > 0 && (
        <details>
          <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-300 select-none">
            Проблемные видео ({state.problem_videos.length})
            {modelKey === 'classifier' && <span className="text-gray-600 ml-1">— по точности ↑</span>}
          </summary>
          <div className="mt-1.5 space-y-1 max-h-52 overflow-y-auto">
            {state.problem_videos.map((v, i) => <ProblemVideoRow key={i} video={v} />)}
          </div>
        </details>
      )}
    </div>
  )
}

// ── FeatureExtractionCard ─────────────────────────────────────────────────────

function FeatureExtractionCard() {
  const [state, setState] = useState(null)
  const [force, setForce] = useState(false)
  const pollRef = useRef(null)

  useEffect(() => {
    getFeatureExtractionProgress()
      .then(s => { setState(s); if (s.status === 'running') startPolling() })
      .catch(() => {})
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const startPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const s = await getFeatureExtractionProgress()
        setState(s)
        if (s.status !== 'running') { clearInterval(pollRef.current); pollRef.current = null }
      } catch { clearInterval(pollRef.current); pollRef.current = null }
    }, 2000)
  }

  const handleExtract = async () => {
    try {
      setState(await startFeatureExtraction(force))
      startPolling()
    } catch (e) {
      setState({ status: 'error', message: e.message, logs: [], n_videos: 0, n_frames: 0, progress: 0 })
    }
  }

  const isRunning = state?.status === 'running'
  const isDone    = state?.status === 'done'
  const isError   = state?.status === 'error'

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="font-bold text-white">Кэш признаков</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            MediaPipe pose extraction из всех видео →{' '}
            <code className="text-gray-500">data/cache/features_cache.pkl</code>
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <label className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={force}
              onChange={e => setForce(e.target.checked)}
              className="rounded"
            />
            Пересоздать всё
          </label>
          <button
            onClick={handleExtract}
            disabled={isRunning}
            className="px-3 py-1.5 text-xs rounded bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
          >
            {isRunning ? '⏳ Выполняется...' : '⟳ Обновить кэш'}
          </button>
        </div>
      </div>

      {isRunning && (
        <div className="flex items-center gap-2 text-xs text-blue-300">
          <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse inline-block" />
          {state?.message || 'Обработка видео...'}
        </div>
      )}

      {isDone && state?.n_videos > 0 && (
        <div className="flex gap-3">
          <div className="bg-gray-700/60 rounded px-4 py-2 text-center">
            <div className="text-lg font-bold text-white">{state.n_videos}</div>
            <div className="text-xs text-gray-400">Видео</div>
          </div>
          <div className="bg-gray-700/60 rounded px-4 py-2 text-center">
            <div className="text-lg font-bold text-white">{state.n_frames.toLocaleString()}</div>
            <div className="text-xs text-gray-400">Кадров</div>
          </div>
        </div>
      )}

      {isError && (
        <div className="text-xs px-2 py-1.5 rounded bg-red-900/40 text-red-300 border border-red-800">
          ⚠ {state?.message}
        </div>
      )}

      <LogBox logs={state?.logs} open={isRunning} />
    </div>
  )
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function ModelsPage() {
  const [health, setHealth]           = useState(null)
  const [stats, setStats]             = useState(null)
  const [loadingStats, setLoadingStats] = useState(false)

  useEffect(() => { getHealth().then(setHealth).catch(() => {}) }, [])

  const handleLoadStats = async () => {
    setLoadingStats(true)
    try { setStats(await getTrainingStats()) }
    catch (e) { setStats({ error: e.message }) }
    finally { setLoadingStats(false) }
  }

  const modelsAvailable = health?.models_available ?? {}
  const loadedCount = Object.values(modelsAvailable).filter(Boolean).length
  const totalCount  = Object.keys(modelsAvailable).length

  return (
    <div className="space-y-5 max-w-5xl mx-auto">

      {/* Заголовок */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold">Модели</h1>
          {health && (
            <p className="text-xs text-gray-400 mt-0.5">
              Загружено: {loadedCount} / {totalCount}
            </p>
          )}
        </div>
        <button
          onClick={handleLoadStats}
          disabled={loadingStats}
          className="px-3 py-1.5 text-xs rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50"
        >
          {loadingStats ? '⏳ Считаем...' : '📊 Пересчитать статистику'}
        </button>
      </div>

      {/* Статистика без переобучения */}
      {stats && !stats.error && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 space-y-2">
          <div className="text-sm font-semibold text-gray-300">Текущая статистика</div>
          <div className="grid grid-cols-3 gap-3 text-xs">
            {stats.classifier && (
              <div className="space-y-0.5">
                <div className="text-gray-400 font-medium">Классификатор</div>
                <div className="text-white font-bold">{stats.classifier.overall_accuracy}%</div>
                <div className="text-gray-500">{stats.classifier.total_strokes} ударов</div>
              </div>
            )}
            {stats.error_detector && (() => {
              const f1s = Object.values(stats.error_detector.per_error_f1 ?? {})
                .filter(v => v.support > 0).map(v => v.f1)
              const avg = f1s.length > 0 ? (f1s.reduce((a, b) => a + b, 0) / f1s.length * 100).toFixed(1) : '—'
              return (
                <div className="space-y-0.5">
                  <div className="text-gray-400 font-medium">Детектор ошибок</div>
                  <div className="text-white font-bold">F1 {avg}%</div>
                  <div className="text-gray-500">{stats.error_detector.total_strokes} ударов</div>
                </div>
              )
            })()}
            {stats.phase_detector && (
              <div className="space-y-0.5">
                <div className="text-gray-400 font-medium">Детектор фаз</div>
                <div className="text-white font-bold">{stats.phase_detector.overall_accuracy}%</div>
                <div className="text-gray-500">{stats.phase_detector.total_videos} видео</div>
              </div>
            )}
          </div>
        </div>
      )}
      {stats?.error && (
        <div className="text-xs px-3 py-2 rounded bg-red-900/40 text-red-300 border border-red-800">⚠ {stats.error}</div>
      )}

      {/* Кэш признаков */}
      <FeatureExtractionCard />

      {/* Карточки моделей */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.keys(MODEL_META).map(key => (
          <ModelCard key={key} modelKey={key} modelsAvailable={modelsAvailable} />
        ))}
      </div>
    </div>
  )
}
