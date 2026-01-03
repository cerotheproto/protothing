import numpy as np
import sounddevice as sd
import threading
import logging
from collections import deque

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Обработчик аудио с FFT для определения визем (форм рта)"""
    
    def __init__(self, sample_rate=16000, chunk_size=512, smoothing_frames=3):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.smoothing_frames = smoothing_frames
        
        # История состояний для сглаживания
        self.state_history = deque(maxlen=smoothing_frames)
        
        # Состояние
        self.current_state = "default"
        self.current_energy = 0.0
        
        # Временные данные
        self.state_duration = 0.0
        self.min_state_duration = 0.05  # минимум 50ms в каждом состоянии
        
        # Поток для захвата аудио
        self.audio_buffer = deque(maxlen=chunk_size)
        self.stream = None
        self.is_running = False
        self._lock = threading.Lock()
    
    def start(self):
        """Запускает захват аудио в фоновом потоке"""
        if self.is_running:
            return
        
        self.is_running = True
        try:
            self.stream = sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                callback=self._audio_callback,
                latency='low'
            )
            self.stream.start()
            logger.info("Audio processor started")
        except Exception as e:
            self.is_running = False
            logger.error(f"Error starting audio capture: {e}")
            raise
    
    def stop(self):
        """Останавливает захват аудио"""
        self.is_running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback для захвата аудиоданных"""
        if status:
            logger.warning(f"Audio stream warning: {status}")
        
        # Добавляем аудиоданные в буфер
        with self._lock:
            for sample in indata[:, 0]:
                self.audio_buffer.append(sample)
    
    def _calculate_rms(self, audio_chunk):
        """Вычисляет RMS (громкость) аудио"""
        return np.sqrt(np.mean(audio_chunk ** 2))
    
    def _analyze_with_fft(self, audio_chunk):
        """Анализирует аудио с помощью FFT для определения виземы"""
        if len(audio_chunk) < 2:
            return "default", 0.0
        
        # Применяем окно Hann для уменьшения утечки спектра
        windowed = audio_chunk * np.hanning(len(audio_chunk))
        
        # FFT
        fft = np.abs(np.fft.fft(windowed))
        freqs = np.fft.fftfreq(len(windowed), 1 / self.sample_rate)
        
        # Берём только положительные частоты
        positive_freqs = freqs[:len(freqs) // 2]
        positive_fft = fft[:len(fft) // 2]
        
        # Нормализуем
        if np.max(positive_fft) > 0:
            positive_fft = positive_fft / np.max(positive_fft)
        
        # Анализируем энергию в разных диапазонах частот
        # Низкие (100-400 Hz) - Основной тон, низкая форманта F1 (У, О)
        low_mask = (positive_freqs >= 100) & (positive_freqs < 400)
        low_energy = np.mean(positive_fft[low_mask]) if np.any(low_mask) else 0.0
        
        # Средние (400-1000 Hz) - Высокая F1 (А)
        mid_mask = (positive_freqs >= 400) & (positive_freqs < 1000)
        mid_energy = np.mean(positive_fft[mid_mask]) if np.any(mid_mask) else 0.0
        
        # Высокие (1000-3000 Hz) - F2 для передних гласных (И, Э)
        high_mask = (positive_freqs >= 1000) & (positive_freqs < 3000)
        high_energy = np.mean(positive_fft[high_mask]) if np.any(high_mask) else 0.0
        
        # RMS для определения молчания
        rms = self._calculate_rms(audio_chunk)
        
        # Если слишком тихо - молчание
        if rms < 0.01:
            return "default", rms
        
        # Нормализуем энергии относительно друг друга
        total_energy = low_energy + mid_energy + high_energy
        if total_energy > 0:
            low_ratio = low_energy / total_energy
            mid_ratio = mid_energy / total_energy
            high_ratio = high_energy / total_energy
        else:
            return "default", rms

        # Определяем визему по соотношению энергий
        # А: доминируют средние частоты (открытый рот)
        if mid_ratio > 0.4:
            return "viseme_a", rms
            
        # И/Э: значительная энергия в высоких частотах
        if high_ratio > 0.3:
            return "viseme_e", rms
            
        # О/У: в основном низкие частоты
        return "viseme_o", rms
    
    def update(self, dt):
        """Обновляет состояние на основе текущего аудиобуфера"""
        with self._lock:
            if len(self.audio_buffer) < self.chunk_size:
                return self.current_state
            
            # Копируем буфер для анализа
            audio_chunk = np.array(list(self.audio_buffer), dtype=np.float32)
        
        # Анализируем аудио
        new_state, energy = self._analyze_with_fft(audio_chunk)
        self.current_energy = energy
        
        # Применяем минимальную длительность состояния
        self.state_duration += dt
        
        if self.state_duration >= self.min_state_duration:
            # Добавляем новое состояние в историю
            self.state_history.append(new_state)
            
            # Берём наиболее частое состояние из истории (сглаживание)
            if self.state_history:
                smoothed_state = max(set(self.state_history), key=self.state_history.count)
                
                # Обновляем состояние только если оно изменилось
                if smoothed_state != self.current_state:
                    self.current_state = smoothed_state
                    self.state_duration = 0.0
        
        return self.current_state
    
    def get_state(self):
        """Возвращает текущее состояние рта"""
        return self.current_state
    
    def get_energy(self):
        """Возвращает текущую энергию аудио"""
        return self.current_energy
