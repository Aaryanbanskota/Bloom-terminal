from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPixmap, QPainter, QPainterPath, QColor, QPen, QBrush
from PyQt5.QtCore import Qt, QRectF, QPointF

class AvatarCropper(QWidget):
    """
    A circular avatar cropper that supports:
    - Drag to pan
    - Scroll-wheel / slider zoom
    - Smooth rendering
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(260, 260)
        self._pixmap = None
        self._scale = 1.0
        self._offset = QPointF(0, 0)
        self._drag_start = None
        self._offset_start = None
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)

    def load_pixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        # Fit to widget on load
        pw, ph = pixmap.width(), pixmap.height()
        sw, sh = self.width(), self.height()
        self._scale = max(sw / pw, sh / ph)
        self._offset = QPointF(
            (sw - pw * self._scale) / 2,
            (sh - ph * self._scale) / 2,
        )
        self.update()

    def set_scale(self, value):
        """value: int 10–400 (slider units → actual scale factor)"""
        if self._pixmap is None:
            return
        pw, ph = self._pixmap.width(), self._pixmap.height()
        sw, sh = self.width(), self.height()
        min_scale = max(sw / pw, sh / ph)
        new_scale = min_scale + (value / 100.0) * min_scale
        # Keep centre stable
        cx, cy = sw / 2, sh / 2
        img_cx = (cx - self._offset.x()) / self._scale
        img_cy = (cy - self._offset.y()) / self._scale
        self._scale = new_scale
        self._offset = QPointF(cx - img_cx * self._scale, cy - img_cy * self._scale)
        self._clamp_offset()
        self.update()

    def _clamp_offset(self):
        if self._pixmap is None:
            return
        sw, sh = self.width(), self.height()
        iw = self._pixmap.width() * self._scale
        ih = self._pixmap.height() * self._scale
        x = self._offset.x()
        y = self._offset.y()
        if iw >= sw:
            x = min(x, 0)
            x = max(x, sw - iw)
        else:
            x = (sw - iw) / 2
        if ih >= sh:
            y = min(y, 0)
            y = max(y, sh - ih)
        else:
            y = (sh - ih) / 2
        self._offset = QPointF(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Clip to circle
        path = QPainterPath()
        path.addEllipse(QRectF(2, 2, 256, 256))
        painter.setClipPath(path)

        if self._pixmap:
            x = self._offset.x()
            y = self._offset.y()
            w = self._pixmap.width() * self._scale
            h = self._pixmap.height() * self._scale
            painter.drawPixmap(QRectF(x, y, w, h), self._pixmap,
                               QRectF(self._pixmap.rect()))

        # Draw red border
        painter.setClipping(False)
        painter.setPen(QPen(QColor("#ff5555"), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(2, 2, 256, 256))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._pixmap is not None:
            self.setCursor(Qt.ClosedHandCursor)
            self._drag_start = event.pos()
            self._offset_start = self._offset
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            delta = event.pos() - self._drag_start
            self._offset = self._offset_start + QPointF(delta.x(), delta.y())
            self._clamp_offset()
            self.update()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.OpenHandCursor)
            self._drag_start = None
            self._offset_start = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        # We can handle wheel events if parent sets a slider, but standard QWidget wheel can zoom too
        # Zoom in/out by adjusting scale directly
        if self._pixmap is None:
            return
        numDegrees = event.angleDelta().y() / 8
        numSteps = numDegrees / 15
        # fake a zoom change
        factor = 1.05 if numSteps > 0 else 0.95
        self.zoom_by_factor(factor)
        event.accept()

    def zoom_by_factor(self, factor):
        sw, sh = self.width(), self.height()
        cx, cy = sw / 2, sh / 2
        img_cx = (cx - self._offset.x()) / self._scale
        img_cy = (cy - self._offset.y()) / self._scale
        self._scale *= factor
        # limit scale
        pw, ph = self._pixmap.width(), self._pixmap.height()
        min_scale = max(sw / pw, sh / ph)
        if self._scale < min_scale:
            self._scale = min_scale
        if self._scale > min_scale * 5.0:
            self._scale = min_scale * 5.0
        self._offset = QPointF(cx - img_cx * self._scale, cy - img_cy * self._scale)
        self._clamp_offset()
        self.update()

    def get_cropped_image(self) -> QPixmap:
        """Render the cropped region to a high-quality 256x256 circular image."""
        target = QPixmap(256, 256)
        target.fill(Qt.transparent)
        painter = QPainter(target)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Clip to circle
        path = QPainterPath()
        path.addEllipse(QRectF(0, 0, 256, 256))
        painter.setClipPath(path)

        if self._pixmap:
            # The cropper size is 260x260, border offset by 2px.
            # So coordinate (2,2) in widget corresponds to (0,0) in target.
            x = self._offset.x() - 2
            y = self._offset.y() - 2
            w = self._pixmap.width() * self._scale
            h = self._pixmap.height() * self._scale
            painter.drawPixmap(QRectF(x, y, w, h), self._pixmap, QRectF(self._pixmap.rect()))
        painter.end()
        return target
