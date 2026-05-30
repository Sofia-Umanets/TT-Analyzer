"""
Запуск: python annotator.py video.mp4
"""

import cv2
import json
import numpy as np
from pathlib import Path
from datetime import datetime


class VideoAnnotator:
    
    STROKE_TYPES = {
        '1': ('topspin_forehand', 'Topspin FH'),      # Топспин справа
        '2': ('drive_forehand', 'Drive FH'),          # Накат справа
        '3': ('slice_forehand', 'Slice FH'),          # Срезка справа
        '4': ('topspin_backhand', 'Topspin BH'),      # Топспин слева
        '5': ('drive_backhand', 'Drive BH'),          # Накат слева
        '6': ('slice_backhand', 'Slice BH'),          # Срезка слева
        '7': ('other', 'Other'),                       # Другое
    }
    
    ERRORS = {
        # Верхний ряд клавиатуры - основные ошибки
        'q': ('straight_legs', 'Straight legs'),           # Прямые ноги
        'w': ('big_swing', 'Big swing'),                   # Большой замах
        'e': ('straight_arm', 'Straight arm end'),         # Прямая рука в конце
        'r': ('straight_body', 'Straight body'),           # Прямой корпус
        't': ('raised_shoulder', 'Raised shoulder'),       # Поднято плечо
        'y': ('raised_elbow', 'Raised elbow'),             # Поднят локоть
        'u': ('wrist_up', 'Wrist up end'),                 # Кисть вверх в конце
        'i': ('low_backswing', 'Low backswing'),           # Замах снизу
        'o': ('no_forearm', 'No forearm work'),            # Нет работы предплечья
        'p': ('sideways_finish', 'Sideways finish'),       # Концовка вбок
        # Средний ряд - дополнительные
        'a': ('wrist_bent_fwd', 'Wrist bent forward'),     # Кисть согнута
        's': ('wrist_bent_back', 'Wrist bent back'),       # Кисть выгнута
        'd': ('arm_far', 'Arm far from body'),             # Рука далеко
        'f': ('straight_line', 'Straight line motion'),    # Движение по прямой()
        'g': ('low_elbow_end', 'Low elbow end'),           # Локоть низко в конце
        'z': ('left_hand_up', 'Left hand raised'),         # опущена левая рука (за корпусом)
        'm': ('no_rotation', 'No body rotation'),          # Движение по прямой (накат)
        'c': ('incomplete_follow_through', 'Incomplete follow-through'),     # Движение не доведено
        'v': ('left_hand_behind_body', 'Left hand behind body'),     # Поднята левая рука
        'b': ('vertical_swing', 'Swing up instead forward'),  # движение снизу вверх (не та амплитуда)
    }
    
    
    def __init__(self, video_path):
        self.video_path = Path(video_path)
        
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        self.cap = cv2.VideoCapture(str(video_path))
        if not self.cap.isOpened():
            raise ValueError("Cannot open video")
        
        # Параметры видео
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.orig_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.orig_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.duration = self.total_frames / self.fps
        
        # Размеры отображения
        self.panel_w = 380
        max_video_h = 700
        self.scale = min(1.0, max_video_h / self.orig_h)
        self.video_w = int(self.orig_w * self.scale)
        self.video_h = int(self.orig_h * self.scale)
        
        # Состояние
        self.frame_idx = 0
        self.playing = False
        self.annotations = []
        
        # Текущая разметка
        self.current = None
        self.step = 0  # 0=нет, 1=начало, 2=контакт, 3=конец, 4=тип, 5=ошибки, 6=качество
        
        # Сообщение
        self.msg = ""
        self.msg_frames = 0
        
        # Файл сохранения
        self.save_dir = Path("data/annotations")
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.save_path = self.save_dir / f"{self.video_path.stem}.json"
        
        self._load()
        self._print_help()
    
    def _load(self):
        """Загрузка существующих аннотаций."""
        if self.save_path.exists():
            try:
                with open(self.save_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.annotations = data.get('strokes', [])
                print(f"Loaded {len(self.annotations)} annotations")
            except:
                self.annotations = []
    
    def _save(self):
        """Сохранение аннотаций."""
        data = {
            'video': self.video_path.name,
            'fps': self.fps,
            'frames': self.total_frames,
            'duration': round(self.duration, 2),
            'strokes': self.annotations
        }
        with open(self.save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(self.annotations)} annotations")
    
    def _print_help(self):
        """Справка в консоль."""
        print("\n" + "="*50)
        print("VIDEO ANNOTATOR v3.0")
        print("="*50)
        print(f"Video: {self.video_path.name}")
        print(f"Duration: {self.duration:.1f}s, {self.total_frames} frames")
        print("-"*50)
        print("CONTROLS:")
        print("  SPACE     - play/pause")
        print("  LEFT/RIGHT- +/-1 frame")
        print("  UP/DOWN   - +/-10 frames")
        print("  ,/.       - +/-1 frame")
        print("  </> or ;/'- +/-30 frames")
        print("  [/]       - +/-1 second")
        print("-"*50)
        print("  ENTER     - start/next step")
        print("  BACKSPACE - cancel current")
        print("  X         - delete last saved")
        print("  ESC       - exit")
        print("="*50 + "\n")
    
    def _show_msg(self, text):
        """Показать сообщение."""
        self.msg = text
        self.msg_frames = 60  # ~2 секунды
        print(f">> {text}")
    
    def run(self):
        """Главный цикл."""
        cv2.namedWindow('Annotator', cv2.WINDOW_AUTOSIZE)
        
        while True:
            # Читаем кадр
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.frame_idx)
            ret, frame = self.cap.read()
            if not ret:
                self.frame_idx = max(0, self.frame_idx - 1)
                continue
            
            # Масштабируем
            if self.scale != 1.0:
                frame = cv2.resize(frame, (self.video_w, self.video_h))
            
            # Создаём дисплей
            display = self._make_display(frame)
            cv2.imshow('Annotator', display)
            
            # Клавиши
            wait = 1 if self.playing else 50
            key = cv2.waitKey(wait) & 0xFF
            
            if key != 255:
                if self._handle_key(key) == 'quit':
                    break
            
            # Воспроизведение
            if self.playing and self.step == 0:
                self.frame_idx = min(self.total_frames - 1, self.frame_idx + 1)
                if self.frame_idx >= self.total_frames - 1:
                    self.playing = False
            
            # Уменьшаем счётчик сообщения
            if self.msg_frames > 0:
                self.msg_frames -= 1
                if self.msg_frames == 0:
                    self.msg = ""
        
        self._save()
        self.cap.release()
        cv2.destroyAllWindows()
    
    def _handle_key(self, key):
        """Обработка клавиш."""
        # ESC - выход
        if key == 27:
            return 'quit'
        
        # SPACE - воспроизведение/пауза
        if key == 32:  # пробел
            if self.step == 0:
                self.playing = not self.playing
                self._show_msg("PLAY" if self.playing else "PAUSE")
            return
        
        # Навигация
        step = 0
        if key == 81 or key == ord(','):  # влево или ,
            step = -1
        elif key == 83 or key == ord('.'):  # вправо или .
            step = 1
        elif key == 82:  # вверх
            step = -10
        elif key == 84:  # вниз
            step = 10
        elif key == ord('['):
            step = -int(self.fps)
        elif key == ord(']'):
            step = int(self.fps)
        elif key == ord('<') or key == ord(';'):
            step = -30
        elif key == ord('>') or key == ord("'"):
            step = 30
        elif key == ord('{'):
            step = -int(self.fps * 5)
        elif key == ord('}'):
            step = int(self.fps * 5)
        
        if step != 0:
            self.frame_idx = max(0, min(self.total_frames - 1, self.frame_idx + step))
            self.playing = False
            return
        
        # ENTER - разметка
        if key == 13:
            self._next_step()
            return
        
        # BACKSPACE - отмена
        if key == 8 or key == 127:
            if self.step > 0:
                self.current = None
                self.step = 0
                self._show_msg("Cancelled")
            return
        
        # X - удалить последнюю
        if key == ord('x') or key == ord('X'):
            if self.annotations and self.step == 0:
                removed = self.annotations.pop()
                self._show_msg(f"Deleted #{removed['id']}")
            return
        
        # Ввод в зависимости от шага
        char = chr(key).lower() if 32 <= key < 127 else ''
        
        if self.step == 4:  # Выбор типа
            if char in self.STROKE_TYPES:
                self._set_type(char)
        
        elif self.step == 5:  # Ошибки
            if char in self.ERRORS:
                self._toggle_error(char)
        
        elif self.step == 6:  # Качество
            if char in '1234567890':
                q = 10 if char == '0' else int(char)
                self._set_quality(q)
    
    def _next_step(self):
        """Следующий шаг разметки."""
        if self.step == 0:
            # Начинаем новую разметку
            self.current = {'errors': []}
            self.step = 1
            self.playing = False
            self._show_msg("Step 1: Mark START")
        
        elif self.step == 1:
            self.current['start'] = self.frame_idx
            self.step = 2
            self._show_msg("Step 2: Mark CONTACT")
        
        elif self.step == 2:
            self.current['contact'] = self.frame_idx
            self.step = 3
            self._show_msg("Step 3: Mark END")
        
        elif self.step == 3:
            self.current['end'] = self.frame_idx
            self.step = 4
            self._show_msg("Step 4: Select TYPE (1-7)")
        
        elif self.step == 4:
            if 'type' in self.current:
                self.step = 5
                self._show_msg("Step 5: Mark ERRORS (q-x) or Enter")
            else:
                self._show_msg("Select type first! (1-7)")
        
        elif self.step == 5:
            self.step = 6
            self._show_msg("Step 6: Rate QUALITY (1-10)")
        
        elif self.step == 6:
            if 'quality' not in self.current:
                self.current['quality'] = 5
            self._save_current()
    
    def _set_type(self, char):
        """Установка типа удара."""
        type_id, type_name = self.STROKE_TYPES[char]
        self.current['type'] = type_id
        self.current['type_name'] = type_name
        self._show_msg(f"Type: {type_name}")
        self.step = 5  # Переход к ошибкам
    
    def _toggle_error(self, char):
        """Переключение ошибки."""
        err_id, err_name = self.ERRORS[char]
        if char in self.current['errors']:
            self.current['errors'].remove(char)
            self._show_msg(f"Removed: {err_name}")
        else:
            self.current['errors'].append(char)
            self._show_msg(f"Added: {err_name}")
    
    def _set_quality(self, q):
        """Установка качества и сохранение."""
        self.current['quality'] = q
        self._show_msg(f"Quality: {q}/10")
        self._save_current()
    
    def _save_current(self):
        """Сохранение текущей разметки."""
        if not self.current or 'type' not in self.current:
            return
        
        ann = {
            'id': len(self.annotations) + 1,
            'start_frame': self.current.get('start', 0),
            'contact_frame': self.current.get('contact'),
            'end_frame': self.current.get('end', self.frame_idx),
            'start_time': round(self.current.get('start', 0) / self.fps, 3),
            'end_time': round(self.current.get('end', self.frame_idx) / self.fps, 3),
            'type': self.current['type'],
            'quality': self.current.get('quality', 5),
            'errors': [self.ERRORS[e][0] for e in self.current.get('errors', [])]
        }
        
        self.annotations.append(ann)
        self._show_msg(f"Saved #{ann['id']}: {self.current.get('type_name', '')}")
        
        self.current = None
        self.step = 0
        
        # Автосохранение
        if len(self.annotations) % 5 == 0:
            self._save()
    
    def _make_display(self, frame):
        """Создание полного изображения."""
        h = self.video_h
        w = self.video_w + self.panel_w
        
        # Создаём холст
        display = np.zeros((h, w, 3), dtype=np.uint8)
        display[:, :, :] = (40, 40, 40)  # Тёмно-серый фон
        
        # Видео слева
        display[:self.video_h, :self.video_w] = frame
        
        # Рамка если разметка активна
        if self.step > 0:
            cv2.rectangle(display, (2, 2), (self.video_w - 3, self.video_h - 3), 
                         (0, 255, 0), 3)
        
        # Панель справа
        self._draw_panel(display)
        
        # Таймлайн
        self._draw_timeline(display)
        
        # Сообщение
        if self.msg:
            self._draw_message(display)
        
        return display
    
    def _draw_panel(self, display):
        """Рисование боковой панели."""
        x0 = self.video_w + 15
        y = 20
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        white = (255, 255, 255)
        gray = (180, 180, 180)
        green = (100, 255, 100)
        yellow = (100, 255, 255)
        cyan = (255, 255, 100)
        orange = (100, 180, 255)
        
        # === СТАТУС ===
        status = "PLAYING" if self.playing else "PAUSED"
        color = green if self.playing else yellow
        cv2.putText(display, status, (x0, y), font, 0.8, color, 2)
        y += 35
        
        # Время
        t = self.frame_idx / self.fps
        cv2.putText(display, f"Time: {t:.2f}s / {self.duration:.1f}s", 
                   (x0, y), font, 0.5, gray, 1)
        y += 22
        cv2.putText(display, f"Frame: {self.frame_idx} / {self.total_frames}", 
                   (x0, y), font, 0.5, gray, 1)
        y += 22
        cv2.putText(display, f"Saved: {len(self.annotations)}", 
                   (x0, y), font, 0.5, green, 1)
        y += 35
        
        # Линия
        cv2.line(display, (x0, y), (x0 + self.panel_w - 30, y), (80, 80, 80), 1)
        y += 20
        
        # === ТЕКУЩИЙ ШАГ ===
        if self.step == 0:
            cv2.putText(display, "Press ENTER to start", (x0, y), font, 0.55, gray, 1)
            y += 25
            cv2.putText(display, "marking a new stroke", (x0, y), font, 0.55, gray, 1)
            y += 40
            
            # Навигация
            cv2.putText(display, "NAVIGATION:", (x0, y), font, 0.55, orange, 1)
            y += 25
            hints = [
                "SPACE - play/pause",
                "< > - +/-1 frame", 
                "^ v - +/-10 frames",
                "; ' - +/-30 frames",
                "[ ] - +/-1 second",
            ]
            for h in hints:
                cv2.putText(display, h, (x0, y), font, 0.45, gray, 1)
                y += 18
        
        else:
            # Название шага
            step_names = {
                1: ("STEP 1: START", "Find stroke START", green),
                2: ("STEP 2: CONTACT", "Find ball CONTACT", cyan),
                3: ("STEP 3: END", "Find stroke END", yellow),
                4: ("STEP 4: TYPE", "Press 1-7:", orange),
                5: ("STEP 5: ERRORS", "Press q-x or ENTER:", orange),
                6: ("STEP 6: QUALITY", "Press 1-9 or 0(=10):", orange),
            }
            
            name, hint, col = step_names.get(self.step, ("", "", white))
            cv2.putText(display, name, (x0, y), font, 0.65, col, 2)
            y += 28
            cv2.putText(display, hint, (x0, y), font, 0.5, gray, 1)
            y += 25
            
            # Варианты для шага
            if self.step == 4:
                # Типы ударов
                for key, (_, name) in self.STROKE_TYPES.items():
                    selected = self.current and self.current.get('type') == self.STROKE_TYPES[key][0]
                    c = green if selected else gray
                    cv2.putText(display, f"{key} - {name}", (x0, y), font, 0.45, c, 1)
                    y += 18
            
            elif self.step == 5:
                # Ошибки (в две колонки)
                errors_list = list(self.ERRORS.items())
                col1 = errors_list[:9]
                col2 = errors_list[9:]
                
                y_start = y
                for key, (_, name) in col1:
                    selected = self.current and key in self.current.get('errors', [])
                    mark = "[X]" if selected else "[ ]"
                    c = green if selected else gray
                    short = name[:15]
                    cv2.putText(display, f"{mark} {key}-{short}", (x0, y), font, 0.38, c, 1)
                    y += 16
                
                y = y_start
                x2 = x0 + 175
                for key, (_, name) in col2:
                    selected = self.current and key in self.current.get('errors', [])
                    mark = "[X]" if selected else "[ ]"
                    c = green if selected else gray
                    short = name[:15]
                    cv2.putText(display, f"{mark} {key}-{short}", (x2, y), font, 0.38, c, 1)
                    y += 16
                
                y = y_start + max(len(col1), len(col2)) * 16 + 10
            
            elif self.step == 6:
                cv2.putText(display, "1-3: bad", (x0, y), font, 0.45, gray, 1)
                y += 18
                cv2.putText(display, "4-6: average", (x0, y), font, 0.45, gray, 1)
                y += 18
                cv2.putText(display, "7-9: good", (x0, y), font, 0.45, gray, 1)
                y += 18
                cv2.putText(display, "0: excellent (10)", (x0, y), font, 0.45, gray, 1)
                y += 25
            
            y += 15
            
            # Текущие данные
            if self.current:
                cv2.line(display, (x0, y), (x0 + self.panel_w - 30, y), (80, 80, 80), 1)
                y += 15
                cv2.putText(display, "CURRENT:", (x0, y), font, 0.5, orange, 1)
                y += 22
                
                if 'start' in self.current:
                    cv2.putText(display, f"Start: {self.current['start']}", 
                               (x0, y), font, 0.45, green, 1)
                    y += 18
                
                if 'contact' in self.current:
                    cv2.putText(display, f"Contact: {self.current['contact']}", 
                               (x0, y), font, 0.45, cyan, 1)
                    y += 18
                
                if 'end' in self.current:
                    cv2.putText(display, f"End: {self.current['end']}", 
                               (x0, y), font, 0.45, yellow, 1)
                    y += 18
                
                if 'type_name' in self.current:
                    cv2.putText(display, f"Type: {self.current['type_name']}", 
                               (x0, y), font, 0.45, orange, 1)
                    y += 18
                
                if self.current.get('errors'):
                    cv2.putText(display, f"Errors: {len(self.current['errors'])}", 
                               (x0, y), font, 0.45, (100, 150, 255), 1)
                    y += 18
    
    def _draw_timeline(self, display):
        """Рисование таймлайна."""
        tl_h = 10
        tl_y = self.video_h - tl_h - 10
        tl_x = 10
        tl_w = self.video_w - 20
        
        # Фон
        cv2.rectangle(display, (tl_x, tl_y), (tl_x + tl_w, tl_y + tl_h), 
                     (60, 60, 60), -1)
        
        # Сохранённые разметки
        for ann in self.annotations:
            x1 = tl_x + int((ann['start_frame'] / self.total_frames) * tl_w)
            x2 = tl_x + int((ann['end_frame'] / self.total_frames) * tl_w)
            color = (0, 180, 0) if not ann.get('errors') else (0, 140, 255)
            cv2.rectangle(display, (x1, tl_y + 1), (max(x2, x1 + 3), tl_y + tl_h - 1), 
                         color, -1)
        
        # Текущая разметка
        if self.current:
            if 'start' in self.current:
                x = tl_x + int((self.current['start'] / self.total_frames) * tl_w)
                cv2.line(display, (x, tl_y - 5), (x, tl_y + tl_h + 5), (0, 255, 0), 2)
            if 'contact' in self.current:
                x = tl_x + int((self.current['contact'] / self.total_frames) * tl_w)
                cv2.line(display, (x, tl_y - 5), (x, tl_y + tl_h + 5), (255, 255, 0), 2)
            if 'end' in self.current:
                x = tl_x + int((self.current['end'] / self.total_frames) * tl_w)
                cv2.line(display, (x, tl_y - 5), (x, tl_y + tl_h + 5), (0, 255, 255), 2)
        
        # Текущая позиция
        cx = tl_x + int((self.frame_idx / self.total_frames) * tl_w)
        cv2.circle(display, (cx, tl_y + tl_h // 2), 6, (0, 0, 200), -1)
        cv2.circle(display, (cx, tl_y + tl_h // 2), 6, (255, 255, 255), 2)
    
    def _draw_message(self, display):
        """Рисование сообщения."""
        if not self.msg:
            return
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), _ = cv2.getTextSize(self.msg, font, 0.7, 2)
        
        mx = 20
        my = 50
        
        # Фон
        cv2.rectangle(display, (mx - 10, my - 25), (mx + tw + 10, my + 10), 
                     (0, 0, 0), -1)
        cv2.rectangle(display, (mx - 10, my - 25), (mx + tw + 10, my + 10), 
                     (100, 255, 255), 2)
        
        # Текст
        cv2.putText(display, self.msg, (mx, my), font, 0.7, (100, 255, 255), 2)


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python annotator.py <video_path>")
        print("Example: python annotator.py video.mp4")
        sys.exit(1)
    
    try:
        app = VideoAnnotator(sys.argv[1])
        app.run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()