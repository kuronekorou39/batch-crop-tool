#!/usr/bin/env python3
import sys
import os
from pathlib import Path
from typing import List, Optional, Tuple
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QListWidget, QLabel, QScrollArea,
    QSplitter, QMessageBox, QSpinBox, QGroupBox, QListWidgetItem,
    QCheckBox, QProgressDialog
)
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QSize, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QImage, QBrush, QCursor


class ImageViewer(QLabel):
    cropChanged = Signal(QRect)
    
    def __init__(self):
        super().__init__()
        self.setScaledContents(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("QLabel { background-color: #f0f0f0; border: 1px solid #ccc; }")
        self.setMouseTracking(True)
        
        self.original_pixmap = None
        self.display_pixmap = None
        self.scale_factor = 1.0
        self.crop_rect = QRect()
        self.is_selecting = False
        self.selection_start = QPoint()
        
        # リサイズ用の変数
        self.drag_mode = None  # None, 'move', 'resize_tl', 'resize_tr', 'resize_bl', 'resize_br', 'resize_t', 'resize_b', 'resize_l', 'resize_r'
        self.drag_start_pos = QPoint()
        self.drag_start_rect = QRect()
        self.handle_size = 8
        
    def set_image(self, image_path: str):
        self.original_pixmap = QPixmap(image_path)
        if self.original_pixmap.isNull():
            return False
        
        self.fit_to_window()
        return True
    
    def fit_to_window(self):
        if not self.original_pixmap:
            return
        
        widget_size = self.size()
        pixmap_size = self.original_pixmap.size()
        
        scale_w = widget_size.width() / pixmap_size.width()
        scale_h = widget_size.height() / pixmap_size.height()
        self.scale_factor = min(scale_w, scale_h, 1.0) * 0.95
        
        scaled_size = pixmap_size * self.scale_factor
        self.display_pixmap = self.original_pixmap.scaled(
            scaled_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.update_display()
    
    def update_display(self):
        if not self.display_pixmap:
            return
        
        temp_pixmap = QPixmap(self.display_pixmap)
        painter = QPainter(temp_pixmap)
        
        if not self.crop_rect.isEmpty():
            scaled_rect = QRect(
                int(self.crop_rect.x() * self.scale_factor),
                int(self.crop_rect.y() * self.scale_factor),
                int(self.crop_rect.width() * self.scale_factor),
                int(self.crop_rect.height() * self.scale_factor)
            )
            
            painter.fillRect(temp_pixmap.rect(), QBrush(QColor(0, 0, 0, 100)))
            
            if scaled_rect.isValid():
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                painter.drawPixmap(scaled_rect, self.display_pixmap, scaled_rect)
            
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.drawRect(scaled_rect)
            
            # ハンドル（調整用の四角）を描画
            painter.fillRect(scaled_rect.x() - self.handle_size//2, scaled_rect.y() - self.handle_size//2, 
                           self.handle_size, self.handle_size, QColor(255, 0, 0))
            painter.fillRect(scaled_rect.right() - self.handle_size//2, scaled_rect.y() - self.handle_size//2, 
                           self.handle_size, self.handle_size, QColor(255, 0, 0))
            painter.fillRect(scaled_rect.x() - self.handle_size//2, scaled_rect.bottom() - self.handle_size//2, 
                           self.handle_size, self.handle_size, QColor(255, 0, 0))
            painter.fillRect(scaled_rect.right() - self.handle_size//2, scaled_rect.bottom() - self.handle_size//2, 
                           self.handle_size, self.handle_size, QColor(255, 0, 0))
            
            # 辺の中央のハンドル
            painter.fillRect(scaled_rect.center().x() - self.handle_size//2, scaled_rect.y() - self.handle_size//2, 
                           self.handle_size, self.handle_size, QColor(255, 0, 0))
            painter.fillRect(scaled_rect.center().x() - self.handle_size//2, scaled_rect.bottom() - self.handle_size//2, 
                           self.handle_size, self.handle_size, QColor(255, 0, 0))
            painter.fillRect(scaled_rect.x() - self.handle_size//2, scaled_rect.center().y() - self.handle_size//2, 
                           self.handle_size, self.handle_size, QColor(255, 0, 0))
            painter.fillRect(scaled_rect.right() - self.handle_size//2, scaled_rect.center().y() - self.handle_size//2, 
                           self.handle_size, self.handle_size, QColor(255, 0, 0))
        
        painter.end()
        self.setPixmap(temp_pixmap)
    
    def get_handle_at_pos(self, pos):
        """マウス位置にあるハンドルを判定"""
        if self.crop_rect.isEmpty():
            return None
            
        scaled_rect = QRect(
            int(self.crop_rect.x() * self.scale_factor),
            int(self.crop_rect.y() * self.scale_factor),
            int(self.crop_rect.width() * self.scale_factor),
            int(self.crop_rect.height() * self.scale_factor)
        )
        
        tolerance = self.handle_size + 2
        
        # 角のハンドル
        if abs(pos.x() - scaled_rect.x()) < tolerance and abs(pos.y() - scaled_rect.y()) < tolerance:
            return 'resize_tl'
        if abs(pos.x() - scaled_rect.right()) < tolerance and abs(pos.y() - scaled_rect.y()) < tolerance:
            return 'resize_tr'
        if abs(pos.x() - scaled_rect.x()) < tolerance and abs(pos.y() - scaled_rect.bottom()) < tolerance:
            return 'resize_bl'
        if abs(pos.x() - scaled_rect.right()) < tolerance and abs(pos.y() - scaled_rect.bottom()) < tolerance:
            return 'resize_br'
        
        # 辺のハンドル
        if abs(pos.x() - scaled_rect.center().x()) < tolerance and abs(pos.y() - scaled_rect.y()) < tolerance:
            return 'resize_t'
        if abs(pos.x() - scaled_rect.center().x()) < tolerance and abs(pos.y() - scaled_rect.bottom()) < tolerance:
            return 'resize_b'
        if abs(pos.x() - scaled_rect.x()) < tolerance and abs(pos.y() - scaled_rect.center().y()) < tolerance:
            return 'resize_l'
        if abs(pos.x() - scaled_rect.right()) < tolerance and abs(pos.y() - scaled_rect.center().y()) < tolerance:
            return 'resize_r'
        
        # 矩形内部（移動）
        if scaled_rect.contains(pos):
            return 'move'
        
        return None
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.display_pixmap:
            pixmap_rect = self.pixmap().rect()
            label_rect = self.rect()
            x_offset = (label_rect.width() - pixmap_rect.width()) // 2
            y_offset = (label_rect.height() - pixmap_rect.height()) // 2
            
            click_pos = event.position().toPoint() - QPoint(x_offset, y_offset)
            
            if pixmap_rect.contains(click_pos):
                handle = self.get_handle_at_pos(click_pos)
                
                if handle:
                    self.drag_mode = handle
                    self.drag_start_pos = click_pos
                    self.drag_start_rect = QRect(self.crop_rect)
                else:
                    # 新規選択開始
                    self.is_selecting = True
                    self.selection_start = click_pos
                    self.crop_rect = QRect(self.selection_start, QSize())
    
    def mouseMoveEvent(self, event):
        if not self.display_pixmap:
            return
            
        pixmap_rect = self.pixmap().rect()
        label_rect = self.rect()
        x_offset = (label_rect.width() - pixmap_rect.width()) // 2
        y_offset = (label_rect.height() - pixmap_rect.height()) // 2
        
        current_pos = event.position().toPoint() - QPoint(x_offset, y_offset)
        
        # カーソル変更
        if not self.is_selecting and not self.drag_mode:
            handle = self.get_handle_at_pos(current_pos)
            if handle:
                if handle == 'move':
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                elif handle in ['resize_tl', 'resize_br']:
                    self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                elif handle in ['resize_tr', 'resize_bl']:
                    self.setCursor(Qt.CursorShape.SizeBDiagCursor)
                elif handle in ['resize_t', 'resize_b']:
                    self.setCursor(Qt.CursorShape.SizeVerCursor)
                elif handle in ['resize_l', 'resize_r']:
                    self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        
        # 新規選択中
        if self.is_selecting:
            current_pos.setX(max(0, min(current_pos.x(), pixmap_rect.width())))
            current_pos.setY(max(0, min(current_pos.y(), pixmap_rect.height())))
            
            scaled_rect = QRect(self.selection_start, current_pos).normalized()
            
            self.crop_rect = QRect(
                int(scaled_rect.x() / self.scale_factor),
                int(scaled_rect.y() / self.scale_factor),
                int(scaled_rect.width() / self.scale_factor),
                int(scaled_rect.height() / self.scale_factor)
            )
            
            self.update_display()
        
        # ドラッグ中（移動・リサイズ）
        elif self.drag_mode:
            delta = current_pos - self.drag_start_pos
            
            if self.drag_mode == 'move':
                # 矩形全体を移動
                new_x = self.drag_start_rect.x() + int(delta.x() / self.scale_factor)
                new_y = self.drag_start_rect.y() + int(delta.y() / self.scale_factor)
                
                # 画像境界内に制限
                new_x = max(0, min(new_x, self.original_pixmap.width() - self.drag_start_rect.width()))
                new_y = max(0, min(new_y, self.original_pixmap.height() - self.drag_start_rect.height()))
                
                self.crop_rect = QRect(new_x, new_y, self.drag_start_rect.width(), self.drag_start_rect.height())
            
            else:
                # リサイズ処理
                delta_unscaled = QPoint(int(delta.x() / self.scale_factor), int(delta.y() / self.scale_factor))
                
                # 新しい座標を計算
                left = self.drag_start_rect.left()
                top = self.drag_start_rect.top()
                right = self.drag_start_rect.right()
                bottom = self.drag_start_rect.bottom()
                
                # 各ハンドルに応じて適切な辺だけを変更
                if self.drag_mode == 'resize_tl':
                    left = self.drag_start_rect.left() + delta_unscaled.x()
                    top = self.drag_start_rect.top() + delta_unscaled.y()
                elif self.drag_mode == 'resize_tr':
                    right = self.drag_start_rect.right() + delta_unscaled.x()
                    top = self.drag_start_rect.top() + delta_unscaled.y()
                elif self.drag_mode == 'resize_bl':
                    left = self.drag_start_rect.left() + delta_unscaled.x()
                    bottom = self.drag_start_rect.bottom() + delta_unscaled.y()
                elif self.drag_mode == 'resize_br':
                    right = self.drag_start_rect.right() + delta_unscaled.x()
                    bottom = self.drag_start_rect.bottom() + delta_unscaled.y()
                elif self.drag_mode == 'resize_t':
                    top = self.drag_start_rect.top() + delta_unscaled.y()
                elif self.drag_mode == 'resize_b':
                    bottom = self.drag_start_rect.bottom() + delta_unscaled.y()
                elif self.drag_mode == 'resize_l':
                    left = self.drag_start_rect.left() + delta_unscaled.x()
                elif self.drag_mode == 'resize_r':
                    right = self.drag_start_rect.right() + delta_unscaled.x()
                
                # 矩形が反転しないように制限（最小サイズ10ピクセル）
                if right - left > 10 and bottom - top > 10:
                    # 画像境界内に制限
                    left = max(0, left)
                    top = max(0, top)
                    right = min(self.original_pixmap.width(), right)
                    bottom = min(self.original_pixmap.height(), bottom)
                    
                    self.crop_rect = QRect(left, top, right - left, bottom - top)
            
            self.update_display()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_selecting = False
            self.drag_mode = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if not self.crop_rect.isEmpty():
                self.cropChanged.emit(self.crop_rect)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.original_pixmap:
            self.fit_to_window()
    
    def get_crop_rect(self) -> QRect:
        return self.crop_rect
    
    def set_crop_rect(self, rect: QRect):
        self.crop_rect = rect
        self.update_display()


class BatchImageCropper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_files: List[str] = []
        self.image_sizes = {}  # {file_path: (width, height)}
        self.current_index = -1
        self.crop_rect = QRect()
        self.base_image_size = None  # 基準画像のサイズ
        self.crop_mode = "absolute"  # "absolute" or "proportional"
        
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("バッチ画像切り抜きツール")
        self.setGeometry(100, 100, 1200, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        file_group = QGroupBox("ファイル管理")
        file_layout = QVBoxLayout()
        
        load_btn = QPushButton("画像を追加...")
        load_btn.clicked.connect(self.load_images)
        file_layout.addWidget(load_btn)
        
        clear_btn = QPushButton("リストをクリア")
        clear_btn.clicked.connect(self.clear_list)
        file_layout.addWidget(clear_btn)
        
        file_group.setLayout(file_layout)
        left_layout.addWidget(file_group)
        
        list_group = QGroupBox("画像リスト")
        list_layout = QVBoxLayout()
        
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.on_image_selected)
        list_layout.addWidget(self.file_list)
        
        list_group.setLayout(list_layout)
        left_layout.addWidget(list_group)
        
        crop_group = QGroupBox("切り抜き設定")
        crop_layout = QVBoxLayout()
        
        self.crop_info_label = QLabel("切り抜き範囲: 未設定")
        crop_layout.addWidget(self.crop_info_label)
        
        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("X:"))
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 9999)
        self.x_spin.valueChanged.connect(self.on_manual_crop_changed)
        coord_layout.addWidget(self.x_spin)
        
        coord_layout.addWidget(QLabel("Y:"))
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 9999)
        self.y_spin.valueChanged.connect(self.on_manual_crop_changed)
        coord_layout.addWidget(self.y_spin)
        
        coord_layout.addWidget(QLabel("幅:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 9999)
        self.width_spin.valueChanged.connect(self.on_manual_crop_changed)
        coord_layout.addWidget(self.width_spin)
        
        coord_layout.addWidget(QLabel("高さ:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(0, 9999)
        self.height_spin.valueChanged.connect(self.on_manual_crop_changed)
        coord_layout.addWidget(self.height_spin)
        
        crop_layout.addLayout(coord_layout)
        
        mode_layout = QHBoxLayout()
        self.absolute_radio = QCheckBox("絶対座標で切り抜き")
        self.absolute_radio.setChecked(True)
        self.absolute_radio.toggled.connect(self.on_mode_changed)
        mode_layout.addWidget(self.absolute_radio)
        
        self.proportional_radio = QCheckBox("比率で切り抜き")
        self.proportional_radio.toggled.connect(self.on_mode_changed)
        mode_layout.addWidget(self.proportional_radio)
        crop_layout.addLayout(mode_layout)
        
        self.apply_to_all_checkbox = QCheckBox("同じサイズの画像に適用")
        self.apply_to_all_checkbox.setChecked(True)
        crop_layout.addWidget(self.apply_to_all_checkbox)
        
        self.size_info_label = QLabel("画像サイズ: -")
        crop_layout.addWidget(self.size_info_label)
        
        crop_group.setLayout(crop_layout)
        left_layout.addWidget(crop_group)
        
        action_group = QGroupBox("操作")
        action_layout = QVBoxLayout()
        
        self.crop_btn = QPushButton("選択範囲で切り抜き実行")
        self.crop_btn.clicked.connect(self.crop_images)
        self.crop_btn.setEnabled(False)
        action_layout.addWidget(self.crop_btn)
        
        self.save_btn = QPushButton("切り抜いた画像を保存...")
        self.save_btn.clicked.connect(self.save_cropped_images)
        self.save_btn.setEnabled(False)
        action_layout.addWidget(self.save_btn)
        
        action_group.setLayout(action_layout)
        left_layout.addWidget(action_group)
        
        left_layout.addStretch()
        
        self.image_viewer = ImageViewer()
        self.image_viewer.cropChanged.connect(self.on_crop_changed)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self.image_viewer)
        splitter.setSizes([350, 850])
        
        main_layout.addWidget(splitter)
    
    def load_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "画像ファイルを選択",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        
        if files:
            size_groups = {}
            
            for file in files:
                if file not in self.image_files:
                    image = QImage(file)
                    if not image.isNull():
                        size = (image.width(), image.height())
                        self.image_sizes[file] = size
                        
                        size_key = f"{size[0]}x{size[1]}"
                        if size_key not in size_groups:
                            size_groups[size_key] = []
                        size_groups[size_key].append(file)
                        
                        self.image_files.append(file)
                        item_text = f"{os.path.basename(file)} [{size[0]}x{size[1]}]"
                        item = QListWidgetItem(item_text)
                        item.setData(Qt.ItemDataRole.UserRole, file)
                        
                        if len(size_groups) > 1:
                            item.setForeground(QColor(200, 100, 0))
                            item.setToolTip(f"サイズ: {size[0]}x{size[1]}")
                        
                        self.file_list.addItem(item)
            
            if len(size_groups) > 1:
                sizes_text = "\n".join([f"- {size}: {len(files)}枚" for size, files in size_groups.items()])
                QMessageBox.information(
                    self,
                    "異なるサイズの画像を検出",
                    f"複数の画像サイズが検出されました:\n{sizes_text}\n\n"
                    "絶対座標モードでは同じサイズの画像のみが正しく切り抜かれます。\n"
                    "比率モードを使用すると、異なるサイズでも相対的に切り抜きできます。"
                )
            
            if self.current_index == -1 and self.image_files:
                self.file_list.setCurrentRow(0)
                self.on_image_selected(self.file_list.item(0))
    
    def clear_list(self):
        self.file_list.clear()
        self.image_files.clear()
        self.image_sizes.clear()
        self.base_image_size = None
        self.current_index = -1
        self.image_viewer.set_image("")
        self.crop_rect = QRect()
        self.update_crop_info()
        self.crop_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.size_info_label.setText("画像サイズ: -")
    
    def on_image_selected(self, item):
        if not item:
            return
        
        file_path = item.data(Qt.ItemDataRole.UserRole)
        self.current_index = self.file_list.row(item)
        
        if self.image_viewer.set_image(file_path):
            if file_path in self.image_sizes:
                size = self.image_sizes[file_path]
                self.size_info_label.setText(f"画像サイズ: {size[0]}x{size[1]}")
                
                if not self.base_image_size:
                    self.base_image_size = size
                
                same_size_count = sum(1 for s in self.image_sizes.values() if s == size)
                if same_size_count > 1:
                    self.apply_to_all_checkbox.setText(f"同じサイズの画像に適用 ({same_size_count}枚)")
                else:
                    self.apply_to_all_checkbox.setText("同じサイズの画像に適用 (この画像のみ)")
            
            if not self.crop_rect.isEmpty():
                self.image_viewer.set_crop_rect(self.crop_rect)
    
    def on_crop_changed(self, rect: QRect):
        self.crop_rect = rect
        self.update_crop_info()
        self.crop_btn.setEnabled(not rect.isEmpty() and len(self.image_files) > 0)
    
    def on_manual_crop_changed(self):
        self.crop_rect = QRect(
            self.x_spin.value(),
            self.y_spin.value(),
            self.width_spin.value(),
            self.height_spin.value()
        )
        self.image_viewer.set_crop_rect(self.crop_rect)
        self.crop_btn.setEnabled(not self.crop_rect.isEmpty() and len(self.image_files) > 0)
    
    def update_crop_info(self):
        if self.crop_rect.isEmpty():
            self.crop_info_label.setText("切り抜き範囲: 未設定")
            self.x_spin.setValue(0)
            self.y_spin.setValue(0)
            self.width_spin.setValue(0)
            self.height_spin.setValue(0)
        else:
            self.crop_info_label.setText(
                f"切り抜き範囲: ({self.crop_rect.x()}, {self.crop_rect.y()}) - "
                f"{self.crop_rect.width()}x{self.crop_rect.height()}"
            )
            self.x_spin.blockSignals(True)
            self.y_spin.blockSignals(True)
            self.width_spin.blockSignals(True)
            self.height_spin.blockSignals(True)
            
            self.x_spin.setValue(self.crop_rect.x())
            self.y_spin.setValue(self.crop_rect.y())
            self.width_spin.setValue(self.crop_rect.width())
            self.height_spin.setValue(self.crop_rect.height())
            
            self.x_spin.blockSignals(False)
            self.y_spin.blockSignals(False)
            self.width_spin.blockSignals(False)
            self.height_spin.blockSignals(False)
    
    def on_mode_changed(self):
        if self.absolute_radio.isChecked():
            self.crop_mode = "absolute"
            self.proportional_radio.setChecked(False)
        elif self.proportional_radio.isChecked():
            self.crop_mode = "proportional"
            self.absolute_radio.setChecked(False)
    
    def crop_images(self):
        if self.crop_rect.isEmpty():
            QMessageBox.warning(self, "警告", "切り抜き範囲が設定されていません。")
            return
        
        if not self.image_files:
            QMessageBox.warning(self, "警告", "画像が読み込まれていません。")
            return
        
        current_file = self.image_files[self.current_index]
        current_size = self.image_sizes.get(current_file)
        
        if self.apply_to_all_checkbox.isChecked():
            if self.crop_mode == "absolute":
                files_to_crop = [f for f in self.image_files if self.image_sizes.get(f) == current_size]
            else:
                files_to_crop = self.image_files
        else:
            files_to_crop = [current_file]
        
        progress = QProgressDialog("画像を切り抜き中...", "キャンセル", 0, len(files_to_crop), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        self.cropped_images = []
        
        for i, file_path in enumerate(files_to_crop):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            progress.setLabelText(f"処理中: {os.path.basename(file_path)}")
            
            image = QImage(file_path)
            if not image.isNull():
                if self.crop_mode == "proportional" and current_size:
                    file_size = self.image_sizes.get(file_path)
                    if file_size and file_size != current_size:
                        scale_x = file_size[0] / current_size[0]
                        scale_y = file_size[1] / current_size[1]
                        
                        scaled_rect = QRect(
                            int(self.crop_rect.x() * scale_x),
                            int(self.crop_rect.y() * scale_y),
                            int(self.crop_rect.width() * scale_x),
                            int(self.crop_rect.height() * scale_y)
                        )
                        cropped = image.copy(scaled_rect)
                    else:
                        cropped = image.copy(self.crop_rect)
                else:
                    cropped = image.copy(self.crop_rect)
                
                self.cropped_images.append((os.path.basename(file_path), cropped))
        
        progress.setValue(len(files_to_crop))
        
        if self.cropped_images:
            QMessageBox.information(self, "完了", f"{len(self.cropped_images)}枚の画像を切り抜きました。")
            self.save_btn.setEnabled(True)
    
    def save_cropped_images(self):
        if not hasattr(self, 'cropped_images') or not self.cropped_images:
            QMessageBox.warning(self, "警告", "切り抜いた画像がありません。")
            return
        
        folder = QFileDialog.getExistingDirectory(self, "保存先フォルダを選択")
        if not folder:
            return
        
        progress = QProgressDialog("画像を保存中...", "キャンセル", 0, len(self.cropped_images), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        saved_count = 0
        for i, (filename, image) in enumerate(self.cropped_images):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            progress.setLabelText(f"保存中: {filename}")
            
            name, ext = os.path.splitext(filename)
            save_path = os.path.join(folder, f"{name}_cropped{ext}")
            
            counter = 1
            while os.path.exists(save_path):
                save_path = os.path.join(folder, f"{name}_cropped_{counter}{ext}")
                counter += 1
            
            if image.save(save_path):
                saved_count += 1
        
        progress.setValue(len(self.cropped_images))
        
        QMessageBox.information(self, "完了", f"{saved_count}枚の画像を保存しました。")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = BatchImageCropper()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()