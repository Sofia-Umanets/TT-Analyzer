import React, { useState, useEffect, useRef } from 'react'
import { getErrorTypes } from '../api/client'

const STROKE_TYPES = [
  { value: 'drive_forehand',    label: 'Drive FH' },
  { value: 'topspin_forehand',  label: 'Topspin FH' },
  { value: 'slice_forehand',    label: 'Slice FH' },
  { value: 'drive_backhand',    label: 'Drive BH' },
  { value: 'topspin_backhand',  label: 'Topspin BH' },
  { value: 'slice_backhand',    label: 'Slice BH' },
  { value: 'other',             label: 'Другой' },
]

const FALLBACK_ERRORS = [
  { value: 'arm_far',                   label: 'Рука далеко от корпуса' },
  { value: 'big_swing',                 label: 'Слишком большой замах' },
  { value: 'incomplete_follow_through', label: 'Не доводит движение' },
  { value: 'left_hand_behind_body',     label: 'Левая рука за корпусом' },
  { value: 'left_hand_up',              label: 'Поднята левая рука' },
  { value: 'low_backswing',             label: 'Замах снизу' },
  { value: 'low_elbow_end',             label: 'Локоть низко в конце' },
  { value: 'no_forearm',                label: 'Нет работы предплечья' },
  { value: 'no_rotation',               label: 'Нет вращения корпуса' },
  { value: 'raised_elbow',              label: 'Поднят локоть' },
  { value: 'raised_shoulder',           label: 'Поднято плечо' },
  { value: 'sideways_finish',           label: 'Концовка вбок' },
  { value: 'straight_arm',              label: 'Прямая рука в конце' },
  { value: 'straight_body',             label: 'Прямой корпус' },
  { value: 'straight_legs',             label: 'Прямые ноги' },
  { value: 'straight_line',             label: 'Движение по прямой' },
  { value: 'vertical_swing',            label: 'Движение снизу вверх' },
  { value: 'wrist_bent_back',           label: 'Кисть выгнута назад' },
  { value: 'wrist_bent_fwd',            label: 'Кисть согнута вперёд' },
  { value: 'wrist_up',                  label: 'Кисть вверх в конце' },
]

const ERR_LABEL = Object.fromEntries(FALLBACK_ERRORS.map(e => [e.value, e.label]))

/**
 * Панель разметки в стиле web1/annotate.html.
 * S/C/E работают в любой момент — без wizard-шагов.
 * Props:
 *   currentFrame   — текущий кадр видео
 *   editingStroke  — null | stroke-объект при редактировании существующего удара
 *   onSave(marks, type, quality, errors, editingId?)
 *   onCancel()
 *   onMarksChange({start_frame, contact_frame, end_frame}) — для Timeline
 */
