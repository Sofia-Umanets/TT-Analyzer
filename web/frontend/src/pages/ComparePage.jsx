import React, { useState, useEffect, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import { getVideos, getAnnotation, getAnalysisResult, compareStrokes } from '../api/client'

// ── constants ─────────────────────────────────────────────────────────────────

const STROKE_COLORS = ['#3b82f6', '#ef4444', '#22c55e']

const TYPE_NAMES = {
  drive_forehand: 'Drive FH', topspin_forehand: 'Topspin FH',
  slice_forehand: 'Slice FH', drive_backhand: 'Drive BH',
  topspin_backhand: 'Topspin BH', slice_backhand: 'Slice BH',
  other: 'Другой',
}

const FEATURE_GROUPS = [
  { label: 'Скорости', features: ['right_wrist_speed', 'left_wrist_speed', 'right_elbow_speed', 'left_elbow_speed', 'right_wrist_accel', 'left_wrist_accel', 'right_elbow_angular_vel', 'right_shoulder_angular_vel'] },
  { label: 'Углы суставов', features: ['right_elbow_angle', 'left_elbow_angle', 'right_shoulder_angle', 'left_shoulder_angle', 'right_knee_angle', 'left_knee_angle', 'right_hip_angle', 'left_hip_angle'] },
  { label: 'Корпус и стойка', features: ['shoulder_hip_rotation', 'torso_forward_tilt', 'torso_side_tilt', 'shoulder_height_diff', 'stance_width', 'right_wrist_dist_body', 'right_elbow_height_vs_shoulder'] },
  { label: 'Позиции', features: ['right_wrist_rel_x', 'right_wrist_rel_y', 'right_wrist_rel_z', 'left_wrist_rel_x', 'right_elbow_rel_x', 'right_elbow_rel_y'] },
  { label: 'Направление', features: ['right_wrist_dir_x', 'right_wrist_dir_y', 'right_wrist_dir_z', 'right_wrist_from_neutral', 'left_wrist_from_neutral'] },
  { label: 'Симметрия', features: ['elbow_angle_diff', 'shoulder_angle_diff', 'knee_angle_diff', 'wrist_distance', 'right_wrist_height_vs_shoulder', 'left_wrist_height_vs_shoulder'] },
]

const FEATURE_LABELS = {
  // Скорости
  right_wrist_speed:           { name: 'Скорость правого запястья',       desc: 'Линейная скорость правого запястья (пиксели/кадр). Показывает динамику замаха и удара.' },
  left_wrist_speed:            { name: 'Скорость левого запястья',        desc: 'Линейная скорость левого запястья. Важна для оценки роли балансирующей руки.' },
  right_elbow_speed:           { name: 'Скорость правого локтя',          desc: 'Скорость движения правого локтя. Характеризует работу предплечья в ударе.' },
  left_elbow_speed:            { name: 'Скорость левого локтя',           desc: 'Скорость движения левого локтя.' },
  right_wrist_accel:           { name: 'Ускорение правого запястья',      desc: 'Производная скорости запястья — показывает резкость разгона и торможения в ударе.' },
  left_wrist_accel:            { name: 'Ускорение левого запястья',       desc: 'Производная скорости левого запястья.' },
  right_elbow_angular_vel:     { name: 'Угловая скорость правого локтя', desc: 'Скорость изменения угла локтевого сустава — ключевой параметр для топспина.' },
  right_shoulder_angular_vel:  { name: 'Угловая скорость правого плеча', desc: 'Скорость вращения плечевого сустава. Характеризует «разворот» плеча в ударе.' },
  // Углы суставов
  right_elbow_angle:           { name: 'Угол правого локтя',             desc: 'Угол сгиба в правом локтевом суставе (градусы). 180° = полностью вытянута рука.' },
  left_elbow_angle:            { name: 'Угол левого локтя',              desc: 'Угол сгиба в левом локтевом суставе.' },
  right_shoulder_angle:        { name: 'Угол правого плеча',             desc: 'Угол между предплечьем и корпусом в правом плечевом суставе.' },
  left_shoulder_angle:         { name: 'Угол левого плеча',              desc: 'Угол между предплечьем и корпусом в левом плечевом суставе.' },
  right_knee_angle:            { name: 'Угол правого колена',            desc: 'Угол сгиба правого колена. Малые значения = глубокая стойка.' },
  left_knee_angle:             { name: 'Угол левого колена',             desc: 'Угол сгиба левого колена.' },
  right_hip_angle:             { name: 'Угол правого бедра',             desc: 'Угол в правом тазобедренном суставе — характеризует посадку и наклон корпуса.' },
  left_hip_angle:              { name: 'Угол левого бедра',              desc: 'Угол в левом тазобедренном суставе.' },
  // Корпус и стойка
  shoulder_hip_rotation:       { name: 'Вращение плечи–бёдра',          desc: 'Угол разворота между линией плеч и линией бёдер. Показывает скручивание корпуса при замахе.' },
  torso_forward_tilt:          { name: 'Наклон корпуса вперёд',         desc: 'Угол наклона туловища вперёд. При активном топспине — обычно больше.' },
  torso_side_tilt:             { name: 'Боковой наклон корпуса',        desc: 'Крен корпуса в сторону (лево-право).' },
  shoulder_height_diff:        { name: 'Разность высоты плеч',          desc: 'Разница высот правого и левого плеча (нормализованная). Показывает асимметрию замаха.' },
  stance_width:                { name: 'Ширина стойки',                 desc: 'Расстояние между ступнями (нормализованное). Шире — устойчивее, уже — мобильнее.' },
  right_wrist_dist_body:       { name: 'Дистанция запястья от тела',    desc: 'Расстояние правого запястья от центра масс (бёдра). Показывает «вынос» руки.' },
  right_elbow_height_vs_shoulder: { name: 'Высота локтя относительно плеча', desc: 'Насколько правый локоть выше или ниже плеча. При высоком локте — больше рычаг.' },
  // Позиции
  right_wrist_rel_x:           { name: 'Запястье: позиция X (лево-право)', desc: 'Горизонтальная позиция правого запястья относительно центра тела. Отрицательное = слева от тела.' },
  right_wrist_rel_y:           { name: 'Запястье: позиция Y (высота)',     desc: 'Высота правого запястья относительно бёдер. Положительное = выше бёдер.' },
  right_wrist_rel_z:           { name: 'Запястье: позиция Z (глубина)',    desc: 'Глубина (удалённость от камеры) правого запястья относительно тела.' },
  left_wrist_rel_x:            { name: 'Лев. запястье: позиция X',        desc: 'Горизонтальная позиция левого запястья относительно центра тела.' },
  right_elbow_rel_x:           { name: 'Локоть: позиция X (лево-право)',  desc: 'Горизонтальная позиция правого локтя относительно тела.' },
  right_elbow_rel_y:           { name: 'Локоть: позиция Y (высота)',      desc: 'Высота правого локтя относительно бёдер.' },
  // Направление
  right_wrist_dir_x:           { name: 'Запястье: направление X',        desc: 'Горизонтальная составляющая вектора движения запястья (куда движется рука).' },
  right_wrist_dir_y:           { name: 'Запястье: направление Y',        desc: 'Вертикальная составляющая вектора движения запястья.' },
  right_wrist_dir_z:           { name: 'Запястье: направление Z',        desc: 'Составляющая движения «от/к камере».' },
  right_wrist_from_neutral:    { name: 'Запястье: откл. от нейтрали',    desc: 'Расстояние запястья от его нейтральной позиции (начало замаха). Показывает фазу удара.' },
  left_wrist_from_neutral:     { name: 'Лев. запястье: откл. от нейтрали', desc: 'То же для левого запястья.' },
  // Симметрия
  elbow_angle_diff:            { name: 'Разница углов локтей',           desc: 'Правый минус левый угол локтя. Показывает асимметрию работы рук.' },
  shoulder_angle_diff:         { name: 'Разница углов плеч',             desc: 'Разница углов в плечевых суставах (правый − левый).' },
  knee_angle_diff:             { name: 'Разница углов колен',            desc: 'Правое минус левое колено. Показывает неравномерную нагрузку на ноги.' },
  wrist_distance:              { name: 'Расстояние между запястьями',    desc: 'Дистанция между правым и левым запястьем. Меняется в зависимости от типа удара.' },
  right_wrist_height_vs_shoulder: { name: 'Высота прав. запястья над плечом', desc: 'Насколько правое запястье выше или ниже правого плеча.' },
  left_wrist_height_vs_shoulder:  { name: 'Высота лев. запястья над плечом',  desc: 'Насколько левое запястье выше или ниже левого плеча.' },
}

// displayMode values: 'raw' | 'normalized' | 'contact'
// 'raw'        → normalize=false API call, frames displayed as-is
// 'normalized' → normalize=true  API call, 100-point time-normalized display
// 'contact'    → normalize=true  API call, 100-point data shifted so contact = position 0

const DISPLAY_MODES = [
  { value: 'raw',        label: 'По кадрам (сырые данные)' },
  { value: 'normalized', label: 'По времени (нормализовано)' },
  { value: 'contact',    label: 'По контакту (выравнивание)' },
]

// ── helpers ───────────────────────────────────────────────────────────────────

// Returns the contact frame index in the (possibly normalized) frames array.
function contactIdxOf(r, normalize) {
  if (r.contact_frame == null || r.start_frame == null) return null
  if (normalize && r.end_frame != null && r.end_frame > r.start_frame) {
    return Math.round(
      (r.contact_frame - r.start_frame) / (r.end_frame - r.start_frame) * 99
    )
  }
  return r.contact_frame - r.start_frame
}

// Returns a 100-element array of feature values shifted so contactIdx → ALIGN_CENTER.
// Out-of-bounds positions become null.
function alignToContact(frames, contactIdx, feature) {
  const ALIGN_CENTER = 50
  return Array.from({ length: 100 }, (_, i) => {
    const src = i + contactIdx - ALIGN_CENTER
    if (src < 0 || src >= frames.length) return null
    return frames[src].features?.[feature] ?? null
  })
}

// ── sub-components ────────────────────────────────────────────────────────────

function StrokeSlot({ index, slot, videos, strokesByVideo, loadingVideo, onVideoChange, onStrokeChange, color, onRemove, canRemove }) {
  const strokes = strokesByVideo[slot.videoId] || []
  const isLoadingStrokes = loadingVideo === slot.videoId

  return (
    <div className="bg-gray-800 border-2 rounded-lg p-3 space-y-2 flex-1 min-w-[220px]" style={{ borderColor: color + '60' }}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold" style={{ color }}>Удар {index + 1}</span>
        {canRemove && (
          <button onClick={onRemove} className="text-gray-500 hover:text-red-400 text-xs leading-none">✕</button>
        )}
      </div>

      <select
        value={slot.videoId}
        onChange={e => onVideoChange(index, e.target.value)}
        className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-xs text-white"
      >
        <option value="">— Выберите видео —</option>
        {videos.map(v => (
          <option key={v.id} value={v.id}>{v.original_name || v.filename}</option>
        ))}
      </select>

      <select
        value={slot.strokeId ?? ''}
        onChange={e => onStrokeChange(index, e.target.value ? parseInt(e.target.value) : null)}
        disabled={!slot.videoId || isLoadingStrokes}
        className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-xs text-white disabled:opacity-50"
      >
        <option value="">
          {isLoadingStrokes ? '⏳ Загрузка...' : strokes.length === 0 && slot.videoId ? '— Нет ударов —' : '— Выберите удар —'}
        </option>
        {strokes.map(s => (
          <option key={s.id} value={s.id}>
            #{s.id} {TYPE_NAMES[s.type] || s.type || '?'}
            {s.start_frame != null ? ` (${s.start_frame}–${s.end_frame})` : ''}
          </option>
        ))}
      </select>
    </div>
  )
}

function CompareChart({ results, feature, displayMode }) {
  const normalize = displayMode !== 'raw'
  const alignContact = displayMode === 'contact'

  const withFrames = results.filter(r => r.frames?.length > 0)
  if (!withFrames.length) return null

  // ── build chart data ───────────────────────────────────────────────────────

  let chartData, xDataKey, xAxisLabel, tooltipFormatter

  if (alignContact) {
    // 100 points; x = position relative to contact (-50 … +49).
    // Each stroke is independently shifted so its contact frame lands at x=0.
    chartData = Array.from({ length: 100 }, (_, i) => {
      const pt = { relIdx: i - 50 }
      results.forEach((r, si) => {
        if (!r.frames?.length) return
        const ci = contactIdxOf(r, true)
        if (ci == null) { pt[`s${si}`] = null; return }
        const aligned = alignToContact(r.frames, ci, feature)
        pt[`s${si}`] = aligned[i]
      })
      return pt
    })
    xDataKey = 'relIdx'
    xAxisLabel = 'Нормированное время (до/после контакта)'
    tooltipFormatter = v => `${v > 0 ? '+' : ''}${v} от контакта`
  } else {
    // Original behaviour: raw frames or normalized 100-point frames.
    const maxLen = Math.max(...withFrames.map(r => r.frames.length))
    chartData = Array.from({ length: maxLen }, (_, i) => {
      const pt = { idx: i }
      results.forEach((r, si) => {
        if (r.frames?.[i]) pt[`s${si}`] = r.frames[i].features?.[feature]
      })
      return pt
    })
    xDataKey = 'idx'
    xAxisLabel = normalize ? 'кадр (%)' : 'кадр от старта'
    tooltipFormatter = v => normalize ? `${v}%` : `кадр +${v}`
  }

  // ── render ────────────────────────────────────────────────────────────────

  return (
    <div className="bg-gray-800 rounded-lg p-3">
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <h3 className="text-xs font-medium text-white">{feature.replace(/_/g, ' ')}</h3>
        {alignContact && (
          <span className="text-xs text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded">
            выравнено по контакту
          </span>
        )}
        {normalize && !alignContact && (
          <span className="text-xs text-gray-500">нормализовано (100 точек)</span>
        )}
        <span className="text-xs text-gray-600">— пунктир: кадр контакта</span>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ right: 10 }}>
          <XAxis
            dataKey={xDataKey}
            tick={{ fontSize: 9, fill: '#9ca3af' }}
            label={{
              value: xAxisLabel,
              position: 'insideBottomRight',
              offset: -5,
              fontSize: 9,
              fill: '#6b7280',
            }}
          />
          <YAxis tick={{ fontSize: 9, fill: '#9ca3af' }} width={38} />
          <Tooltip
            contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 10 }}
            labelFormatter={tooltipFormatter}
          />
          <Legend wrapperStyle={{ fontSize: 10 }} iconType="plainline" />

          {/* Lines for every stroke */}
          {results.map((r, si) => {
            if (!r.frames?.length) return null
            const label = `#${r.stroke_id} ${TYPE_NAMES[r.type] || r.type || '?'} — ${r.video_id}`
            return (
              <Line
                key={si}
                type="monotone"
                dataKey={`s${si}`}
                stroke={STROKE_COLORS[si]}
                strokeWidth={2}
                dot={false}
                name={label}
                connectNulls
              />
            )
          })}

          {/* Contact alignment mode: single shared reference line at x=0 */}
          {alignContact && (
            <ReferenceLine
              x={0}
              stroke="#f59e0b"
              strokeDasharray="4 2"
              strokeOpacity={0.9}
              strokeWidth={1.5}
              label={{ value: 'контакт', position: 'insideTopRight', fontSize: 9, fill: '#f59e0b' }}
            />
          )}

          {/* Time mode: per-stroke reference lines at each stroke's contact position */}
          {!alignContact && results.map((r, si) => {
            if (!r.frames?.length) return null
            const ci = contactIdxOf(r, normalize)
            if (ci == null) return null
            return (
              <ReferenceLine
                key={`ref-${si}`}
                x={ci}
                stroke={STROKE_COLORS[si]}
                strokeDasharray="4 2"
                strokeOpacity={0.6}
                strokeWidth={1.5}
              />
            )
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function SummaryTable({ results }) {
  if (!results.length) return null

  const rows = [
    { label: 'Видео',       get: r => r.video_id },
    { label: 'Тип',         get: r => TYPE_NAMES[r.type] || r.type || '—' },
    { label: 'Качество',    get: r => r.quality != null ? `${Number(r.quality).toFixed(1)} / 10` : '—' },
    { label: 'Длительность',get: r => r.duration != null ? `${r.duration} с` : '—' },
    { label: 'Кадры',       get: r => r.start_frame != null ? `${r.start_frame} – ${r.end_frame}` : '—' },
    { label: 'Ошибки',      get: r => r.errors?.length > 0 ? r.errors.join(', ') : '—' },
    { label: 'Источник',    get: r => r.error ? `⚠ ${r.error}` : r.source === 'analysis' ? 'Анализ' : 'Разметка' },
  ]

  return (
    <div className="bg-gray-800 rounded-lg p-3 overflow-x-auto">
      <h3 className="text-xs text-gray-400 mb-2">Сводная таблица</h3>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left text-gray-500 py-1.5 pr-6 font-normal whitespace-nowrap">Параметр</th>
            {results.map((r, i) => (
              <th key={i} className="text-left py-1.5 px-3 font-semibold whitespace-nowrap" style={{ color: STROKE_COLORS[i] }}>
                Удар #{r.stroke_id}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700/40">
          {rows.map(({ label, get }) => (
            <tr key={label} className="hover:bg-gray-700/30 transition-colors">
              <td className="py-1.5 pr-6 text-gray-400 whitespace-nowrap">{label}</td>
              {results.map((r, i) => (
                <td key={i} className={`py-1.5 px-3 ${r.error && label === 'Источник' ? 'text-red-400' : 'text-gray-200'}`}>
                  {get(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function ComparePage() {
  const [slots, setSlots] = useState([
    { videoId: '', strokeId: null },
    { videoId: '', strokeId: null },
  ])
  const [displayMode, setDisplayMode]         = useState('normalized')
  const [selectedFeature, setSelectedFeature] = useState('right_wrist_speed')
  const [videos, setVideos]                   = useState([])
  const [strokesByVideo, setStrokesByVideo]   = useState({})
  const [loadingVideo, setLoadingVideo]       = useState(null)
  const [compareResult, setCompareResult]     = useState(null)
  const [comparing, setComparing]             = useState(false)
  const [error, setError]                     = useState(null)

  // Tracks which normalize flag was used for the last compare.
  // When the user changes displayMode in a way that requires different API data,
  // we show a hint to re-compare.
  const [resultWasNormalized, setResultWasNormalized] = useState(null)

  useEffect(() => {
    getVideos().then(r => setVideos(r.videos || [])).catch(() => {})
  }, [])

  const loadStrokesForVideo = useCallback(async (videoId) => {
    if (!videoId || strokesByVideo[videoId] !== undefined) return
    setLoadingVideo(videoId)
    try {
      const result = await getAnalysisResult(videoId)
      setStrokesByVideo(prev => ({
        ...prev,
        [videoId]: (result.strokes || []).map(s => ({
          id: s.id,
          type: s.predicted_type || s.type,
          start_frame: s.start_frame,
          end_frame: s.end_frame,
        })),
      }))
    } catch {
      try {
        const ann = await getAnnotation(videoId)
        setStrokesByVideo(prev => ({
          ...prev,
          [videoId]: (ann.strokes || []).map(s => ({
            id: s.id,
            type: s.type,
            start_frame: s.start_frame,
            end_frame: s.end_frame,
          })),
        }))
      } catch {
        setStrokesByVideo(prev => ({ ...prev, [videoId]: [] }))
      }
    } finally {
      setLoadingVideo(null)
    }
  }, [strokesByVideo])

  const handleVideoChange = (idx, videoId) => {
    setSlots(prev => prev.map((s, i) => i === idx ? { videoId, strokeId: null } : s))
    if (videoId) loadStrokesForVideo(videoId)
  }

  const handleStrokeChange = (idx, strokeId) => {
    setSlots(prev => prev.map((s, i) => i === idx ? { ...s, strokeId } : s))
  }

  const handleAddSlot = () => {
    if (slots.length < 3) setSlots(prev => [...prev, { videoId: '', strokeId: null }])
  }

  const handleRemoveSlot = (idx) => {
    setSlots(prev => prev.filter((_, i) => i !== idx))
    setCompareResult(null)
  }

  const validSlots = slots.filter(s => s.videoId && s.strokeId != null)
  const canCompare = validSlots.length >= 2 && !comparing

  // 'raw' mode sends normalize=false; 'normalized' and 'contact' both send normalize=true
  const apiNormalize = displayMode !== 'raw'

  const handleCompare = async () => {
    if (!canCompare) return
    setComparing(true)
    setError(null)
    setCompareResult(null)
    try {
      const result = await compareStrokes(
        validSlots.map(s => ({ video_id: s.videoId, stroke_id: s.strokeId })),
        apiNormalize,
      )
      setCompareResult(result)
      setResultWasNormalized(apiNormalize)
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Ошибка при сравнении')
    } finally {
      setComparing(false)
    }
  }

  const results = compareResult?.strokes || []
  const hasFrames = results.some(r => r.frames?.length > 0)

  // Show a hint when the user changes the normalization mode after comparing
  // but hasn't re-compared yet (so the chart data may not match the new mode).
  const normalizeModeMismatch =
    compareResult != null &&
    resultWasNormalized != null &&
    resultWasNormalized !== apiNormalize

  // 'contact' alignment requires normalized data — warn if the last result used raw frames.
  const contactWithRawData =
    displayMode === 'contact' && resultWasNormalized === false

  return (
    <div className="space-y-5 max-w-5xl mx-auto">

      {/* Заголовок */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold">Сравнение ударов</h1>
        {slots.length < 3 && (
          <button
            onClick={handleAddSlot}
            className="px-3 py-1.5 text-xs rounded bg-gray-700 hover:bg-gray-600 transition-colors"
          >
            + Добавить 3-й удар
          </button>
        )}
      </div>

      {/* Слоты выбора */}
      <div className="flex gap-3 flex-wrap">
        {slots.map((slot, idx) => (
          <StrokeSlot
            key={idx}
            index={idx}
            slot={slot}
            videos={videos}
            strokesByVideo={strokesByVideo}
            loadingVideo={loadingVideo}
            onVideoChange={handleVideoChange}
            onStrokeChange={handleStrokeChange}
            color={STROKE_COLORS[idx]}
            onRemove={() => handleRemoveSlot(idx)}
            canRemove={slots.length > 2}
          />
        ))}
      </div>

      {/* Настройки + кнопка */}
      <div className="bg-gray-800 rounded-lg px-4 py-3 space-y-3">
        {/* Режим отображения */}
        <div className="flex flex-col gap-1.5">
          <span className="text-xs text-gray-400 font-medium">Режим графика:</span>
          <div className="flex flex-wrap gap-x-5 gap-y-1.5">
            {DISPLAY_MODES.map(({ value, label }) => (
              <label
                key={value}
                className="flex items-center gap-1.5 text-sm text-gray-300 cursor-pointer select-none"
              >
                <input
                  type="radio"
                  name="displayMode"
                  value={value}
                  checked={displayMode === value}
                  onChange={() => setDisplayMode(value)}
                  className="accent-blue-500"
                />
                {label}
              </label>
            ))}
          </div>
        </div>

        {/* Признак + кнопка «Сравнить» */}
        <div className="flex items-start gap-2 flex-wrap pt-1">
          <div className="flex flex-col gap-1 flex-1 min-w-[240px]">
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 whitespace-nowrap">Признак:</span>
              <select
                value={selectedFeature}
                onChange={e => setSelectedFeature(e.target.value)}
                className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs text-white flex-1"
              >
                {FEATURE_GROUPS.map(({ label, features }) => (
                  <optgroup key={label} label={label}>
                    {features.map(f => (
                      <option key={f} value={f}>
                        {FEATURE_LABELS[f]?.name ?? f.replace(/_/g, ' ')}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
            {FEATURE_LABELS[selectedFeature] && (
              <p className="text-xs text-gray-500 pl-[52px] leading-snug">
                <span className="text-gray-600 font-mono">{selectedFeature}</span>
                {' — '}
                {FEATURE_LABELS[selectedFeature].desc}
              </p>
            )}
          </div>

          <button
            onClick={handleCompare}
            disabled={!canCompare}
            className="px-5 py-1.5 text-sm font-medium rounded bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors self-start"
          >
            {comparing ? '⏳ Загрузка...' : '⚡ Сравнить'}
          </button>
        </div>
      </div>

      {/* Предупреждения */}
      {normalizeModeMismatch && (
        <div className="text-xs px-3 py-2 rounded bg-yellow-900/30 text-yellow-300 border border-yellow-800">
          Режим изменён — нажмите «Сравнить» снова, чтобы получить данные для нового режима.
        </div>
      )}
      {contactWithRawData && (
        <div className="text-xs px-3 py-2 rounded bg-yellow-900/30 text-yellow-300 border border-yellow-800">
          Режим «По контакту» требует нормализованных данных. Нажмите «Сравнить» ещё раз.
        </div>
      )}

      {/* Ошибка */}
      {error && (
        <div className="text-xs px-3 py-2 rounded bg-red-900/40 text-red-300 border border-red-800">
          ⚠ {error}
        </div>
      )}

      {/* Результаты */}
      {results.length > 0 && (
        <div className="space-y-4">
          {hasFrames ? (
            <CompareChart
              results={results}
              feature={selectedFeature}
              displayMode={displayMode}
            />
          ) : (
            <div className="text-sm text-center text-gray-500 py-8 bg-gray-800 rounded-lg border border-gray-700">
              Признаки не найдены ни для одного удара.
              <br />
              <span className="text-xs text-gray-600">Запустите анализ видео, затем повторите сравнение.</span>
            </div>
          )}
          <SummaryTable results={results} />
        </div>
      )}

      {/* Подсказка, пока не выбраны оба удара */}
      {!compareResult && !comparing && (
        <div className="text-xs text-gray-600 text-center py-4">
          Выберите видео и удар в каждом слоте, затем нажмите «Сравнить».
        </div>
      )}
    </div>
  )
}
