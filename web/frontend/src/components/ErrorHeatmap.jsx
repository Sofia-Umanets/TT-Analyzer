import React from 'react'

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

export default function ErrorHeatmap({ errorProbabilities, errors }) {
  if (!errorProbabilities || Object.keys(errorProbabilities).length === 0) {
    return null
  }

  const sorted = Object.entries(errorProbabilities)
    .sort((a, b) => b[1] - a[1])

  const getColor = (prob) => {
    if (prob > 0.7) return 'bg-red-600'
    if (prob > 0.5) return 'bg-orange-600'
    if (prob > 0.3) return 'bg-yellow-600'
    if (prob > 0.1) return 'bg-gray-600'
    return 'bg-gray-700'
  }

  return (
    <div className="space-y-1">
      {sorted.map(([name, prob]) => {
        const isDetected = errors?.includes(name)
        return (
          <div key={name} className="flex items-center gap-2 text-sm">
            <div className="w-44 text-gray-300 truncate shrink-0" title={ERROR_NAMES_RU[name] ?? name}>
              {ERROR_NAMES_RU[name] ?? name}
            </div>
            <div className="flex-1 h-4 bg-gray-700 rounded overflow-hidden">
              <div
                className={`h-full rounded ${getColor(prob)} transition-all`}
                style={{ width: `${Math.max(prob * 100, 1)}%` }}
              />
            </div>
            <span className={`w-12 text-right shrink-0 ${isDetected ? 'text-red-400 font-bold' : 'text-gray-500'}`}>
              {(prob * 100).toFixed(0)}%
            </span>
            {isDetected && <span className="text-red-400 shrink-0">⚠</span>}
          </div>
        )
      })}
    </div>
  )
}