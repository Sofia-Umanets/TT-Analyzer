import React from 'react'

const TYPE_NAMES = {
  drive_forehand:   'Drive FH',
  topspin_forehand: 'Topspin FH',
  slice_forehand:   'Slice FH',
  drive_backhand:   'Drive BH',
  topspin_backhand: 'Topspin BH',
  slice_backhand:   'Slice BH',
  other:            'Другой',
}

const ERR_SHORT = {
  arm_far:                   'Рука далеко',
  big_swing:                 'Большой замах',
  incomplete_follow_through: 'Неполное завершение',
  left_hand_behind_body:     'Левая за спиной',
  left_hand_up:              'Левая вверх',
  low_backswing:             'Замах снизу',
  low_elbow_end:             'Низкий локоть',
  no_forearm:                'Нет предплечья',
  no_rotation:               'Нет вращения',
  raised_elbow:              'Поднят локоть',
  raised_shoulder:           'Поднято плечо',
  sideways_finish:           'Вбок',
  straight_arm:              'Прямая рука',
  straight_body:             'Прямой корпус',
  straight_legs:             'Прямые ноги',
  straight_line:             'По прямой',
  vertical_swing:            'Снизу вверх',
  wrist_bent_back:           'Кисть назад',
  wrist_bent_fwd:            'Кисть вперёд',
  wrist_up:                  'Кисть вверх',
}

/**
 * Список сохранённых ударов.
 * Клик по строке — переход к start_frame.
 * Кнопка ✎ — переход к start_frame + загрузка в панель редактирования.
 */
export default function StrokeList({ strokes, editingId, onEdit, onDelete, onSeek }) {
  if (!strokes?.length) {
    return (
      <div className="text-gray-500 text-sm text-center py-4">
        Нет размеченных ударов
      </div>
    )
  }

  return (
    <div className="space-y-1 max-h-[420px] overflow-y-auto pr-0.5">
      {strokes.map((s) => {
        const isEditing = s.id === editingId
        return (
          <div
            key={s.id}
            className={`rounded border text-xs transition-colors ${
              isEditing
                ? 'bg-blue-900/40 border-blue-500'
                : 'bg-gray-800/80 border-gray-700'
            }`}
          >
            {/* Верхняя строка: id, тип, качество, кнопки */}
            <div className="flex items-center justify-between px-2 py-1 gap-1">
              <button
                onClick={() => onSeek?.(s.start_frame)}
                className="flex items-center gap-1.5 flex-1 min-w-0 text-left hover:text-white transition-colors"
                title="Перейти к началу"
              >
                <span className="text-gray-500 font-mono shrink-0">#{s.id}</span>
                <span className="font-medium text-gray-200 truncate">
                  {TYPE_NAMES[s.type] || s.type}
                </span>
                {s.quality != null && (
                  <span className={`shrink-0 px-1 rounded ${
                    s.quality >= 7 ? 'bg-green-800 text-green-200' :
                    s.quality >= 4 ? 'bg-yellow-800 text-yellow-200' :
                                     'bg-red-800 text-red-200'
                  }`}>
                    Q{s.quality}
                  </span>
                )}
                {s.auto_detected && (
                  <span className="shrink-0 bg-gray-700 text-gray-400 px-1 rounded">авто</span>
                )}
              </button>

              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => onEdit?.(s)}
                  className={`px-1.5 py-0.5 rounded text-xs transition-colors ${
                    isEditing
                      ? 'bg-blue-500 text-white'
                      : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                  }`}
                  title="Редактировать"
                >
                  ✎
                </button>
                <button
                  onClick={() => {
                    if (window.confirm(`Удалить удар #${s.id}?`)) onDelete?.(s.id)
                  }}
                  className="px-1.5 py-0.5 rounded bg-gray-700 hover:bg-red-700 text-gray-300 transition-colors"
                  title="Удалить"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Нижняя строка: кадры S→C→E и ошибки */}
            <div className="px-2 pb-1 font-mono text-gray-500 leading-tight">
              <span className="text-yellow-600">{s.start_frame ?? '?'}</span>
              <span className="text-gray-600"> → </span>
              <span className="text-red-500">{s.contact_frame ?? '?'}</span>
              <span className="text-gray-600"> → </span>
              <span className="text-green-600">{s.end_frame ?? '?'}</span>
              {s.errors?.length > 0 && (
                <span className="text-orange-400 ml-2 font-sans">
                  {s.errors.slice(0, 2).map(e => ERR_SHORT[e] || e).join(', ')}
                  {s.errors.length > 2 && ` +${s.errors.length - 2}`}
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
