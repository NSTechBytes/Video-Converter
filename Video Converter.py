import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, 
                             QLabel, QFileDialog, QProgressBar, QComboBox, QMessageBox)
from PyQt5.QtGui import QIcon
from moviepy.editor import VideoFileClip
from PyQt5.QtCore import Qt, QThread, pyqtSignal

class VideoConverterThread(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, videos, output_format, quality, output_folder):
        super().__init__()
        self.videos = videos
        self.output_format = output_format
        self.quality = quality
        self.output_folder = output_folder
        self.total_frames = 0
        self.frames_processed = 0
        self.cancelled = False

    def count_total_frames(self):
        # Calculate total frames across all videos
        for video in self.videos:
            try:
                clip = VideoFileClip(video)
                self.total_frames += int(clip.fps * clip.duration)
            except Exception as e:
                print(f"Error getting total frames for {video}: {e}")
                continue

    def run(self):
        self.count_total_frames()

        for video in self.videos:
            if self.cancelled:
                break
            try:
                video_clip = VideoFileClip(video)
                output_file = os.path.join(self.output_folder, os.path.basename(video).replace(os.path.splitext(video)[1], f'.{self.output_format}'))

                def update_progress(get_frame, t):
                    if self.cancelled:
                        raise Exception("Conversion cancelled by user.")
                    self.frames_processed += 1
                    progress = int((self.frames_processed / self.total_frames) * 100)
                    self.progress_signal.emit(progress)
                    return get_frame(t)

                # Handle codec and preset logic based on quality
                if self.quality == "Original":
                    video_clip.fl(update_progress).write_videofile(output_file, codec='libx264')
                else:
                    if self.quality == "low":
                        preset = 'veryfast'
                    elif self.quality == "medium":
                        preset = 'medium'
                    elif self.quality == "high":
                        preset = 'slow'
                    else:
                        preset = 'medium'

                    video_clip.fl(update_progress).write_videofile(output_file, codec='libx264', preset=preset)

            except AttributeError as e:
                if "'NoneType' object has no attribute 'dtype'" in str(e):
                    self.error_signal.emit(f"Error converting {video}: Frame data missing or corrupted.")
                else:
                    self.error_signal.emit(f"Error converting {video}: {e}")
                continue
            except Exception as e:
                if str(e) == "Conversion cancelled by user.":
                    self.error_signal.emit("Conversion cancelled.")
                    break
                else:
                    self.error_signal.emit(f"Error converting {video}: {e}")
                continue

        if not self.cancelled:
            self.finished_signal.emit()

    def cancel(self):
        self.cancelled = True

class VideoConverterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Video Converter')
        self.setGeometry(300, 300, 400, 250)
        self.setFixedSize(420,400)

        # Set the window icon
        self.setWindowIcon(QIcon('icons/Video Converter.png'))

        self.layout = QVBoxLayout()

        self.label = QLabel('Select Videos to Convert')
        self.layout.addWidget(self.label)

        self.select_button = QPushButton('Select Videos')
        self.select_button.setIcon(QIcon('icons/add.png'))  # Set button icon
        self.select_button.clicked.connect(self.select_videos)
        self.layout.addWidget(self.select_button)

        self.format_label = QLabel('Select Output Format')
        self.layout.addWidget(self.format_label)

        self.format_combo = QComboBox()
        self.format_combo.addItems(['mp4', 'avi', 'mkv', 'mov'])
        self.layout.addWidget(self.format_combo)

        self.quality_label = QLabel('Select Quality')
        self.layout.addWidget(self.quality_label)

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['Original', 'low', 'medium', 'high'])
        self.layout.addWidget(self.quality_combo)

        self.output_folder_label = QLabel('Select Output Folder')
        self.layout.addWidget(self.output_folder_label)

        self.output_folder_button = QPushButton('Select Output Folder')
        self.output_folder_button.setIcon(QIcon('icons/folder.png'))  # Set button icon
        self.output_folder_button.clicked.connect(self.select_output_folder)
        self.layout.addWidget(self.output_folder_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar)

        self.convert_button = QPushButton('Convert')
        self.convert_button.setIcon(QIcon('icons/convert.png'))  # Set button icon
        self.convert_button.clicked.connect(self.start_conversion)
        self.layout.addWidget(self.convert_button)

        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.setIcon(QIcon('icons/cancel.png'))  # Set button icon
        self.cancel_button.clicked.connect(self.cancel_conversion)
        self.layout.addWidget(self.cancel_button)

        self.setLayout(self.layout)
        self.videos = []
        self.output_folder = ''

    def select_videos(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Videos", "", "Video Files (*.mp4 *.avi *.mkv *.mov)")
        if files:
            self.videos = files
            self.label.setText(f"Selected {len(files)} video(s)")

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder
            self.output_folder_label.setText(f"Output Folder: {folder}")

    def start_conversion(self):
        if not self.videos:
            self.label.setText("Please select videos first.")
            return
        if not self.output_folder:
            self.label.setText("Please select an output folder.")
            return

        output_format = self.format_combo.currentText()
        quality = self.quality_combo.currentText()

        self.converter_thread = VideoConverterThread(self.videos, output_format, quality, self.output_folder)
        self.converter_thread.progress_signal.connect(self.update_progress)
        self.converter_thread.finished_signal.connect(self.conversion_complete)
        self.converter_thread.error_signal.connect(self.show_error)
        self.converter_thread.start()

    def cancel_conversion(self):
        if hasattr(self, 'converter_thread') and self.converter_thread.isRunning():
            self.converter_thread.cancel()
            self.converter_thread.wait()  # Wait for the thread to terminate
            self.label.setText('Conversion Cancelled.')
            self.reset_gui()  # Clear the GUI after cancellation

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def conversion_complete(self):
        QMessageBox.information(self, 'Conversion Complete', 'All videos have been successfully converted!')
        self.reset_gui()

    def show_error(self, message):
        QMessageBox.critical(self, 'Error', message)

    def reset_gui(self):
        self.videos = []
        self.output_folder = ''
        self.progress_bar.setValue(0)
        self.label.setText('Select Videos to Convert')
        self.output_folder_label.setText('Select Output Folder')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoConverterApp()
    window.show()
    sys.exit(app.exec_())
