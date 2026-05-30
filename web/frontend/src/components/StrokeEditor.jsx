import React, { useState, useEffect } from 'react'

const STROKE_TYPES = [
  { value: 'drive_forehand', label: 'Drive FH', key: '1' },
  { value: 'topspin_forehand', label: 'Topspin FH', key: '2' },
  { value: 'slice_forehand', label: 'Slice FH', key: '3' },
  { value: 'drive_backhand', label: 'Drive BH', key: '4' },
  { value: 'topspin_backhand', label: 'Topspin BH', key: '5' },
  { value: 'slice_backhand', label: 'Slice BH', key: '6' },
  { value: 'other', label: 'Другой', key: '7' },
]

const ERROR_TYPES = [
  { value: 'straight_legs', label: 'Прямые ноги', key: 'q' },
  { value: 'big_swing', label: 'Большой замах', key: 'w' },
  { value: 'straight_arm', label: 'Прямая рука', key: 'e' },
  { value: 'straight_body', label: 'Прямой корпус', key: 'r' },
  { value: 'raised_shoulder', label: 'Поднятое плечо', key: 't' },
  { value: 'raised_elbow', label: 'Поднятый локоть', key: 'y' },
  { value: 'wrist_up', label: 'Кисть вверх', key: 'u' },
  { value: 'low_backswing', label: 'Низкий замах', key: 'i' },
  { value: 'no_forearm', label: 'Нет работы предплечья', key: 'o' },
  { value: 'sideways_finish', label: 'Завершение вбок', key: 'p' },
  { value: 'wrist_bent_fwd', label: 'Кисть вперёд', key: 'a' },
  { value: 'wrist_bent_back', label: 'Кисть назад', key: 's' },
  { value: 'arm_far', label: 'Рука далеко', key: 'd' },
  { value: 'straight_line', label: 'Прямая линия', key: 'f' },
  { value: 'low_elbow_end', label: 'Низкий локоть', key: 'g' },
  { value: 'left_hand_up', label: 'Левая рука вверх', key: 'z' },
  { value: 'no_rotation', label: 'Нет вращения', key: 'x' },
  { value: 'incomplete_follow_through', label: 'Неполное завершение', key: 'c' },
  { value: 'left_hand_behind_body', label: 'Левая за спиной', key: 'v' },
  { value: 'vertical_swing', label: 'Вертикальный замах', key: 'b' },
]

/**
 * Редактор одного удара: тип, ошибки, качество.
 */
export default function StrokeEditor({ stroke, onUpdate, onClose }) {
  const [type, setType] = useState(stroke?.type || 'other')
  const [errors, setErrors] = useState(stroke?.errors || [])
  const [quality, setQuality] = useState(stroke?.quality || 5)
  const [notes, setNotes] = useState(stroke?.notes || '')

  useEffect(() => {
    if (stroke) {
      setType(stroke.type || 'other')
      setErrors(stroke.errors || [])
      setQuality(stroke.quality || 5)
      setNotes(stroke.notes || '')
    }
  }, [stroke])

  if (!stroke) return null

  const toggleError = (errValue) => {
    setErrors(prev =>
      prev.includes(errValue)
        ? prev.filter(e => e !== errValue)
        : [...prev, errValue]
    )
  }

  const handleSave = () => {
    onUpdate(stroke.id, { type, errors, quality, notes })
  }

  return (
    <div className="bg-gray-800 border border-gray-600 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-white">
          Редактирование удара #{stroke.id}
        </h3>
        <button onClick={onClose} className="text-gray-400 hover:text-white text-sm">✕</button>
      </div>

      {/* Кадры (только чтение) */}
      <div className="text-xs text-gray-400 space-y-1">
        <div>Начало: кадр {stroke.start_frame}</div>
        <div>Контакт: кадр {stroke.contact_frame ?? '—'}</div>
        <div>Конец: кадр {stroke.end_frame}</div>
      </div>

      {/* Тип удара */}
      <div>
        <label className="text-xs text-gray-400 mb-1 block">Тип удара:</label>
        <div className="grid grid-cols-2 gap-1">
          {STROKE_TYPES.map(({ value, label, key }) => (
            <button
              key={value}
              onClick={() => setType(value)}
              className={`text-xs px-2 py-1 rounded border transition-colors ${
                type === value
                  ? 'bg-blue-600 border-blue-500 text-white'
                  : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
              }`}
            >
              <span className="text-gray-500 mr-1">{key}</span>{label}
            </button>
          ))}
        </div>
      </div>

      {/* Ошибки */}
      <div>
        <label className="text-xs text-gray-400 mb-1 block">
          Ошибки ({errors.length}):
        </label>
        <div className="grid grid-cols-2 gap-1 max-h-[200px] overflow-y-auto">
          {ERROR_TYPES.map(({ value, label, key }) => (
            <button
              key={value}
              onClick={() => toggleError(value)}
              className={`text-xs px-2 py-1 rounded border text-left transition-colors ${
                errors.includes(value)
                  ? 'bg-red-900/50 border-red-500 text-red-200'
                  : 'bg-gray-700 border-gray-600 text-gray-400 hover:bg-gray-600'
              }`}
            >
              <span className="text-gray-500 mr-1">{key}</span>{label}
            </button>
          ))}
        </div>
      </div>

      {/* Качество */}
      <div>
        <label className="text-xs text-gray-400 mb-1 block">
          Качество: {quality}/10
        </label>
        <input
          type="range"
          min="1"
          max="10"
          value={quality}
          onChange={(e) => setQuality(parseInt(e.target.value))}
          className="w-full"
        />
        <div className="flex justify-between text-xs text-gray-600">
          <span>1 (плохо)</span>
          <span>5 (средне)</span>
          <span>10 (отлично)</span>
        </div>
      </div>

      {/* Заметки */}
      <div>
        <label className="text-xs text-gray-400 mb-1 block">Заметки:</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-white resize-none"
          rows={2}
          placeholder="Комментарий..."
        />
      </div>

      {/* Кнопки */}
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          className="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-sm py-1.5 rounded"
        >
          Сохранить
        </button>
        <button
          onClick={onClose}
          className="px-4 bg-gray-600 hover:bg-gray-500 text-white text-sm py-1.5 rounded"
        >
          Отмена
        </button>
      </div>
    </div>
  )
}