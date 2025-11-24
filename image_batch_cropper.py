#!/usr/bin/env python3
import sys
import os
from pathlib import Path
from typing import List, Optional, Tuple
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QListWidget, QLabel, QScrollArea,
    QSplitter, QMessageBox, QSpinBox, QGroupBox, QListWidgetItem,
    QCheckBox, QProgressDialog, QMenu, QAbstractItemView, QComboBox
)
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QSize, QRectF, QPointF, QTimer
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QImage, QBrush, QCursor


class ImageViewer(QLabel):
    cropChanged = Signal(QRect)
    cropChanging = Signal(QRect)  # リアルタイム更新用のシグナル
    zoomChanged = Signal(float)  # ズーム率変更通知

    def __init__(self):
        super().__init__()
        self.setScaledContents(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("QLabel { background-color: #f0f0f0; border: 1px solid #ccc; }")
        self.setMouseTracking(True)

        self.original_pixmap = None
        self.display_pixmap = None
        self.scale_factor = 1.0
        self.min_scale_factor = 0.1
        self.max_scale_factor = 10.0
        self.pan_offset = QPointF(0, 0)
        self.crop_rect = QRect()
        self.is_selecting = False
        self.selection_start = QPoint()
        self.user_zoomed = False  # ユーザーが手動でズームしたかを追跡

        # リサイズ用の変数
        self.drag_mode = None  # None, 'move', 'resize_tl', 'resize_tr', 'resize_bl', 'resize_br', 'resize_t', 'resize_b', 'resize_l', 'resize_r', 'pan'
        self.drag_start_pos = QPoint()
        self.drag_start_rect = QRect()
        self.handle_size = 8

        # パン用の変数（右クリックドラッグ）
        self.is_panning = False
        self.pan_start_pos = QPoint()
        self.scroll_start_x = 0
        self.scroll_start_y = 0

        # アスペクト比固定
        self.aspect_ratio_locked = False
        self.aspect_ratio = 1.0  # width / height
        
    def set_image(self, image_path: str):
        self.original_pixmap = QPixmap(image_path)
        if self.original_pixmap.isNull():
            return False

        self.user_zoomed = False  # 新しい画像をロードしたらフラグをリセット
        self.fit_to_window()
        # スクロール位置を画像中央に設定（レイアウト更新後に実行）
        QTimer.singleShot(0, self.center_image)
        return True
    
    def fit_to_window(self):
        if not self.original_pixmap:
            return

        # スクロールエリア内にいるため、親（viewport）のサイズを取得
        # 親がない場合は、デフォルトサイズ（800x600）を使用
        if self.parent():
            widget_size = self.parent().size()
        else:
            widget_size = QSize(800, 600)

        pixmap_size = self.original_pixmap.size()

        scale_w = widget_size.width() / pixmap_size.width()
        scale_h = widget_size.height() / pixmap_size.height()
        self.scale_factor = min(scale_w, scale_h, 1.0) * 0.95

        scaled_size = pixmap_size * self.scale_factor

        # 倍率に応じてスケーリング方式を切り替え
        # 100%以上：FastTransformation（ピクセル境界くっきり）
        # 100%未満：SmoothTransformation（滑らかに縮小）
        transform_mode = Qt.TransformationMode.FastTransformation if self.scale_factor >= 1.0 else Qt.TransformationMode.SmoothTransformation

        self.display_pixmap = self.original_pixmap.scaled(
            scaled_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            transform_mode
        )

        self.update_display()
        self.zoomChanged.emit(self.scale_factor)
    
    def update_display(self):
        if not self.display_pixmap:
            self.setPixmap(QPixmap())  # 空のPixmapを設定
            self.setMinimumSize(400, 300)  # 最小サイズを設定
            return

        # 画像サイズの3倍のキャンバスを作成（上下左右に画像サイズ分の余白）
        # これにより、画像を自由に移動できる
        widget_width = self.display_pixmap.width() * 3
        widget_height = self.display_pixmap.height() * 3

        self.setFixedSize(widget_width, widget_height)

        # 再描画して矩形を表示
        self.update()

    def paintEvent(self, event):
        """画像と矩形を描画"""
        # 親クラスのpaintEventは呼ばない（自分で描画する）

        if not self.display_pixmap:
            return

        painter = QPainter(self)

        # 画像を中央に描画（3倍キャンバスの中央）
        label_rect = self.rect()
        x_offset = (label_rect.width() - self.display_pixmap.width()) // 2
        y_offset = (label_rect.height() - self.display_pixmap.height()) // 2

        painter.drawPixmap(x_offset, y_offset, self.display_pixmap)

        if self.crop_rect.isEmpty():
            painter.end()
            return

        # 切り抜き矩形をスケール変換
        scaled_rect = QRect(
            int(self.crop_rect.x() * self.scale_factor),
            int(self.crop_rect.y() * self.scale_factor),
            int(self.crop_rect.width() * self.scale_factor),
            int(self.crop_rect.height() * self.scale_factor)
        )

        # オフセットを適用
        scaled_rect.translate(x_offset, y_offset)

        # 画像の範囲
        image_rect = QRect(x_offset, y_offset, self.display_pixmap.width(), self.display_pixmap.height())

        # 暗いオーバーレイ（画像内の切り抜き範囲外のみ）
        # 上部
        if scaled_rect.top() > image_rect.top():
            painter.fillRect(image_rect.left(), image_rect.top(), image_rect.width(), scaled_rect.top() - image_rect.top(), QBrush(QColor(0, 0, 0, 100)))
        # 下部
        if scaled_rect.bottom() < image_rect.bottom():
            painter.fillRect(image_rect.left(), scaled_rect.bottom(), image_rect.width(), image_rect.bottom() - scaled_rect.bottom(), QBrush(QColor(0, 0, 0, 100)))
        # 左部
        if scaled_rect.left() > image_rect.left():
            painter.fillRect(image_rect.left(), scaled_rect.top(), scaled_rect.left() - image_rect.left(), scaled_rect.height(), QBrush(QColor(0, 0, 0, 100)))
        # 右部
        if scaled_rect.right() < image_rect.right():
            painter.fillRect(scaled_rect.right(), scaled_rect.top(), image_rect.right() - scaled_rect.right(), scaled_rect.height(), QBrush(QColor(0, 0, 0, 100)))

        # 外側の赤い実線（切り取り線の外側を示す）
        pen_outer = QPen(QColor(255, 0, 0), 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen_outer)
        painter.drawRect(scaled_rect)

        # 内側の白い破線（切り取り線の内側を示す）
        pen_inner = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_inner)
        # 1ピクセル内側に描画
        inner_rect = scaled_rect.adjusted(1, 1, -1, -1)
        painter.drawRect(inner_rect)

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
    
    def get_image_offset(self):
        """画像の描画オフセットを取得"""
        if not self.display_pixmap:
            return QPoint(0, 0)
        label_rect = self.rect()
        x_offset = (label_rect.width() - self.display_pixmap.width()) // 2
        y_offset = (label_rect.height() - self.display_pixmap.height()) // 2
        return QPoint(x_offset, y_offset)

    def get_handle_at_pos(self, pos):
        """マウス位置にあるハンドルを判定"""
        if self.crop_rect.isEmpty():
            return None

        offset = self.get_image_offset()

        scaled_rect = QRect(
            int(self.crop_rect.x() * self.scale_factor) + offset.x(),
            int(self.crop_rect.y() * self.scale_factor) + offset.y(),
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
        # 右クリックでパン（スクロール）開始
        if event.button() == Qt.MouseButton.RightButton:
            self.is_panning = True
            self.pan_start_pos = event.globalPosition().toPoint()

            # スクロールエリアの現在のスクロール位置を保存
            scroll_area = self.get_scroll_area()
            if scroll_area:
                self.scroll_start_x = scroll_area.horizontalScrollBar().value()
                self.scroll_start_y = scroll_area.verticalScrollBar().value()

            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton and self.display_pixmap:
            offset = self.get_image_offset()
            click_pos = event.position().toPoint() - offset

            # 画像の範囲内をクリックしたか確認
            image_rect = QRect(0, 0, self.display_pixmap.width(), self.display_pixmap.height())
            if image_rect.contains(click_pos):
                handle = self.get_handle_at_pos(event.position().toPoint())

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

        # パン（スクロール）中の処理
        if self.is_panning:
            current_pos = event.globalPosition().toPoint()
            delta = current_pos - self.pan_start_pos

            # スクロールエリアのスクロール位置を更新（ドラッグの逆方向）
            scroll_area = self.get_scroll_area()
            if scroll_area:
                scroll_area.horizontalScrollBar().setValue(self.scroll_start_x - delta.x())
                scroll_area.verticalScrollBar().setValue(self.scroll_start_y - delta.y())
            return

        offset = self.get_image_offset()

        # 浮動小数点精度を保持
        current_pos_float = event.position() - QPointF(offset.x(), offset.y())
        current_pos = current_pos_float.toPoint()

        # 画像の範囲
        image_rect = QRect(0, 0, self.display_pixmap.width(), self.display_pixmap.height())

        # カーソル変更
        if not self.is_selecting and not self.drag_mode:
            handle = self.get_handle_at_pos(event.position().toPoint())
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
            current_pos.setX(max(0, min(current_pos.x(), image_rect.width())))
            current_pos.setY(max(0, min(current_pos.y(), image_rect.height())))

            scaled_rect = QRect(self.selection_start, current_pos).normalized()

            # アスペクト比固定の場合は調整
            if self.aspect_ratio_locked and scaled_rect.width() > 0 and scaled_rect.height() > 0:
                # 開始点を固定し、現在の位置に基づいて比率を維持
                width = scaled_rect.width()
                height = scaled_rect.height()

                # より大きく変化した方向に合わせる
                if abs(current_pos.x() - self.selection_start.x()) / self.aspect_ratio > abs(current_pos.y() - self.selection_start.y()):
                    # 幅基準
                    height = int(width / self.aspect_ratio)
                else:
                    # 高さ基準
                    width = int(height * self.aspect_ratio)

                # 矩形を再構築（開始点と符号を維持）
                if current_pos.x() >= self.selection_start.x():
                    x = self.selection_start.x()
                else:
                    x = self.selection_start.x() - width

                if current_pos.y() >= self.selection_start.y():
                    y = self.selection_start.y()
                else:
                    y = self.selection_start.y() - height

                scaled_rect = QRect(x, y, width, height)

            self.crop_rect = QRect(
                int(scaled_rect.x() / self.scale_factor),
                int(scaled_rect.y() / self.scale_factor),
                int(scaled_rect.width() / self.scale_factor),
                int(scaled_rect.height() / self.scale_factor)
            )

            self.update()  # Pixmapコピーなしで再描画
            self.cropChanging.emit(self.crop_rect)  # リアルタイム通知

        # ドラッグ中（移動・リサイズ）
        elif self.drag_mode:
            # 浮動小数点で差分を計算してから変換
            delta_float = QPointF(current_pos_float.x() - self.drag_start_pos.x(),
                                 current_pos_float.y() - self.drag_start_pos.y())

            # スケール変換前にスナップ処理（画面上のピクセル単位）
            snap_threshold = 0.5
            if abs(delta_float.x()) < snap_threshold:
                delta_float.setX(0)
            if abs(delta_float.y()) < snap_threshold:
                delta_float.setY(0)

            delta_unscaled = QPointF(delta_float.x() / self.scale_factor,
                                    delta_float.y() / self.scale_factor)

            if self.drag_mode == 'move':
                # 矩形全体を移動
                new_x = round(self.drag_start_rect.x() + delta_unscaled.x())
                new_y = round(self.drag_start_rect.y() + delta_unscaled.y())

                # 画像境界内に制限
                new_x = max(0, min(new_x, self.original_pixmap.width() - self.drag_start_rect.width()))
                new_y = max(0, min(new_y, self.original_pixmap.height() - self.drag_start_rect.height()))

                if new_x != self.crop_rect.x() or new_y != self.crop_rect.y():
                    self.crop_rect = QRect(new_x, new_y, self.drag_start_rect.width(), self.drag_start_rect.height())
                    self.update()  # Pixmapコピーなしで再描画
                    self.cropChanging.emit(self.crop_rect)  # リアルタイム通知

            else:
                # リサイズ処理 - 浮動小数点精度を維持
                # 新しい座標を計算（浮動小数点）
                left = float(self.drag_start_rect.left())
                top = float(self.drag_start_rect.top())
                right = float(self.drag_start_rect.right())
                bottom = float(self.drag_start_rect.bottom())

                # アスペクト比固定時は辺のハンドルでのリサイズを無効化
                if self.aspect_ratio_locked and self.drag_mode in ['resize_t', 'resize_b', 'resize_l', 'resize_r']:
                    return

                # 各ハンドルに応じて適切な辺だけを変更
                if self.drag_mode == 'resize_tl':
                    left = self.drag_start_rect.left() + delta_unscaled.x()
                    top = self.drag_start_rect.top() + delta_unscaled.y()
                    # アスペクト比固定
                    if self.aspect_ratio_locked:
                        width = right - left
                        height = width / self.aspect_ratio
                        top = bottom - height
                elif self.drag_mode == 'resize_tr':
                    right = self.drag_start_rect.right() + delta_unscaled.x()
                    top = self.drag_start_rect.top() + delta_unscaled.y()
                    # アスペクト比固定
                    if self.aspect_ratio_locked:
                        width = right - left
                        height = width / self.aspect_ratio
                        top = bottom - height
                elif self.drag_mode == 'resize_bl':
                    left = self.drag_start_rect.left() + delta_unscaled.x()
                    bottom = self.drag_start_rect.bottom() + delta_unscaled.y()
                    # アスペクト比固定
                    if self.aspect_ratio_locked:
                        width = right - left
                        height = width / self.aspect_ratio
                        bottom = top + height
                elif self.drag_mode == 'resize_br':
                    right = self.drag_start_rect.right() + delta_unscaled.x()
                    bottom = self.drag_start_rect.bottom() + delta_unscaled.y()
                    # アスペクト比固定
                    if self.aspect_ratio_locked:
                        width = right - left
                        height = width / self.aspect_ratio
                        bottom = top + height
                elif self.drag_mode == 'resize_t':
                    top = self.drag_start_rect.top() + delta_unscaled.y()
                elif self.drag_mode == 'resize_b':
                    bottom = self.drag_start_rect.bottom() + delta_unscaled.y()
                elif self.drag_mode == 'resize_l':
                    left = self.drag_start_rect.left() + delta_unscaled.x()
                elif self.drag_mode == 'resize_r':
                    right = self.drag_start_rect.right() + delta_unscaled.x()

                # 最後に整数に丸める
                left = round(left)
                top = round(top)
                right = round(right)
                bottom = round(bottom)

                # 矩形が反転しないように制限（最小サイズ10ピクセル）
                if right - left > 10 and bottom - top > 10:
                    # 画像境界内に制限
                    left = max(0, left)
                    top = max(0, top)
                    right = min(self.original_pixmap.width(), right)
                    bottom = min(self.original_pixmap.height(), bottom)

                    new_rect = QRect(int(left), int(top), int(right - left), int(bottom - top))
                    if new_rect != self.crop_rect:
                        self.crop_rect = new_rect
                        self.update()  # Pixmapコピーなしで再描画
                        self.cropChanging.emit(self.crop_rect)  # リアルタイム通知
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self.is_selecting = False
            self.drag_mode = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if not self.crop_rect.isEmpty():
                self.cropChanged.emit(self.crop_rect)

    def wheelEvent(self, event):
        """マウスホイールでズーム（マウス位置を中心に）"""
        if not self.original_pixmap:
            return

        # スクロールエリアを取得
        scroll_area = self.get_scroll_area()
        if not scroll_area:
            return

        # ズーム前のマウス位置（ImageViewer座標系）
        mouse_pos_widget = event.position()

        # 画像のオフセットを取得
        offset = self.get_image_offset()

        # マウスが画像上の位置（スケール済み画像での座標）
        mouse_on_image_x = mouse_pos_widget.x() - offset.x()
        mouse_on_image_y = mouse_pos_widget.y() - offset.y()

        # 元画像のピクセル座標
        image_x = mouse_on_image_x / self.scale_factor
        image_y = mouse_on_image_y / self.scale_factor

        # ズーム倍率の変更
        old_scale = self.scale_factor
        zoom_delta = event.angleDelta().y() / 120.0
        zoom_factor = 1.1 ** zoom_delta

        new_scale = old_scale * zoom_factor
        new_scale = max(self.min_scale_factor, min(self.max_scale_factor, new_scale))

        if new_scale == old_scale:
            return

        self.user_zoomed = True
        self.scale_factor = new_scale

        # 新しいスケールで画像をスケーリング
        pixmap_size = self.original_pixmap.size()
        scaled_size = pixmap_size * self.scale_factor

        # 倍率に応じてスケーリング方式を切り替え
        # 100%以上：FastTransformation（ピクセル境界くっきり）
        # 100%未満：SmoothTransformation（滑らかに縮小）
        transform_mode = Qt.TransformationMode.FastTransformation if self.scale_factor >= 1.0 else Qt.TransformationMode.SmoothTransformation

        self.display_pixmap = self.original_pixmap.scaled(
            scaled_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            transform_mode
        )

        self.update_display()
        self.zoomChanged.emit(self.scale_factor)

        # マウス位置が同じ画像座標を指すようにスクロール位置を調整
        # viewport内でのマウス位置（グローバル座標から変換）
        viewport = scroll_area.viewport()
        global_mouse_pos = self.mapToGlobal(mouse_pos_widget.toPoint())
        viewport_mouse_pos = viewport.mapFromGlobal(global_mouse_pos)

        # 新しいスケールでの画像上の位置
        new_mouse_on_image_x = image_x * self.scale_factor
        new_mouse_on_image_y = image_y * self.scale_factor

        # 新しいオフセット（3倍キャンバスの中央）
        new_offset = self.get_image_offset()

        # マウスがviewport内の同じ位置にいるために必要なスクロール位置
        # ImageViewer座標 = スクロール位置 + viewport内の位置
        # スクロール位置 = ImageViewer座標 - viewport内の位置
        new_scroll_x = (new_mouse_on_image_x + new_offset.x()) - viewport_mouse_pos.x()
        new_scroll_y = (new_mouse_on_image_y + new_offset.y()) - viewport_mouse_pos.y()

        # スクロールバーの範囲内に制限
        h_bar = scroll_area.horizontalScrollBar()
        v_bar = scroll_area.verticalScrollBar()

        new_scroll_x = max(h_bar.minimum(), min(int(new_scroll_x), h_bar.maximum()))
        new_scroll_y = max(v_bar.minimum(), min(int(new_scroll_y), v_bar.maximum()))

        h_bar.setValue(new_scroll_x)
        v_bar.setValue(new_scroll_y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # スクロールエリア内にいるため、resizeEventでの自動調整は無効化
        # 画像読み込み時のみfit_to_window()を呼ぶ
    
    def get_crop_rect(self) -> QRect:
        return self.crop_rect

    def set_crop_rect(self, rect: QRect):
        self.crop_rect = rect
        self.update()  # Pixmapコピーなしで再描画

    def set_aspect_ratio(self, locked: bool, ratio: float = 1.0):
        """アスペクト比を設定"""
        self.aspect_ratio_locked = locked
        self.aspect_ratio = ratio

    def get_scroll_area(self):
        """親のQScrollAreaを取得"""
        parent = self.parent()
        if parent:
            # parentはviewportなので、その親がQScrollArea
            scroll_area = parent.parent()
            if isinstance(scroll_area, QScrollArea):
                return scroll_area
        return None

    def center_image(self):
        """スクロール位置を調整して画像を中央に表示"""
        if not self.display_pixmap:
            return

        scroll_area = self.get_scroll_area()
        if not scroll_area:
            return

        # 3倍キャンバスの中央に画像が描画されているので、
        # スクロール位置を画像の中央に合わせる
        # 画像の中央位置（ウィジェット座標系）
        # 3倍キャンバスの中央 = 画像サイズ * 3 / 2
        image_center_x = self.display_pixmap.width() * 3 // 2
        image_center_y = self.display_pixmap.height() * 3 // 2

        # viewportのサイズ
        viewport = scroll_area.viewport()
        viewport_width = viewport.width()
        viewport_height = viewport.height()

        # 画像の中央がviewportの中央に来るようなスクロール位置
        scroll_x = image_center_x - viewport_width // 2
        scroll_y = image_center_y - viewport_height // 2

        # スクロールバーに設定
        scroll_area.horizontalScrollBar().setValue(scroll_x)
        scroll_area.verticalScrollBar().setValue(scroll_y)


class BatchImageCropper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_files: List[str] = []
        self.image_sizes = {}  # {file_path: (width, height)}
        self.current_index = -1
        self.crop_rect = QRect()

        self.setup_ui()
        self.setAcceptDrops(True)  # ドラッグ&ドロップを有効化
    
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

        # 画像を追加ボタン
        load_btn = QPushButton("画像を追加...")
        load_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogOpenButton))
        load_btn.setMinimumHeight(40)
        load_btn.setToolTip("切り抜きたい画像ファイルを選択します\n(PNG, JPG, BMP, GIF対応)")
        load_btn.clicked.connect(self.load_images)
        file_layout.addWidget(load_btn)

        # 選択した画像を削除ボタン
        remove_btn = QPushButton("選択した画像を削除")
        remove_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogDiscardButton))
        remove_btn.setMinimumHeight(40)
        remove_btn.setToolTip("リストで選択中の画像を削除します\n(Ctrl/Shiftキーで複数選択可能)")
        remove_btn.clicked.connect(self.remove_selected_images)
        file_layout.addWidget(remove_btn)

        # リストをクリアボタン
        clear_btn = QPushButton("リストをクリア")
        clear_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogResetButton))
        clear_btn.setMinimumHeight(40)
        clear_btn.setToolTip("すべての画像をリストから削除します")
        clear_btn.clicked.connect(self.clear_list)
        file_layout.addWidget(clear_btn)

        file_group.setLayout(file_layout)
        left_layout.addWidget(file_group)
        
        list_group = QGroupBox("画像リスト")
        list_layout = QVBoxLayout()

        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.on_image_selected)
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_context_menu)
        list_layout.addWidget(self.file_list)

        # 表示情報（画像サイズとズーム）
        self.size_info_label = QLabel("画像サイズ: -")
        self.size_info_label.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        list_layout.addWidget(self.size_info_label)

        self.zoom_info_label = QLabel("ズーム: 100%")
        self.zoom_info_label.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        list_layout.addWidget(self.zoom_info_label)

        list_group.setLayout(list_layout)
        left_layout.addWidget(list_group)
        
        crop_group = QGroupBox("切り抜き設定")
        crop_layout = QVBoxLayout()

        self.crop_info_label = QLabel("切り抜き範囲: 未設定")
        crop_layout.addWidget(self.crop_info_label)

        # X, Y 座標
        xy_layout = QHBoxLayout()
        xy_layout.addWidget(QLabel("X:"))
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 9999)
        self.x_spin.setToolTip("切り抜き範囲の左上X座標")
        self.x_spin.valueChanged.connect(self.on_crop_spin_changed)
        xy_layout.addWidget(self.x_spin)

        xy_layout.addWidget(QLabel("Y:"))
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 9999)
        self.y_spin.setToolTip("切り抜き範囲の左上Y座標")
        self.y_spin.valueChanged.connect(self.on_crop_spin_changed)
        xy_layout.addWidget(self.y_spin)

        crop_layout.addLayout(xy_layout)

        # 幅、高さ
        wh_layout = QHBoxLayout()
        wh_layout.addWidget(QLabel("幅:"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 9999)
        self.width_spin.setToolTip("切り抜き範囲の幅")
        self.width_spin.valueChanged.connect(self.on_crop_spin_changed)
        wh_layout.addWidget(self.width_spin)

        wh_layout.addWidget(QLabel("高さ:"))
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 9999)
        self.height_spin.setToolTip("切り抜き範囲の高さ")
        self.height_spin.valueChanged.connect(self.on_crop_spin_changed)
        wh_layout.addWidget(self.height_spin)

        crop_layout.addLayout(wh_layout)

        # アスペクト比固定
        aspect_layout = QHBoxLayout()
        self.aspect_ratio_checkbox = QCheckBox("アスペクト比固定")
        self.aspect_ratio_checkbox.setToolTip("切り抜き矩形の縦横比を固定します")
        self.aspect_ratio_checkbox.toggled.connect(self.on_aspect_ratio_toggled)
        aspect_layout.addWidget(self.aspect_ratio_checkbox)

        self.aspect_ratio_combo = QComboBox()
        self.aspect_ratio_combo.addItems(["1:1 (正方形)", "4:3", "3:2", "16:9", "16:10", "21:9", "カスタム"])
        self.aspect_ratio_combo.setToolTip("固定する縦横比を選択します")
        self.aspect_ratio_combo.setEnabled(False)
        self.aspect_ratio_combo.currentIndexChanged.connect(self.on_aspect_ratio_changed)
        aspect_layout.addWidget(self.aspect_ratio_combo)

        crop_layout.addLayout(aspect_layout)

        # カスタム比率入力
        custom_ratio_layout = QHBoxLayout()
        custom_ratio_layout.addWidget(QLabel("カスタム比率:"))
        self.custom_width_spin = QSpinBox()
        self.custom_width_spin.setRange(1, 999)
        self.custom_width_spin.setValue(16)
        self.custom_width_spin.setEnabled(False)
        self.custom_width_spin.setToolTip("カスタム比率の幅")
        self.custom_width_spin.valueChanged.connect(self.on_custom_ratio_changed)
        custom_ratio_layout.addWidget(self.custom_width_spin)

        custom_ratio_layout.addWidget(QLabel(":"))
        self.custom_height_spin = QSpinBox()
        self.custom_height_spin.setRange(1, 999)
        self.custom_height_spin.setValue(9)
        self.custom_height_spin.setEnabled(False)
        self.custom_height_spin.setToolTip("カスタム比率の高さ")
        self.custom_height_spin.valueChanged.connect(self.on_custom_ratio_changed)
        custom_ratio_layout.addWidget(self.custom_height_spin)

        custom_ratio_layout.addStretch()
        crop_layout.addLayout(custom_ratio_layout)

        crop_group.setLayout(crop_layout)
        left_layout.addWidget(crop_group)
        
        action_group = QGroupBox("操作")
        action_layout = QVBoxLayout()

        # 切り抜いて保存ボタン
        self.crop_and_save_btn = QPushButton("切り抜いて保存...")
        self.crop_and_save_btn.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DialogSaveButton))
        self.crop_and_save_btn.setMinimumHeight(50)
        self.crop_and_save_btn.setToolTip("設定した範囲で画像を切り抜き、\n保存先フォルダに保存します")
        self.crop_and_save_btn.clicked.connect(self.crop_and_save_images)
        self.crop_and_save_btn.setEnabled(False)

        # ボタンのフォントサイズを大きくして目立たせる
        font = self.crop_and_save_btn.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        self.crop_and_save_btn.setFont(font)

        action_layout.addWidget(self.crop_and_save_btn)

        action_group.setLayout(action_layout)
        left_layout.addWidget(action_group)
        
        left_layout.addStretch()

        self.image_viewer = ImageViewer()
        self.image_viewer.cropChanged.connect(self.on_crop_changed)
        self.image_viewer.cropChanging.connect(self.on_crop_changing)  # リアルタイム更新
        self.image_viewer.zoomChanged.connect(self.on_zoom_changed)  # ズーム率更新

        # スクロールエリアで画像ビューアをラップ
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_viewer)
        scroll_area.setWidgetResizable(False)  # 拡大時にスクロールバーを表示
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(scroll_area)
        splitter.setSizes([250, 950])

        # 左側のパネルは固定幅、右側の画像エリアだけが伸縮する
        splitter.setStretchFactor(0, 0)  # 左側は伸縮しない
        splitter.setStretchFactor(1, 1)  # 右側だけが伸縮する

        # 両側のパネルに最小幅を設定（これ以上小さくできないようにする）
        left_panel.setMinimumWidth(200)
        scroll_area.setMinimumWidth(400)

        main_layout.addWidget(splitter)
    
    def load_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "画像ファイルを選択",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        
        if files:
            self.add_image_files(files)
    
    def clear_list(self):
        self.file_list.clear()
        self.image_files.clear()
        self.image_sizes.clear()
        self.current_index = -1
        # 画像ビューアを適切にクリア
        self.image_viewer.original_pixmap = None
        self.image_viewer.display_pixmap = None
        self.image_viewer.crop_rect = QRect()
        self.image_viewer.setPixmap(QPixmap())  # 空のPixmapをセット
        self.crop_rect = QRect()
        self.update_crop_info()
        self.crop_and_save_btn.setEnabled(False)
        self.size_info_label.setText("画像サイズ: -")
        self.zoom_info_label.setText("ズーム: 100%")
    
    def on_image_selected(self, item):
        if not item:
            return

        file_path = item.data(Qt.ItemDataRole.UserRole)
        self.current_index = self.file_list.row(item)

        if self.image_viewer.set_image(file_path):
            if file_path in self.image_sizes:
                size = self.image_sizes[file_path]
                self.size_info_label.setText(f"画像サイズ: {size[0]}x{size[1]}")

                # スピンボックスの最大値を画像サイズに設定
                self.update_spin_ranges()

                # リスト表示を更新（処理対象かどうかを視覚化）
                self.update_list_item_styles()

            if not self.crop_rect.isEmpty():
                self.image_viewer.set_crop_rect(self.crop_rect)
    
    def on_crop_changed(self, rect: QRect):
        self.crop_rect = rect
        self.update_crop_info()
        self.crop_and_save_btn.setEnabled(not rect.isEmpty() and len(self.image_files) > 0)

    def on_crop_changing(self, rect: QRect):
        """マウス操作中のリアルタイム更新"""
        self.crop_rect = rect
        self.update_crop_info()
        self.crop_and_save_btn.setEnabled(not rect.isEmpty() and len(self.image_files) > 0)
    
    def update_list_item_styles(self):
        """選択中の画像と同じサイズかどうかで表示を変更"""
        if self.current_index < 0 or self.current_index >= len(self.image_files):
            return

        current_file = self.image_files[self.current_index]
        if current_file not in self.image_sizes:
            return

        current_size = self.image_sizes[current_file]
        same_size_count = 0

        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            file_path = item.data(Qt.ItemDataRole.UserRole)

            if file_path in self.image_sizes:
                size = self.image_sizes[file_path]
                is_same_size = (size == current_size)

                if is_same_size:
                    # 処理対象: 通常の色
                    item.setForeground(QColor(0, 0, 0))
                    item.setToolTip(f"サイズ: {size[0]}x{size[1]}\n✓ この画像は切り抜き処理されます")
                    same_size_count += 1
                else:
                    # スキップ対象: 灰色
                    item.setForeground(QColor(150, 150, 150))
                    item.setToolTip(f"サイズ: {size[0]}x{size[1]}\n✗ サイズが異なるためスキップされます")

        # ボタンのツールチップを更新
        if same_size_count > 0:
            self.crop_and_save_btn.setToolTip(
                f"設定した範囲で画像を切り抜き、\n保存先フォルダに保存します\n\n処理対象: {same_size_count}枚"
            )

    def update_spin_ranges(self):
        """画像サイズに基づいてスピンボックスの範囲を更新"""
        if self.current_index < 0 or self.current_index >= len(self.image_files):
            return

        current_file = self.image_files[self.current_index]
        if current_file not in self.image_sizes:
            return

        img_width, img_height = self.image_sizes[current_file]

        # シグナルをブロックして無限ループを防ぐ
        self.x_spin.blockSignals(True)
        self.y_spin.blockSignals(True)
        self.width_spin.blockSignals(True)
        self.height_spin.blockSignals(True)

        # 現在の値を取得
        x = self.x_spin.value()
        y = self.y_spin.value()
        width = self.width_spin.value()
        height = self.height_spin.value()

        # X の最大値: 画像幅 - 幅
        x_max = max(0, img_width - width)
        self.x_spin.setRange(0, x_max)
        if x > x_max:
            self.x_spin.setValue(x_max)

        # Y の最大値: 画像高さ - 高さ
        y_max = max(0, img_height - height)
        self.y_spin.setRange(0, y_max)
        if y > y_max:
            self.y_spin.setValue(y_max)

        # 幅の最大値: 画像幅 - X
        width_max = img_width - x
        self.width_spin.setRange(1, width_max)
        if width > width_max:
            self.width_spin.setValue(width_max)

        # 高さの最大値: 画像高さ - Y
        height_max = img_height - y
        self.height_spin.setRange(1, height_max)
        if height > height_max:
            self.height_spin.setValue(height_max)

        # シグナルを再有効化
        self.x_spin.blockSignals(False)
        self.y_spin.blockSignals(False)
        self.width_spin.blockSignals(False)
        self.height_spin.blockSignals(False)

    def on_crop_spin_changed(self):
        """スピンボックスの値が変更されたとき"""
        # まず範囲を更新
        self.update_spin_ranges()

        # 切り抜き矩形を更新
        self.crop_rect = QRect(
            self.x_spin.value(),
            self.y_spin.value(),
            self.width_spin.value(),
            self.height_spin.value()
        )
        self.image_viewer.set_crop_rect(self.crop_rect)
        self.crop_and_save_btn.setEnabled(not self.crop_rect.isEmpty() and len(self.image_files) > 0)

    def on_zoom_changed(self, scale_factor: float):
        """ズーム率変更時の更新"""
        zoom_percent = scale_factor * 100
        self.zoom_info_label.setText(f"ズーム: {zoom_percent:.0f}%")

    def on_aspect_ratio_toggled(self, checked: bool):
        """アスペクト比固定のON/OFF"""
        self.aspect_ratio_combo.setEnabled(checked)
        is_custom = self.aspect_ratio_combo.currentText() == "カスタム"
        self.custom_width_spin.setEnabled(checked and is_custom)
        self.custom_height_spin.setEnabled(checked and is_custom)

        if checked:
            self.on_aspect_ratio_changed()
        else:
            self.image_viewer.set_aspect_ratio(False)

    def on_aspect_ratio_changed(self):
        """アスペクト比プリセットの変更"""
        if not self.aspect_ratio_checkbox.isChecked():
            return

        text = self.aspect_ratio_combo.currentText()
        is_custom = text == "カスタム"

        self.custom_width_spin.setEnabled(is_custom)
        self.custom_height_spin.setEnabled(is_custom)

        # プリセット比率
        ratio_map = {
            "1:1 (正方形)": 1.0,
            "4:3": 4/3,
            "3:2": 3/2,
            "16:9": 16/9,
            "16:10": 16/10,
            "21:9": 21/9,
        }

        if is_custom:
            ratio = self.custom_width_spin.value() / self.custom_height_spin.value()
        else:
            ratio = ratio_map.get(text, 1.0)

        self.image_viewer.set_aspect_ratio(True, ratio)

    def on_custom_ratio_changed(self):
        """カスタム比率の変更"""
        if self.aspect_ratio_checkbox.isChecked() and self.aspect_ratio_combo.currentText() == "カスタム":
            ratio = self.custom_width_spin.value() / self.custom_height_spin.value()
            self.image_viewer.set_aspect_ratio(True, ratio)

    def update_crop_info(self):
        if self.crop_rect.isEmpty():
            self.crop_info_label.setText("切り抜き範囲: 未設定")
            self.x_spin.blockSignals(True)
            self.y_spin.blockSignals(True)
            self.width_spin.blockSignals(True)
            self.height_spin.blockSignals(True)

            self.x_spin.setValue(0)
            self.y_spin.setValue(0)
            self.width_spin.setValue(0)
            self.height_spin.setValue(0)

            self.x_spin.blockSignals(False)
            self.y_spin.blockSignals(False)
            self.width_spin.blockSignals(False)
            self.height_spin.blockSignals(False)
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

            # スピンボックスの範囲も更新
            self.update_spin_ranges()
    
    def crop_and_save_images(self):
        """切り抜きと保存を一度に実行"""
        if self.crop_rect.isEmpty():
            QMessageBox.warning(self, "警告", "切り抜き範囲が設定されていません。")
            return

        if not self.image_files:
            QMessageBox.warning(self, "警告", "画像が読み込まれていません。")
            return

        # 最初に保存先フォルダを選択
        folder = QFileDialog.getExistingDirectory(self, "保存先フォルダを選択")
        if not folder:
            return

        # 現在選択中の画像と同じサイズの画像すべてを対象にする
        current_file = self.image_files[self.current_index]
        current_size = self.image_sizes.get(current_file)
        files_to_crop = [f for f in self.image_files if self.image_sizes.get(f) == current_size]

        progress = QProgressDialog("画像を処理中...", "キャンセル", 0, len(files_to_crop), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        saved_count = 0

        for i, file_path in enumerate(files_to_crop):
            if progress.wasCanceled():
                break

            progress.setValue(i)
            filename = os.path.basename(file_path)
            progress.setLabelText(f"処理中: {filename}")

            image = QImage(file_path)
            if not image.isNull():
                # 絶対座標で切り抜き
                cropped = image.copy(self.crop_rect)

                # 保存処理
                name, ext = os.path.splitext(filename)
                save_path = os.path.join(folder, f"{name}_cropped{ext}")

                counter = 1
                while os.path.exists(save_path):
                    save_path = os.path.join(folder, f"{name}_cropped_{counter}{ext}")
                    counter += 1

                if cropped.save(save_path):
                    saved_count += 1

        progress.setValue(len(files_to_crop))

        if saved_count > 0:
            QMessageBox.information(self, "完了", f"{saved_count}枚の画像を切り抜いて保存しました。")
        elif not progress.wasCanceled():
            QMessageBox.warning(self, "警告", "画像の保存に失敗しました。")
    
    def remove_selected_images(self):
        """選択された画像をリストから削除"""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            row = self.file_list.row(item)
            self.file_list.takeItem(row)

            if file_path in self.image_files:
                self.image_files.remove(file_path)
            if file_path in self.image_sizes:
                del self.image_sizes[file_path]

        # リストが空になったら画像ビューアもクリア
        if not self.image_files:
            self.clear_list()
        # まだ画像があれば最初の画像を選択
        elif self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
            self.on_image_selected(self.file_list.item(0))
        # 選択はそのままで、リストの表示だけ更新
        elif self.current_index >= 0:
            self.update_list_item_styles()
    
    def show_context_menu(self, position):
        """ファイルリストの右クリックメニュー"""
        if not self.file_list.selectedItems():
            return
        
        menu = QMenu(self)
        
        remove_action = menu.addAction("選択した画像を削除")
        remove_action.triggered.connect(self.remove_selected_images)
        
        menu.addSeparator()
        
        clear_action = menu.addAction("すべてクリア")
        clear_action.triggered.connect(self.clear_list)
        
        menu.exec(self.file_list.mapToGlobal(position))
    
    def dragEnterEvent(self, event):
        """ドラッグされたファイルの検証"""
        if event.mimeData().hasUrls():
            # 画像ファイルかチェック
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        event.acceptProposedAction()
                        return
            event.ignore()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """ドロップされたファイルを追加"""
        files = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    files.append(file_path)
        
        if files:
            self.add_image_files(files)
    
    def add_image_files(self, files):
        """画像ファイルをリストに追加（共通処理）"""
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
                    item.setToolTip(f"サイズ: {size[0]}x{size[1]}")

                    self.file_list.addItem(item)
        
        if len(size_groups) > 1:
            sizes_text = "\n".join([f"- {size}: {len(files)}枚" for size, files in size_groups.items()])
            QMessageBox.information(
                self,
                "異なるサイズの画像を検出",
                f"複数の画像サイズが検出されました:\n{sizes_text}\n\n"
                "切り抜き処理は、選択中の画像と同じサイズの画像のみに適用されます。"
            )
        
        if self.current_index == -1 and self.image_files:
            self.file_list.setCurrentRow(0)
            self.on_image_selected(self.file_list.item(0))
        elif self.current_index >= 0:
            # 既に画像が選択されている場合もリストのスタイルを更新
            self.update_list_item_styles()
    


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = BatchImageCropper()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()