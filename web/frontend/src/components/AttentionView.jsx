import React, { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

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

const FEATURE_NAMES_RU = {
  right_wrist_speed:              'Скорость прав. запястья',
  left_wrist_speed:               'Скорость лев. запястья',
  right_elbow_speed:              'Скорость прав. локтя',
  left_elbow_speed:               'Скорость лев. локтя',
  right_wrist_accel:              'Ускорение прав. запястья',
  left_wrist_accel:               'Ускорение лев. запястья',
  right_elbow_angular_vel:        'Угл. скорость лок. (пр.)',
  right_shoulder_angular_vel:     'Угл. скорость плеча (пр.)',
  right_elbow_angle:              'Угол прав. локтя',
  left_elbow_angle:               'Угол лев. локтя',
  right_shoulder_angle:           'Угол прав. плеча',
  left_shoulder_angle:            'Угол лев. плеча',
  right_knee_angle:               'Угол прав. колена',
  left_knee_angle:                'Угол лев. колена',
  right_hip_angle:                'Угол прав. бедра',
  left_hip_angle:                 'Угол лев. бедра',
  shoulder_hip_rotation:          'Вращение плечи–бёдра',
  torso_forward_tilt:             'Наклон корпуса вперёд',
  torso_side_tilt:                'Боковой наклон корпуса',
  shoulder_height_diff:           'Разность высоты плеч',
  stance_width:                   'Ширина стойки',
  right_wrist_dist_body:          'Дистанция запястья от тела',
  right_elbow_height_vs_shoulder: 'Высота локтя от плеча',
  right_wrist_rel_x:              'Запястье X (лево-право)',
  right_wrist_rel_y:              'Запястье Y (высота)',
  right_wrist_rel_z:              'Запястье Z (глубина)',
  left_wrist_rel_x:               'Лев. запястье X',
  right_elbow_rel_x:              'Локоть X (лево-право)',
  right_elbow_rel_y:              'Локоть Y (высота)',
  right_wrist_dir_x:              'Направление запястья X',
  right_wrist_dir_y:              'Направление запястья Y',
  right_wrist_dir_z:              'Направление запястья Z',
  right_wrist_from_neutral:       'Откл. запястья от нейтр.',
  left_wrist_from_neutral:        'Откл. лев. запястья',
  elbow_angle_diff:               'Разница углов локтей',
  shoulder_angle_diff:            'Разница углов плеч',
  knee_angle_diff:                'Разница углов колен',
  wrist_distance:                 'Расстояние між запястьями',
  right_wrist_height_vs_shoulder: 'Высота прав. запястья',
  left_wrist_height_vs_shoulder:  'Высота лев. запястья',
}

function featureLabel(name) {
  return FEATURE_NAMES_RU[name] ?? name.replace(/_/g, ' ')
}

function TemporalChart({ values, startFrame, title, color }) {
  if (!values?.length) return null
  const data = values.map((v, i) => ({ frame: startFrame + i, weight: v }))
  return (
    <div className="bg-gray-800 rounded-lg p-3">
      <h4 className="text-sm text-gray-300 mb-2 font-medium">{title}</h4>
      <ResponsiveContainer width="100%" height={110}>
        <BarChart data={data} margin={{ top: 2, right: 4, bottom: 0, left: 0 }}>
          <XAxis dataKey="frame" tick={{ fontSize: 11, fill: '#9ca3af' }} />
          <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} width={36} />
          <Tooltip
            contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 12 }}
            formatter={v => v.toFixed(4)}
            labelFormatter={f => `кадр ${f}`}
          />
          <Bar dataKey="weight" fill={color} radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function FeatureImportanceChart({ importance, selectedFeature, onFeatureClick, title, color }) {
  const data = Object.entries(importance)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([name, value]) => ({ name: featureLabel(name), rawName: name, value: value * 100 }))
  if (!data.length) return null
  return (
    <div className="bg-gray-800 rounded-lg p-3">
      <h4 className="text-sm text-gray-300 mb-2 font-medium">
        {title}
        {onFeatureClick && <span className="text-gray-500 font-normal ml-1 text-xs">— кликни для показа на графике</span>}
      </h4>
      <ResponsiveContainer width="100%" height={Math.min(data.length * 32 + 10, 340)}>
        <BarChart data={data} layout="vertical" margin={{ top: 2, right: 12, bottom: 0, left: 0 }}>
          <XAxis type="number" tick={{ fontSize: 11, fill: '#9ca3af' }} />
          <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#c4c9d4' }} width={175} />
          <Tooltip
            contentStyle={{ background: '#1f2937', border: '1px solid #374151', fontSize: 12 }}
            formatter={v => `${v.toFixed(2)}%`}
          />
          <Bar dataKey="value" cursor={onFeatureClick ? 'pointer' : 'default'} onClick={d => onFeatureClick?.(d.rawName)} radius={[0, 3, 3, 0]}>
            {data.map((entry, idx) => (
              <Cell key={idx} fill={entry.rawName === selectedFeature ? '#5aaa7a' : color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {selectedFeature && (
        <div className="text-xs text-emerald-400 mt-1.5">
          Выбрано: <span className="font-mono">{featureLabel(selectedFeature)}</span>
        </div>
      )}
    </div>
  )
}

export default function AttentionView({ attention, selectedFeature, onFeatureClick }) {
  const [activeError, setActiveError] = useState(null)
  if (!attention) return null

  const detectedErrors = Object.keys(attention.error_feature_importance || {})
  const currentError = activeError && detectedErrors.includes(activeError)
    ? activeError
    : detectedErrors[0] ?? null

  return (
    <div className="space-y-3">

      {/* Временное внимание классификатора */}
      <TemporalChart
        values={attention.temporal_attention}
        startFrame={attention.start_frame}
        title="Важные кадры (классификатор типа удара)"
        color="#7c6fcd"
      />

      {/* Временное внимание детектора ошибок */}
      <TemporalChart
        values={attention.error_temporal_attention}
        startFrame={attention.start_frame}
        title="Важные кадры (детектор ошибок)"
        color="#c46e6e"
      />

      {/* Важность признаков для классификатора */}
      {attention.feature_importance && (
        <FeatureImportanceChart
          importance={attention.feature_importance}
          selectedFeature={selectedFeature}
          onFeatureClick={onFeatureClick}
          title="Важность параметров для классификации типа удара (top-10)"
          color="#9e7db5"
        />
      )}

      {/* Важность признаков по конкретным ошибкам */}
      {detectedErrors.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-3 space-y-2">
          <h4 className="text-xs text-gray-400">Что повлияло на определение каждой ошибки</h4>

          {/* Таби ошибок */}
          {detectedErrors.length > 1 && (
            <div className="flex flex-wrap gap-1">
              {detectedErrors.map(err => (
                <button
                  key={err}
                  onClick={() => setActiveError(err)}
                  className={`text-xs px-2 py-0.5 rounded transition-colors ${
                    err === currentError
                      ? 'bg-red-700 text-white'
                      : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                  }`}
                >
                  {ERROR_NAMES_RU[err] ?? err}
                </button>
              ))}
            </div>
          )}

          {/* График для выбранной ошибки */}
          {currentError && attention.error_feature_importance[currentError] && (
            <div>
              {detectedErrors.length === 1 && (
                <div className="text-xs text-red-400 mb-1 font-medium">
                  {ERROR_NAMES_RU[currentError] ?? currentError}
                </div>
              )}
              <FeatureImportanceChart
                importance={attention.error_feature_importance[currentError]}
                selectedFeature={selectedFeature}
                onFeatureClick={onFeatureClick}
                title="Параметры, важные для этой ошибки (top-10)"
                color="#c46e6e"
              />
            </div>
          )}
        </div>
      )}

    </div>
  )
}