export default function AnnotationPanel({
  frameRef,       // прямой ref из useVideo — всегда актуальный кадр без React-рендеров
  editingStroke,
  onSave,
  onCancel,
  onMarksChange,
}) {
  const [marks, setMarks]       = useState({ start: null, contact: null, end: null })
  const [type, setType]         = useState('drive_forehand')
  const [quality, setQuality]   = useState(5)
  const [errors, setErrors]     = useState([])
  const [errorTypes, setErrorTypes] = useState(FALLBACK_ERRORS)
  const [saving, setSaving]     = useState(false)
  const [editingId, setEditingId] = useState(null)

  // frameRef приходит снаружи (video.currentFrameRef) и всегда содержит текущий кадр.
  // Это убирает useEffect-синхронизацию из currentFrame-пропа и связанные ре-рендеры.
  const currentFrameRef = frameRef ?? useRef(0)

  const canAddRef = useRef(false)

  // Загружаем типы ошибок из бэкенда один раз
  useEffect(() => {
    getErrorTypes()
      .then(d => {
        if (d?.error_types?.length) {
          setErrorTypes(d.error_types.map(v => ({ value: v, label: ERR_LABEL[v] || v })))
        }
      })
      .catch(() => {}) // при ошибке остаются FALLBACK_ERRORS
  }, [])

  // Заполняем форму при переходе в режим редактирования
  useEffect(() => {
    if (!editingStroke) return
    setMarks({
      start:   editingStroke.start_frame   ?? null,
      contact: editingStroke.contact_frame ?? null,
      end:     editingStroke.end_frame     ?? null,
    })
    setType(editingStroke.type    || 'drive_forehand')
    setQuality(editingStroke.quality || 5)
    setErrors(editingStroke.errors  || [])
    setEditingId(editingStroke.id)
  }, [editingStroke])

  // Сообщаем Timeline о текущих метках
  useEffect(() => {
    onMarksChange?.({
      start_frame:   marks.start,
      contact_frame: marks.contact,
      end_frame:     marks.end,
    })
  }, [marks, onMarksChange])

  const canAdd = (
    marks.start   !== null && marks.contact !== null && marks.end !== null &&
    marks.start    <  marks.contact &&
    marks.contact  <= marks.end
  )
  canAddRef.current = canAdd

  const clearMarks = () => {
    setMarks({ start: null, contact: null, end: null })
    setEditingId(null)
    setErrors([])
    onCancel?.()
  }

  const toggleError = (v) =>
    setErrors(prev => prev.includes(v) ? prev.filter(e => e !== v) : [...prev, v])

  const handleAdd = async () => {
    if (!canAddRef.current || saving) return
    setSaving(true)
    try {
      await onSave(marks, type, quality, errors, editingId)
      setMarks({ start: null, contact: null, end: null })
      setEditingId(null)
      setErrors([])
    } finally {
      setSaving(false)
    }
  }
  // Ref для hotkey-замыкания
  const handleAddRef = useRef(handleAdd)
  handleAddRef.current = handleAdd

  // Горячие клавиши: S/C/E всегда работают, Enter сохраняет
  useEffect(() => {
    const handler = (e) => {
      const tag = document.activeElement?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      const key = e.key
      if (key === 's' || key === 'S') {
        e.preventDefault()
        setMarks(m => ({ ...m, start: currentFrameRef.current }))
        return
      }
      if (key === 'c' || key === 'C') {
        e.preventDefault()
        setMarks(m => ({ ...m, contact: currentFrameRef.current }))
        return
      }
      if (key === 'e' || key === 'E') {
        e.preventDefault()
        setMarks(m => ({ ...m, end: currentFrameRef.current }))
        return
      }
      if (key === 'Escape') {
        e.preventDefault()
        clearMarks()
        return
      }
      if (key === 'Enter' && canAddRef.current) {
        e.preventDefault()
        handleAddRef.current()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, []) // empty — все переменные через refs

  const invalid = marks.start !== null && marks.contact !== null && marks.end !== null && !canAdd

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 space-y-2.5 text-sm">

      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <span className="font-bold text-white">
          {editingId ? `✎ Удар #${editingId}` : 'Новый удар'}
        </span>
        {editingId && (
          <button
            onClick={clearMarks}
            className="text-xs text-gray-400 hover:text-white"
          >
            ✕ Отмена
          </button>
        )}
      </div>

      {/* Три кнопки меток */}
      <div className="grid grid-cols-3 gap-1">
        <button
          onClick={() => setMarks(m => ({ ...m, start: currentFrameRef.current }))}
          className="py-2 rounded border-2 border-yellow-600 bg-yellow-900/30 hover:bg-yellow-900/60 active:bg-yellow-800 text-yellow-300 transition-colors"
        >
          <div className="text-xs font-bold">
            Start <kbd className="text-gray-500 font-normal text-xs">S</kbd>
          </div>
          <div className="font-mono text-sm text-yellow-400">
            {marks.start ?? '—'}
          </div>
        </button>

        <button
          onClick={() => setMarks(m => ({ ...m, contact: currentFrameRef.current }))}
          className="py-2 rounded border-2 border-red-600 bg-red-900/30 hover:bg-red-900/60 active:bg-red-800 text-red-300 transition-colors"
        >
          <div className="text-xs font-bold">
            Contact <kbd className="text-gray-500 font-normal text-xs">C</kbd>
          </div>
          <div className="font-mono text-sm text-red-400">
            {marks.contact ?? '—'}
          </div>
        </button>

        <button
          onClick={() => setMarks(m => ({ ...m, end: currentFrameRef.current }))}
          className="py-2 rounded border-2 border-green-600 bg-green-900/30 hover:bg-green-900/60 active:bg-green-800 text-green-300 transition-colors"
        >
          <div className="text-xs font-bold">
            End <kbd className="text-gray-500 font-normal text-xs">E</kbd>
          </div>
          <div className="font-mono text-sm text-green-400">
            {marks.end ?? '—'}
          </div>
        </button>
      </div>

      {invalid && (
        <p className="text-xs text-red-400 bg-red-900/20 rounded px-2 py-1">
          ⚠ Нужно: Start &lt; Contact ≤ End
        </p>
      )}

      {/* Тип удара */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-gray-400 w-8 shrink-0">Тип:</label>
        <select
          value={type}
          onChange={e => setType(e.target.value)}
          className="flex-1 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-white"
        >
          {STROKE_TYPES.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      {/* Качество */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-gray-400 w-8 shrink-0">
          Q: <span className="text-white font-bold">{quality}</span>
        </label>
        <input
          type="range" min="1" max="10" value={quality}
          onChange={e => setQuality(Number(e.target.value))}
          className="flex-1"
        />
        <span className="text-xs text-gray-500 w-14 text-right">
          {quality < 4 ? 'плохо' : quality < 7 ? 'средне' : 'хорошо'}
        </span>
      </div>

      {/* Ошибки */}
      <div>
        <div className="text-xs text-gray-400 mb-1">
          Ошибки{errors.length > 0 && (
            <span className="text-red-400 ml-1">({errors.length})</span>
          )}:
        </div>
        <div className="grid grid-cols-2 gap-0.5 max-h-40 overflow-y-auto pr-0.5">
          {errorTypes.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => toggleError(value)}
              className={`text-xs px-1.5 py-0.5 rounded border text-left leading-snug transition-colors ${
                errors.includes(value)
                  ? 'bg-red-900/60 border-red-600 text-red-200'
                  : 'bg-gray-700/50 border-gray-700 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Кнопки добавить / сбросить */}
      <div className="flex gap-1.5">
        <button
          onClick={handleAdd}
          disabled={!canAdd || saving}
          className={`flex-1 py-2 rounded font-bold transition-colors ${
            canAdd && !saving
              ? editingId
                ? 'bg-blue-600 hover:bg-blue-500 text-white'
                : 'bg-green-700 hover:bg-green-600 text-white'
              : 'bg-gray-700 text-gray-500 cursor-not-allowed'
          }`}
        >
          {saving ? '…'
            : editingId ? `Обновить #${editingId} ↵`
            : 'Добавить ↵'}
        </button>
        <button
          onClick={clearMarks}
          className={`px-3 py-2 rounded text-xs ${
            editingId
              ? 'bg-gray-700 hover:bg-gray-600 text-orange-400 hover:text-orange-300'
              : 'bg-gray-700 hover:bg-gray-600 text-gray-400'
          }`}
          title={editingId ? 'Отменить редактирование (Esc)' : 'Сбросить метки (Esc)'}
        >
          {editingId ? 'Отменить' : 'Esc'}
        </button>
      </div>

      <div className="text-xs text-gray-600 leading-relaxed">
        <kbd className="bg-gray-700 px-1 rounded">S</kbd> старт ·{' '}
        <kbd className="bg-gray-700 px-1 rounded">C</kbd> контакт ·{' '}
        <kbd className="bg-gray-700 px-1 rounded">E</kbd> конец ·{' '}
        <kbd className="bg-gray-700 px-1 rounded">↵</kbd> добавить ·{' '}
        <kbd className="bg-gray-700 px-1 rounded">Esc</kbd> сброс
      </div>
    </div>
  )
}
