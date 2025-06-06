# This file is part of BeeRef.
#
# BeeRef is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BeeRef is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BeeRef.  If not, see <https://www.gnu.org/licenses/>.

"""Classes for items that are added to the scene by the user (images,
text).
"""

from collections import defaultdict
from functools import cached_property
import logging
import os.path

from PyQt6 import QtCore, QtGui, QtWidgets
from PIL import Image
import io
from PyQt6.QtCore import Qt

from beeref import commands
from beeref.config import BeeSettings
from beeref.constants import COLORS
from beeref.selection import SelectableMixin


logger = logging.getLogger(__name__)

item_registry = {}


def register_item(cls):
    item_registry[cls.TYPE] = cls
    return cls


def sort_by_filename(items):
    """Order items by filename.

    Items with a filename (ordered by filename) first, then items
    without a filename but with a save_id follow (ordered by
    save_id), then remaining items in the order that they have
    been inserted into the scene.
    """

    items_by_filename = []
    items_by_save_id = []
    items_remaining = []

    for item in items:
        if getattr(item, 'filename', None):
            items_by_filename.append(item)
        elif getattr(item, 'save_id', None):
            items_by_save_id.append(item)
        else:
            items_remaining.append(item)

    items_by_filename.sort(key=lambda x: x.filename)
    items_by_save_id.sort(key=lambda x: x.save_id)
    return items_by_filename + items_by_save_id + items_remaining


class BeeItemMixin(SelectableMixin):
    """Base for all items added by the user."""

    def set_pos_center(self, pos):
        """Sets the position using the item's center as the origin point."""

        self.setPos(pos - self.center_scene_coords)

    def has_selection_outline(self):
        return self.isSelected()

    def has_selection_handles(self):
        return (self.isSelected()
                and self.scene()
                and self.scene().has_single_selection())

    def selection_action_items(self):
        """The items affected by selection actions like scaling and rotating.
        """
        return [self]

    def on_selected_change(self, value):
        if (value and self.scene()
                and not self.scene().has_selection()
                and not self.scene().active_mode is None):
            self.bring_to_front()

    def update_from_data(self, **kwargs):
        self.save_id = kwargs.get('save_id', self.save_id)
        self.setPos(kwargs.get('x', self.pos().x()),
                    kwargs.get('y', self.pos().y()))
        self.setZValue(kwargs.get('z', self.zValue()))
        self.setScale(kwargs.get('scale', self.scale()))
        self.setRotation(kwargs.get('rotation', self.rotation()))
        if kwargs.get('flip', 1) != self.flip():
            self.do_flip()


@register_item
class BeePixmapItem(BeeItemMixin, QtWidgets.QGraphicsPixmapItem):
    """Class for images added by the user."""

    TYPE = 'pixmap'
    CROP_HANDLE_SIZE = 15

    def __init__(self, image, filename=None, **kwargs):
        super().__init__(QtGui.QPixmap.fromImage(image))
        self.save_id = None
        self.filename = filename
        self.reset_crop()
        logger.debug(f'Initialized {self}')
        self.is_image = True
        self.crop_mode = False
        self.init_selectable()
        self.settings = BeeSettings()
        self.grayscale = False

    @classmethod
    def create_from_data(self, **kwargs):
        item = kwargs.pop('item')
        data = kwargs.pop('data', {})
        item.filename = item.filename or data.get('filename')
        if 'crop' in data:
            item.crop = QtCore.QRectF(*data['crop'])
        item.setOpacity(data.get('opacity', 1))
        item.grayscale = data.get('grayscale', False)
        return item

    def __str__(self):
        size = self.pixmap().size()
        return (f'Image "{self.filename}" {size.width()} x {size.height()}')

    @property
    def crop(self):
        return self._crop

    @crop.setter
    def crop(self, value):
        logger.debug(f'Setting crop for {self} to {value}')
        self.prepareGeometryChange()
        self._crop = value
        self.update()

    @property
    def grayscale(self):
        return self._grayscale

    @grayscale.setter
    def grayscale(self, value):
        logger.debug('Setting grayscale for {self} to {value}')
        self._grayscale = value
        if value is True:
            # Using the grayscale image format to convert to grayscale
            # loses an image's tranparency. So the straightworward
            # following method gives us an ugly black replacement:
            # img = img.convertToFormat(QtGui.QImage.Format.Format_Grayscale8)

            # Instead, we will fill the background with the current
            # canvas colour, so the issue is only visible if the image
            # overlaps other images. The way we do it here only works
            # as long as the canvas colour is itself grayscale,
            # though.
            img = QtGui.QImage(
                self.pixmap().size(), QtGui.QImage.Format.Format_Grayscale8)
            img.fill(QtGui.QColor(*COLORS['Scene:Canvas']))
            painter = QtGui.QPainter(img)
            painter.drawPixmap(0, 0, self.pixmap())
            painter.end()
            self._grayscale_pixmap = QtGui.QPixmap.fromImage(img)

            # Alternative methods that have their own issues:
            #
            # 1. Use setAlphaChannel of the resulting grayscale
            # image. How do we get the original alpha channel? Using
            # the whole original image also takes color values into
            # account, not just their alpha values.
            #
            # 2. QtWidgets.QGraphicsColorizeEffect() with black colour
            # on the GraphicsItem. This applys to everything the paint
            # method does, so the selection outline/handles will also
            # be gray. setGraphicsEffect is only available on some
            # widgets, so we can't apply it selectively.
            #
            # 3. Going through every pixel and doing it manually — bad
            # performance.
        else:
            self._grayscale_pixmap = None

        self.update()

    def sample_color_at(self, pos):
        ipos = self.mapFromScene(pos)
        if self.grayscale:
            pm = self._grayscale_pixmap
        else:
            pm = self.pixmap()
        img = pm.toImage()

        color = img.pixelColor(int(ipos.x()), int(ipos.y()))
        if color.alpha():
            return color

    def bounding_rect_unselected(self):
        if self.crop_mode:
            return QtWidgets.QGraphicsPixmapItem.boundingRect(self)
        else:
            return self.crop

    def get_extra_save_data(self):
        return {'filename': self.filename,
                'opacity': self.opacity(),
                'grayscale': self.grayscale,
                'crop': [self.crop.topLeft().x(),
                         self.crop.topLeft().y(),
                         self.crop.width(),
                         self.crop.height()]}

    def get_filename_for_export(self, imgformat, save_id_default=None):
        save_id = self.save_id or save_id_default
        assert save_id is not None

        if self.filename:
            basename = os.path.splitext(os.path.basename(self.filename))[0]
            return f'{save_id:04}-{basename}.{imgformat}'
        else:
            return f'{save_id:04}.{imgformat}'

    def get_imgformat(self, img):
        """Determines the format for storing this image."""

        formt = self.settings.valueOrDefault('Items/image_storage_format')

        if formt == 'best':
            # Images with alpha channel and small images are stored as png
            if (img.hasAlphaChannel()
                    or (img.height() < 500 and img.width() < 500)):
                formt = 'png'
            else:
                formt = 'jpg'

        logger.debug(f'Found format {formt} for {self}')
        return formt

    def pixmap_to_bytes(self, apply_grayscale=False, apply_crop=False):
        """Convert the pixmap data to PNG bytestring."""
        barray = QtCore.QByteArray()
        buffer = QtCore.QBuffer(barray)
        buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
        if apply_grayscale and self.grayscale:
            pm = self._grayscale_pixmap
        else:
            pm = self.pixmap()

        if apply_crop:
            pm = pm.copy(self.crop.toRect())

        img = pm.toImage()
        imgformat = self.get_imgformat(img)
        img.save(buffer, imgformat.upper(), quality=90)
        return (barray.data(), imgformat)

    def setPixmap(self, pixmap):
        super().setPixmap(pixmap)
        self.reset_crop()

    def pixmap_from_bytes(self, data):
        """Set image pimap from a bytestring."""
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(data)
        self.setPixmap(pixmap)

    def create_copy(self):
        item = BeePixmapItem(QtGui.QImage(), self.filename)
        item.setPixmap(self.pixmap())
        item.setPos(self.pos())
        item.setZValue(self.zValue())
        item.setScale(self.scale())
        item.setRotation(self.rotation())
        item.setOpacity(self.opacity())
        item.grayscale = self.grayscale
        if self.flip() == -1:
            item.do_flip()
        item.crop = self.crop
        return item

    @cached_property
    def color_gamut(self):
        logger.debug(f'Calculating color gamut for {self}')
        gamut = defaultdict(int)
        img = self.pixmap().toImage()
        # Don't evaluate every pixel for larger images:
        step = max(1, int(max(img.width(), img.height()) / 1000))
        logger.debug(f'Considering every {step}. row/column')

        # Not actually faster than solution below :(
        # ptr = img.bits()
        # size = img.sizeInBytes()
        # pixelsize = int(img.sizeInBytes() / img.width() / img.height())
        # ptr.setsize(size)
        # for pixel in batched(ptr, n=pixelsize):
        #     r, g, b, alpha = tuple(map(ord, pixel))
        #     if 5 < alpha and 5 < r < 250 and 5 < g < 250 and 5 < b < 250:
        #         # Only consider pixels that aren't close to
        #         # transparent, white or black
        #         rgb = QtGui.QColor(r, g, b)
        #         gamut[rgb.hue(), rgb.saturation()] += 1

        for i in range(0, img.width(), step):
            for j in range(0, img.height(), step):
                rgb = img.pixelColor(i, j)
                rgbtuple = (rgb.red(), rgb.blue(), rgb.green())
                if (5 < rgb.alpha()
                        and min(rgbtuple) < 250 and max(rgbtuple) > 5):
                    # Only consider pixels that aren't close to
                    # transparent, white or black
                    gamut[rgb.hue(), rgb.saturation()] += 1

        logger.debug(f'Got {len(gamut)} color gamut values')
        return gamut

    def copy_to_clipboard(self, clipboard):
        clipboard.setPixmap(self.pixmap())

    def reset_crop(self):
        self.crop = QtCore.QRectF(
            0, 0, self.pixmap().size().width(), self.pixmap().size().height())

    @property
    def crop_handle_size(self):
        return self.fixed_length_for_viewport(self.CROP_HANDLE_SIZE)

    def crop_handle_topleft(self):
        topleft = self.crop_temp.topLeft()
        return QtCore.QRectF(
            topleft.x(),
            topleft.y(),
            self.crop_handle_size,
            self.crop_handle_size)

    def crop_handle_bottomleft(self):
        bottomleft = self.crop_temp.bottomLeft()
        return QtCore.QRectF(
            bottomleft.x(),
            bottomleft.y() - self.crop_handle_size,
            self.crop_handle_size,
            self.crop_handle_size)

    def crop_handle_bottomright(self):
        bottomright = self.crop_temp.bottomRight()
        return QtCore.QRectF(
            bottomright.x() - self.crop_handle_size,
            bottomright.y() - self.crop_handle_size,
            self.crop_handle_size,
            self.crop_handle_size)

    def crop_handle_topright(self):
        topright = self.crop_temp.topRight()
        return QtCore.QRectF(
            topright.x() - self.crop_handle_size,
            topright.y(),
            self.crop_handle_size,
            self.crop_handle_size)

    def crop_handles(self):
        return (self.crop_handle_topleft,
                self.crop_handle_bottomleft,
                self.crop_handle_bottomright,
                self.crop_handle_topright)

    def crop_edge_top(self):
        topleft = self.crop_temp.topLeft()
        return QtCore.QRectF(
            topleft.x() + self.crop_handle_size,
            topleft.y(),
            self.crop_temp.width() - 2 * self.crop_handle_size,
            self.crop_handle_size)

    def crop_edge_left(self):
        topleft = self.crop_temp.topLeft()
        return QtCore.QRectF(
            topleft.x(),
            topleft.y() + self.crop_handle_size,
            self.crop_handle_size,
            self.crop_temp.height() - 2 * self.crop_handle_size)

    def crop_edge_bottom(self):
        bottomleft = self.crop_temp.bottomLeft()
        return QtCore.QRectF(
            bottomleft.x() + self.crop_handle_size,
            bottomleft.y() - self.crop_handle_size,
            self.crop_temp.width() - 2 * self.crop_handle_size,
            self.crop_handle_size)

    def crop_edge_right(self):
        topright = self.crop_temp.topRight()
        return QtCore.QRectF(
            topright.x() - self.crop_handle_size,
            topright.y() + self.crop_handle_size,
            self.crop_handle_size,
            self.crop_temp.height() - 2 * self.crop_handle_size)

    def crop_edges(self):
        return (self.crop_edge_top,
                self.crop_edge_left,
                self.crop_edge_bottom,
                self.crop_edge_right)

    def get_crop_handle_cursor(self, handle):
        """Gets the crop cursor for the given handle."""

        is_topleft_or_bottomright = handle in (
            self.crop_handle_topleft, self.crop_handle_bottomright)
        return self.get_diag_cursor(is_topleft_or_bottomright)

    def get_crop_edge_cursor(self, edge):
        """Gets the crop edge cursor for the given edge."""

        top_or_bottom = edge in (
            self.crop_edge_top, self.crop_edge_bottom)
        sideways = (45 < self.rotation() < 135
                    or 225 < self.rotation() < 315)

        if top_or_bottom is sideways:
            return Qt.CursorShape.SizeHorCursor
        else:
            return Qt.CursorShape.SizeVerCursor

    def draw_crop_rect(self, painter, rect):
        """Paint a dotted rectangle for the cropping UI."""
        pen = QtGui.QPen(QtGui.QColor(255, 255, 255))
        pen.setWidth(2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawRect(rect)
        pen.setColor(QtGui.QColor(0, 0, 0))
        pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)
        painter.drawRect(rect)

    def paint(self, painter, option, widget):
        if abs(painter.combinedTransform().m11()) < 2:
            # We want image smoothing, but only for images where we
            # are not zoomed in a lot. This is to ensure that for
            # example icons and pixel sprites can be viewed correctly.
            painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform)

        if self.crop_mode:
            self.paint_debug(painter, option, widget)

            # Darken image outside of cropped area
            painter.drawPixmap(0, 0, self.pixmap())
            path = QtWidgets.QGraphicsPixmapItem.shape(self)
            path.addRect(self.crop_temp)
            color = QtGui.QColor(0, 0, 0)
            color.setAlpha(100)
            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)
            painter.setBrush(QtGui.QBrush())

            for handle in self.crop_handles():
                self.draw_crop_rect(painter, handle())
            self.draw_crop_rect(painter, self.crop_temp)
        else:
            pm = self._grayscale_pixmap if self.grayscale else self.pixmap()
            painter.drawPixmap(self.crop, pm, self.crop)
            self.paint_selectable(painter, option, widget)

    def enter_crop_mode(self):
        logger.debug(f'Entering crop mode on {self}')
        self.prepareGeometryChange()
        self.crop_mode = True
        self.crop_temp = QtCore.QRectF(self.crop)
        self.crop_mode_move = None
        self.crop_mode_event_start = None
        self.grabKeyboard()
        self.update()
        self.scene().crop_item = self

    def exit_crop_mode(self, confirm):
        logger.debug(f'Exiting crop mode with {confirm} on {self}')
        if confirm and self.crop != self.crop_temp:
            self.scene().undo_stack.push(
                commands.CropItem(self, self.crop_temp))
        self.prepareGeometryChange()
        self.crop_mode = False
        self.crop_temp = None
        self.crop_mode_move = None
        self.crop_mode_event_start = None
        self.ungrabKeyboard()
        self.update()
        self.scene().crop_item = None

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.exit_crop_mode(confirm=True)
        elif event.key() == Qt.Key.Key_Escape:
            self.exit_crop_mode(confirm=False)
        else:
            super().keyPressEvent(event)

    def hoverMoveEvent(self, event):
        if not self.crop_mode:
            return super().hoverMoveEvent(event)

        for handle in self.crop_handles():
            if handle().contains(event.pos()):
                self.set_cursor(self.get_crop_handle_cursor(handle))
                return
        for edge in self.crop_edges():
            if edge().contains(event.pos()):
                self.set_cursor(self.get_crop_edge_cursor(edge))
                return
        self.unset_cursor()

    def mousePressEvent(self, event):
        if not self.crop_mode:
            return super().mousePressEvent(event)

        event.accept()
        for handle in self.crop_handles():
            # Click into a handle?
            if handle().contains(event.pos()):
                self.crop_mode_event_start = event.pos()
                self.crop_mode_move = handle
                return
        for edge in self.crop_edges():
            # Click into an edge handle?
            if edge().contains(event.pos()):
                self.crop_mode_event_start = event.pos()
                self.crop_mode_move = edge
                return
        # Click not in handle, end cropping mode:
        self.exit_crop_mode(
            confirm=self.crop_temp.contains(event.pos()))

    def ensure_point_within_crop_bounds(self, point, handle):
        """Returns the point, or the nearest point within the pixmap."""

        if handle == self.crop_handle_topleft:
            topleft = QtCore.QPointF(0, 0)
            bottomright = self.crop_temp.bottomRight()
        if handle == self.crop_handle_bottomleft:
            topleft = QtCore.QPointF(0, self.crop_temp.top())
            bottomright = QtCore.QPointF(
                self.crop_temp.right(), self.pixmap().size().height())
        if handle == self.crop_handle_bottomright:
            topleft = self.crop_temp.topLeft()
            bottomright = QtCore.QPointF(
                self.pixmap().size().width(), self.pixmap().size().height())
        if handle == self.crop_handle_topright:
            topleft = QtCore.QPointF(self.crop_temp.left(), 0)
            bottomright = QtCore.QPointF(
                self.pixmap().size().width(), self.crop_temp.bottom())
        if handle == self.crop_edge_top:
            topleft = QtCore.QPointF(0, 0)
            bottomright = QtCore.QPointF(
                self.pixmap().size().width(), self.crop_temp.bottom())
        if handle == self.crop_edge_bottom:
            topleft = QtCore.QPointF(0, self.crop_temp.top())
            bottomright = QtCore.QPointF(
                self.pixmap().size().width(), self.pixmap().size().height())
        if handle == self.crop_edge_left:
            topleft = QtCore.QPointF(0, 0)
            bottomright = QtCore.QPointF(
                self.crop_temp.right(), self.pixmap().size().height())
        if handle == self.crop_edge_right:
            topleft = QtCore.QPointF(self.crop_temp.left(), 0)
            bottomright = QtCore.QPointF(
                self.pixmap().size().width(), self.pixmap().size().height())

        point.setX(min(bottomright.x(), max(topleft.x(), point.x())))
        point.setY(min(bottomright.y(), max(topleft.y(), point.y())))

        return point

    def mouseMoveEvent(self, event):
        if self.crop_mode and self.crop_mode_event_start:
            diff = event.pos() - self.crop_mode_event_start
            if self.crop_mode_move == self.crop_handle_topleft:
                new = self.ensure_point_within_crop_bounds(
                    self.crop_temp.topLeft() + diff, self.crop_mode_move)
                self.crop_temp.setTopLeft(new)
            if self.crop_mode_move == self.crop_handle_bottomleft:
                new = self.ensure_point_within_crop_bounds(
                    self.crop_temp.bottomLeft() + diff, self.crop_mode_move)
                self.crop_temp.setBottomLeft(new)
            if self.crop_mode_move == self.crop_handle_bottomright:
                new = self.ensure_point_within_crop_bounds(
                    self.crop_temp.bottomRight() + diff, self.crop_mode_move)
                self.crop_temp.setBottomRight(new)
            if self.crop_mode_move == self.crop_handle_topright:
                new = self.ensure_point_within_crop_bounds(
                    self.crop_temp.topRight() + diff, self.crop_mode_move)
                self.crop_temp.setTopRight(new)
            if self.crop_mode_move == self.crop_edge_top:
                new = self.ensure_point_within_crop_bounds(
                    self.crop_temp.topLeft() + diff, self.crop_mode_move)
                self.crop_temp.setTop(new.y())
            if self.crop_mode_move == self.crop_edge_left:
                new = self.ensure_point_within_crop_bounds(
                    self.crop_temp.topLeft() + diff, self.crop_mode_move)
                self.crop_temp.setLeft(new.x())
            if self.crop_mode_move == self.crop_edge_bottom:
                new = self.ensure_point_within_crop_bounds(
                    self.crop_temp.bottomLeft() + diff, self.crop_mode_move)
                self.crop_temp.setBottom(new.y())
            if self.crop_mode_move == self.crop_edge_right:
                new = self.ensure_point_within_crop_bounds(
                    self.crop_temp.topRight() + diff, self.crop_mode_move)
                self.crop_temp.setRight(new.x())
            self.update()
            self.crop_mode_event_start = event.pos()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.crop_mode:
            self.crop_mode_move = None
            self.crop_mode_event_start = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)


@register_item
class BeeTextItem(BeeItemMixin, QtWidgets.QGraphicsTextItem):
    """Class for text added by the user."""

    TYPE = 'text'

    def __init__(self, text=None, **kwargs):
        super().__init__(text or "Text")
        self.save_id = None
        logger.debug(f'Initialized {self}')
        self.is_image = False
        self.init_selectable()
        self.is_editable = True
        self.edit_mode = False
        self.setDefaultTextColor(QtGui.QColor(*COLORS['Scene:Text']))

    @classmethod
    def create_from_data(cls, **kwargs):
        data = kwargs.get('data', {})
        item = cls(**data)
        return item

    def __str__(self):
        txt = self.toPlainText()[:40]
        return (f'Text "{txt}"')

    def get_extra_save_data(self):
        return {'text': self.toPlainText()}

    def contains(self, point):
        return self.boundingRect().contains(point)

    def paint(self, painter, option, widget):
        painter.setPen(Qt.PenStyle.NoPen)
        color = QtGui.QColor(0, 0, 0)
        color.setAlpha(40)
        brush = QtGui.QBrush(color)
        painter.setBrush(brush)
        painter.drawRect(QtWidgets.QGraphicsTextItem.boundingRect(self))
        option.state = QtWidgets.QStyle.StateFlag.State_Enabled
        super().paint(painter, option, widget)
        self.paint_selectable(painter, option, widget)

    def create_copy(self):
        item = BeeTextItem(self.toPlainText())
        item.setPos(self.pos())
        item.setZValue(self.zValue())
        item.setScale(self.scale())
        item.setRotation(self.rotation())
        if self.flip() == -1:
            item.do_flip()
        return item

    def enter_edit_mode(self):
        logger.debug(f'Entering edit mode on {self}')
        self.edit_mode = True
        self.old_text = self.toPlainText()
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextEditorInteraction)
        self.scene().edit_item = self

    def exit_edit_mode(self, commit=True):
        logger.debug(f'Exiting edit mode on {self}')
        self.edit_mode = False
        # reset selection:
        self.setTextCursor(QtGui.QTextCursor(self.document()))
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.scene().edit_item = None
        if commit:
            self.scene().undo_stack.push(
                commands.ChangeText(self, self.toPlainText(), self.old_text))
            if not self.toPlainText().strip():
                logger.debug('Removing empty text item')
                self.scene().undo_stack.push(
                    commands.DeleteItems(self.scene(), [self]))
        else:
            self.setPlainText(self.old_text)

    def has_selection_handles(self):
        return super().has_selection_handles() and not self.edit_mode

    def keyPressEvent(self, event):
        if (event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return)
                and event.modifiers() == Qt.KeyboardModifier.NoModifier):
            self.exit_edit_mode()
            event.accept()
            return
        if (event.key() == Qt.Key.Key_Escape
                and event.modifiers() == Qt.KeyboardModifier.NoModifier):
            self.exit_edit_mode(commit=False)
            event.accept()
            return
        super().keyPressEvent(event)

    def copy_to_clipboard(self, clipboard):
        clipboard.setText(self.toPlainText())


@register_item
class BeeErrorItem(BeeItemMixin, QtWidgets.QGraphicsTextItem):
    """Class for displaying error messages when an item can't be loaded
    from a bee file.

    This item will be displayed instead of the original item. It won't
    save to bee files. The original item will be preserved in the bee
    file, unless this item gets deleted by the user, or a new bee file
    is saved.
    """

    TYPE = 'error'

    def __init__(self, text=None, **kwargs):
        super().__init__(text or "Text")
        self.original_save_id = None
        logger.debug(f'Initialized {self}')
        self.is_image = False
        self.init_selectable()
        self.is_editable = False
        self.setDefaultTextColor(QtGui.QColor(*COLORS['Scene:Text']))

    @classmethod
    def create_from_data(cls, **kwargs):
        data = kwargs.get('data', {})
        item = cls(**data)
        return item

    def __str__(self):
        txt = self.toPlainText()[:40]
        return (f'Error "{txt}"')

    def contains(self, point):
        return self.boundingRect().contains(point)

    def paint(self, painter, option, widget):
        painter.setPen(Qt.PenStyle.NoPen)
        color = QtGui.QColor(200, 0, 0)
        brush = QtGui.QBrush(color)
        painter.setBrush(brush)
        painter.drawRect(QtWidgets.QGraphicsTextItem.boundingRect(self))
        option.state = QtWidgets.QStyle.StateFlag.State_Enabled
        super().paint(painter, option, widget)
        self.paint_selectable(painter, option, widget)

    def update_from_data(self, **kwargs):
        self.original_save_id = kwargs.get('save_id', self.original_save_id)
        self.setPos(kwargs.get('x', self.pos().x()),
                    kwargs.get('y', self.pos().y()))
        self.setZValue(kwargs.get('z', self.zValue()))
        self.setScale(kwargs.get('scale', self.scale()))
        self.setRotation(kwargs.get('rotation', self.rotation()))

    def create_copy(self):
        item = BeeErrorItem(self.toPlainText())
        item.setPos(self.pos())
        item.setZValue(self.zValue())
        item.setScale(self.scale())
        item.setRotation(self.rotation())
        return item

    def flip(self, *args, **kwargs):
        """Returns the flip value (1 or -1)"""
        # Never display error messages flipped
        return 1

    def do_flip(self, *args, **kwargs):
        """Flips the item."""
        # Never flip error messages
        pass

    def copy_to_clipboard(self, clipboard):
        clipboard.setText(self.toPlainText())


@register_item
class BeeAnimatedDataItem(BeeItemMixin, QtWidgets.QGraphicsObject):
    """元データ保持＋動的フレーム取得アプローチのアニメーション画像アイテム"""
    
    TYPE = 'animated_data'
    CROP_HANDLE_SIZE = 15
    
    def __init__(self, animation_file_data, filename=None, **kwargs):
        """
        Args:
            animation_file_data (bytes): 元のアニメーションファイルのバイナリデータ
            filename (str): ファイル名
        """
        super().__init__()
        self.save_id = None
        self.filename = filename
        self.is_image = True
        self.crop_mode = False
        self.settings = BeeSettings()
        
        # 元データを保持
        self._animation_data = animation_file_data
        self._image_reader = None
        self._frame_cache = {}  # フレーム番号 -> QPixmap のキャッシュ
        self._frame_count = 0
        self._current_frame = 0
        self._delays = []
        
        # QImageReaderを初期化してフレーム情報を取得
        self._initialize_reader()
        
        # アニメーション制御
        self._animation_started = False
        self.frame_timer = 0
        
        # その他の初期化
        self.reset_crop()
        self._grayscale = False
        self.init_selectable()
        
        logger.debug(f'Initialized {self} with {self._frame_count} frames from {len(animation_file_data)} bytes')
    
    def _initialize_reader(self):
        """PIL を使って全フレームを初期化時に読み込む"""
        try:
            from PIL import Image
            import io
            import tempfile
            
            logger.debug(f'Initializing animation with PIL for {self.filename}')
            
            # 一時ファイルとして保存してPILで読み込み
            with tempfile.NamedTemporaryFile(delete=True, suffix='.gif') as tmp_file:
                tmp_file.write(self._animation_data)
                tmp_file.flush()
                
                # PILでアニメーションを開く
                with Image.open(tmp_file.name) as pil_img:
                    self._frame_count = getattr(pil_img, 'n_frames', 1)
                    self._delays = []
                    self._pil_frames = []  # PILフレームを保持
                    
                    logger.debug(f'PIL detected {self._frame_count} frames')
                    
                    # 全フレームを読み込み
                    for frame_idx in range(self._frame_count):
                        pil_img.seek(frame_idx)
                        
                        # フレームの遅延時間を取得
                        delay = pil_img.info.get('duration', 100)  # ミリ秒
                        if delay <= 0:
                            delay = 100
                        self._delays.append(delay)
                        
                        # PILフレームをRGBAに変換してコピー
                        frame_copy = pil_img.convert('RGBA').copy()
                        self._pil_frames.append(frame_copy)
                        
                        # 最初のフレームはすぐにQPixmapに変換してキャッシュ
                        if frame_idx == 0:
                            qimage = self._pil_to_qimage(frame_copy)
                            if not qimage.isNull():
                                self._frame_cache[0] = QtGui.QPixmap.fromImage(qimage)
                                logger.debug(f'Cached initial frame: size={qimage.size()}')
            
            logger.debug(f'Successfully initialized PIL animation: {self._frame_count} frames, delays: {self._delays[:5]}...')
            
            # 従来のQImageReader関連の変数を設定（互換性のため）
            self._buffer = None
            self._image_reader = None
            
        except Exception as e:
            logger.error(f'Failed to initialize PIL animation for {self.filename}: {e}', exc_info=True)
            # フォールバック
            self._frame_count = 1
            self._delays = [100]
            self._pil_frames = []
            # エラー時は空のPixmapを作成
            self._frame_cache[0] = QtGui.QPixmap(100, 100)
            self._buffer = None
            self._image_reader = None
    
    def _pil_to_qimage(self, pil_image):
        """PIL ImageをQImageに変換"""
        try:
            import io
            # PILイメージをPNGバイトに変換
            buffer = io.BytesIO()
            pil_image.save(buffer, format='PNG')
            buffer.seek(0)
            
            # QImageとして読み込み
            qimage = QtGui.QImage()
            qimage.loadFromData(buffer.getvalue())
            return qimage
        except Exception as e:
            logger.error(f'Failed to convert PIL image to QImage: {e}')
            return QtGui.QImage()
    
    def get_frame_pixmap(self, frame_index):
        """指定されたフレームのQPixmapを取得（PILベース、キャッシュ機能付き）"""
        logger.debug(f'get_frame_pixmap called: frame_index={frame_index}, current_frame={self._current_frame}, frame_count={self._frame_count}')
        
        if frame_index < 0 or frame_index >= self._frame_count:
            logger.warning(f'Invalid frame_index {frame_index}, resetting to 0 (frame_count={self._frame_count})')
            frame_index = 0
        
        # キャッシュにあるかチェック
        if frame_index in self._frame_cache:
            pixmap = self._frame_cache[frame_index]
            logger.debug(f'Frame {frame_index} found in cache, pixmap null={pixmap.isNull()}, size={pixmap.size()}')
            return pixmap
        
        logger.debug(f'Frame {frame_index} not in cache, loading from PIL frames (cache keys: {list(self._frame_cache.keys())})')
        
        # キャッシュにない場合はPILフレームから生成
        try:
            if not hasattr(self, '_pil_frames') or not self._pil_frames:
                logger.error(f'No PIL frames available for {self.filename}')
                return QtGui.QPixmap()
            
            if frame_index >= len(self._pil_frames):
                logger.error(f'Frame index {frame_index} out of range for PIL frames (count: {len(self._pil_frames)})')
                return QtGui.QPixmap()
            
            # PILフレームからQImageに変換
            pil_frame = self._pil_frames[frame_index]
            logger.debug(f'Converting PIL frame {frame_index} to QImage, PIL size: {pil_frame.size}')
            
            qimage = self._pil_to_qimage(pil_frame)
            if qimage.isNull():
                logger.error(f'Failed to convert PIL frame {frame_index} to QImage for {self.filename}')
                return QtGui.QPixmap()
            
            logger.debug(f'Successfully converted frame {frame_index}, QImage size: {qimage.size()}')
            pixmap = QtGui.QPixmap.fromImage(qimage)
            
            # キャッシュサイズ制限（メモリ効率のため最大10フレームまで）
            if len(self._frame_cache) >= 10:
                # 現在表示中のフレームを削除しないよう改善
                cache_keys = [k for k in self._frame_cache.keys() if k != self._current_frame]
                if cache_keys:
                    oldest_key = min(cache_keys)
                    logger.debug(f'Cache full, removing oldest non-current frame {oldest_key} (current: {self._current_frame})')
                    del self._frame_cache[oldest_key]
                else:
                    # 現在のフレームしかない場合は最古のキャッシュを削除
                    oldest_key = min(self._frame_cache.keys())
                    logger.debug(f'Cache full, removing oldest frame {oldest_key} (current: {self._current_frame})')
                    del self._frame_cache[oldest_key]
            
            self._frame_cache[frame_index] = pixmap
            logger.debug(f'Cached frame {frame_index} for {self.filename} (cache size: {len(self._frame_cache)}, keys: {list(self._frame_cache.keys())})')
            return pixmap
            
        except Exception as e:
            logger.error(f'Exception in get_frame_pixmap for frame {frame_index} of {self.filename}: {e}', exc_info=True)
        
        # エラー時は空のPixmapを返す
        logger.error(f'Returning empty pixmap for frame {frame_index} of {self.filename}')
        return QtGui.QPixmap()
    
    @classmethod
    def create_from_data(cls, **kwargs):
        item = kwargs.pop('item')
        data = kwargs.pop('data', {})
        # filenameの更新を確実に行う
        if 'filename' in data:
            item.filename = data['filename']
        if 'crop' in data:
            item.crop = QtCore.QRectF(*data['crop'])
        item.setOpacity(data.get('opacity', 1))
        item.grayscale = data.get('grayscale', False)
        item._current_frame = data.get('current_frame', 0)
        return item
    
    def __str__(self):
        size = self.pixmap().size()
        frame_info = f' ({self._frame_count} frames)' if self._frame_count > 1 else ''
        return (f'Animated Data Item "{self.filename}" {size.width()} x {size.height()}{frame_info}')
    
    def pixmap(self):
        """現在のフレームのPixmapを返す"""
        pixmap = self.get_frame_pixmap(self._current_frame)
        logger.debug(f'pixmap() called for frame {self._current_frame}: null={pixmap.isNull()}, size={pixmap.size()}')
        return pixmap
    
    @property
    def frames(self):
        """互換性のためのプロパティ（全フレーム数を返すリスト的なオブジェクト）"""
        class FrameAccessor:
            def __init__(self, parent):
                self.parent = parent
            
            def __len__(self):
                return self.parent._frame_count
            
            def __getitem__(self, index):
                return self.parent.get_frame_pixmap(index)
        
        return FrameAccessor(self)
    
    @property
    def delays(self):
        """フレーム遅延時間のリスト"""
        return self._delays.copy()
    
    @property
    def current_frame(self):
        return self._current_frame
    
    @current_frame.setter
    def current_frame(self, value):
        if 0 <= value < self._frame_count:
            self._current_frame = value
    
    def start_animation(self):
        """アニメーション開始"""
        logger.debug(f'start_animation called for {self}, frames: {self._frame_count}, scene: {self.scene()}, started: {self._animation_started}')
        if self._frame_count > 1 and self.scene() and not self._animation_started:
            self._animation_started = True
            logger.debug(f'Started animation for {self}')
    
    def stop_animation(self):
        """アニメーション停止"""
        self._animation_started = False
        logger.debug(f'Stopped animation for {self}')
    
    def update_animation(self, elapsed_ms):
        """シーンのタイマーから呼ばれるアニメーション更新"""
        logger.debug(f'update_animation called: elapsed_ms={elapsed_ms}, started={self._animation_started}, frame_count={self._frame_count}, delays={len(self._delays)}')
        
        if not self._animation_started:
            logger.debug(f'Animation not started for {self.filename}')
            return False
            
        if self._frame_count <= 1:
            logger.debug(f'Single frame animation for {self.filename}')
            return False
            
        if not self._delays:
            logger.warning(f'No delays configured for {self.filename}')
            return False
        
        old_frame = self._current_frame
        self.frame_timer += elapsed_ms
        frames_advanced = 0
        
        # 現在のフレームの遅延時間を取得
        delay_per_frame = self._delays[self._current_frame] if self._current_frame < len(self._delays) else 100
        logger.debug(f'Current frame {self._current_frame}, delay={delay_per_frame}ms, frame_timer={self.frame_timer:.2f}ms')
        
        if delay_per_frame <= 0:
            logger.warning(f"Delay per frame is {delay_per_frame} for {self}. Animation may not work correctly.")
            return False
        
        while self.frame_timer >= delay_per_frame and self._frame_count > 0:
            self.frame_timer -= delay_per_frame
            old_current_frame = self._current_frame
            self._current_frame = (self._current_frame + 1) % self._frame_count
            frames_advanced += 1
            
            logger.debug(f'Frame advanced from {old_current_frame} to {self._current_frame} (loop completed: {self._current_frame == 0})')
            
            # ループ完了時の特別なログ
            # if self._current_frame == 0 and old_current_frame == self._frame_count - 1:
            #     logger.info(f'*** LOOP COMPLETED *** for {self.filename} from frame {old_current_frame} to {self._current_frame}')
            
            # 次のフレームの遅延時間を取得
            delay_per_frame = self._delays[self._current_frame] if self._current_frame < len(self._delays) else 100
        
        if frames_advanced > 0:
            logger.debug(f'Advanced {frames_advanced} frame(s) from {old_frame} to {self._current_frame} for {self} (timer: {self.frame_timer:.2f}ms left)')
            
            # 重要：フレーム切り替え時は必ず更新を要求
            self.update()
            logger.debug(f'Called update() after frame advance to {self._current_frame}')
            return True
        
        return False
    
    def bounding_rect_unselected(self):
        pm = self.pixmap()
        if self.crop_mode:
            rect = QtCore.QRectF(pm.rect())
            logger.debug(f'bounding_rect_unselected (crop_mode): frame={self._current_frame}, pixmap_null={pm.isNull()}, rect={rect}')
            return rect
        else:
            logger.debug(f'bounding_rect_unselected (normal): frame={self._current_frame}, pixmap_null={pm.isNull()}, crop={self.crop}')
            return self.crop
    
    @property
    def crop(self):
        return self._crop
    
    @crop.setter
    def crop(self, value):
        logger.debug(f'Setting crop for {self} to {value}')
        self.prepareGeometryChange()
        self._crop = value
        self.update()
    
    @property
    def grayscale(self):
        return self._grayscale
    
    @grayscale.setter
    def grayscale(self, value):
        logger.debug(f'Setting grayscale for {self} to {value}')
        self._grayscale = value
        # グレースケール変更時はキャッシュをクリア
        self._frame_cache.clear()
        self.update()
    
    def reset_crop(self):
        """クロップ領域をリセット"""
        pm = self.pixmap()
        if not pm.isNull():
            size = pm.size()
            self.crop = QtCore.QRectF(0, 0, size.width(), size.height())
    
    def paint(self, painter, option, widget):
        """描画メソッド"""
        logger.debug(f'paint() called for frame {self._current_frame} of {self.filename}')
        
        if abs(painter.combinedTransform().m11()) < 2:
            painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform)
        
        pm = self.pixmap()
        if pm.isNull():
            logger.error(f'paint(): pixmap is null for frame {self._current_frame} of {self.filename} - ITEM WILL NOT BE VISIBLE')
            return
        
        logger.debug(f'paint(): pixmap valid, size={pm.size()}, crop={self.crop}, crop_mode={self.crop_mode}')
        
        # グレースケール処理
        if self._grayscale:
            # 簡単なグレースケール変換
            img = pm.toImage().convertToFormat(QtGui.QImage.Format.Format_Grayscale8)
            pm = QtGui.QPixmap.fromImage(img)
            logger.debug(f'paint(): applied grayscale conversion')
        
        if self.crop_mode:
            # クロップモードでは全体を表示
            painter.drawPixmap(0, 0, pm)
            logger.debug(f'paint(): drew pixmap in crop mode at (0,0)')
        else:
            # 通常モードではクロップ領域のみ表示
            painter.drawPixmap(self.crop, pm, self.crop)
            logger.debug(f'paint(): drew pixmap with crop {self.crop}')
            self.paint_selectable(painter, option, widget)
        
        logger.debug(f'paint() completed successfully for frame {self._current_frame}')
    
    def itemChange(self, change, value):
        """アイテム状態変更時の処理"""
        if change == self.GraphicsItemChange.ItemSceneHasChanged:
            if value:  # シーンに追加された
                logger.debug(f'Item added to scene, starting animation for {self}')
                self.start_animation()
            else:  # シーンから削除された
                logger.debug(f'Item removed from scene, stopping animation for {self}')
                self.stop_animation()
        
        return super().itemChange(change, value)
    
    def get_extra_save_data(self):
        """保存用の追加データ"""
        return {
            'filename': self.filename,
            'opacity': self.opacity(),
            'grayscale': self.grayscale,
            'current_frame': self._current_frame,
            'crop': [self.crop.topLeft().x(),
                     self.crop.topLeft().y(),
                     self.crop.width(),
                     self.crop.height()]
        }
    
    def create_copy(self):
        """アイテムのコピーを作成"""
        item = BeeAnimatedDataItem(self._animation_data, self.filename)
        item.setPos(self.pos())
        item.setZValue(self.zValue())
        item.setScale(self.scale())
        item.setRotation(self.rotation())
        item.setOpacity(self.opacity())
        item.grayscale = self.grayscale
        if self.flip() == -1:
            item.do_flip()
        item.crop = self.crop
        item._current_frame = self._current_frame
        return item
    
    def copy_to_clipboard(self, clipboard):
        """現在のフレームをクリップボードにコピー"""
        clipboard.setPixmap(self.pixmap())
    
    def pixmap_to_bytes(self, apply_grayscale=False, apply_crop=False):
        """元のアニメーションデータを返す（保存用）"""
        # 元データをそのまま返すことでメモリ効率を保つ
        return (self._animation_data, 'gif')  # 元の形式を保持
    
    def pixmap_from_bytes(self, data):
        """バイト列からアニメーションデータを復元"""
        try:
            self._animation_data = data
            self._frame_cache.clear()
            self._initialize_reader()
            self.reset_crop()
            logger.debug(f'Restored animated data item with {self._frame_count} frames')
        except Exception as e:
            logger.error(f'Failed to restore animated data item: {e}')
    
    def get_filename_for_export(self, imgformat, save_id_default=None):
        """エクスポート用のファイル名を生成"""
        save_id = self.save_id or save_id_default
        assert save_id is not None
        
        if self.filename:
            basename = os.path.splitext(os.path.basename(self.filename))[0]
            return f'{save_id:04}-{basename}.{imgformat}'
        else:
            return f'{save_id:04}.{imgformat}'
    
    def get_imgformat(self, img=None):
        """画像保存形式を決定"""
        # 元データの形式を保持
        if self.filename:
            ext = os.path.splitext(self.filename)[1].lower()
            if ext in ['.gif', '.webp']:
                return ext[1:]  # ドット除去
        return 'gif'  # デフォルト

    def to_animated_gif_bytes(self, apply_crop=False):
        """アニメーションGIF形式でバイトデータを返す（元データ利用）"""
        try:
            if apply_crop and hasattr(self, 'crop') and self.crop != self.bounding_rect_unselected():
                # クロップが適用されている場合は再生成が必要
                return self._generate_cropped_animation('gif')
            
            # 元データがGIFの場合はそのまま返す
            if self.get_imgformat() == 'gif':
                return (self._animation_data, 'gif')
            
            # 他の形式の場合は変換
            return self._convert_animation_format('gif')
        except Exception as e:
            logger.error(f"Failed to export animated GIF for {self}: {e}")
            return (None, 'gif')

    def to_animated_webp_bytes(self, apply_crop=False):
        """アニメーションWebP形式でバイトデータを返す（元データ利用）"""
        try:
            if apply_crop and hasattr(self, 'crop') and self.crop != self.bounding_rect_unselected():
                # クロップが適用されている場合は再生成が必要
                return self._generate_cropped_animation('webp')
            
            # 元データがWebPの場合はそのまま返す
            if self.get_imgformat() == 'webp':
                return (self._animation_data, 'webp')
            
            # 他の形式の場合は変換
            return self._convert_animation_format('webp')
        except Exception as e:
            logger.error(f"Failed to export animated WebP for {self}: {e}")
            return (None, 'webp')

    def to_same_as_source_bytes(self, apply_crop=False):
        """元の形式でバイトデータを返す（Same as Source機能）"""
        try:
            original_format = self.get_imgformat()
            
            if apply_crop and hasattr(self, 'crop') and self.crop != self.bounding_rect_unselected():
                # クロップが適用されている場合は再生成が必要
                return self._generate_cropped_animation(original_format)
            
            # 元データをそのまま返す（最高品質）
            logger.debug(f"Exporting {self.filename} in original format: {original_format}")
            return (self._animation_data, original_format)
            
        except Exception as e:
            logger.error(f"Failed to export same as source for {self}: {e}")
            # フォールバック: 安全なデフォルト処理
            try:
                # まず元の形式判定を再試行
                original_format = self.get_imgformat()
                if original_format == 'webp':
                    return self.to_animated_webp_bytes(apply_crop)
                else:
                    return self.to_animated_gif_bytes(apply_crop)
            except Exception as fallback_error:
                logger.error(f"Fallback also failed for {self}: {fallback_error}")
                # 最終フォールバック: GIFとして処理
                return self.to_animated_gif_bytes(apply_crop)

    def _convert_animation_format(self, target_format):
        """アニメーション形式を変換（Pillowを使用）"""
        try:
            from PIL import Image
            import io
            import tempfile
            
            # 一時ファイルとして保存してPillowで読み込み
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(self._animation_data)
                tmp_file.flush()
                
                with Image.open(tmp_file.name) as pil_img:
                    frames = []
                    durations = []
                    
                    for frame_idx in range(getattr(pil_img, 'n_frames', 1)):
                        pil_img.seek(frame_idx)
                        frames.append(pil_img.copy())
                        durations.append(pil_img.info.get('duration', 100))
                    
                    output = io.BytesIO()
                    if target_format == 'webp':
                        frames[0].save(
                            output,
                            format='WebP',
                            save_all=True,
                            append_images=frames[1:],
                            duration=durations,
                            loop=0
                        )
                    else:  # gif
                        frames[0].save(
                            output,
                            format='GIF',
                            save_all=True,
                            append_images=frames[1:],
                            duration=durations,
                            loop=0
                        )
                    
                    return (output.getvalue(), target_format)
                    
        except Exception as e:
            logger.error(f"Failed to convert animation format to {target_format}: {e}")
            return (None, target_format)

    def _generate_cropped_animation(self, target_format):
        """クロップされたアニメーションを生成"""
        try:
            from PIL import Image
            import io
            
            frames = []
            durations = []
            
            for i in range(self._frame_count):
                pixmap = self.get_frame_pixmap(i)
                if pixmap and not pixmap.isNull():
                    # クロップ適用
                    cropped_pixmap = pixmap.copy(self.crop.toRect())
                    
                    # QPixmapからPIL Imageに変換
                    qimage = cropped_pixmap.toImage()
                    buffer = QtCore.QBuffer()
                    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
                    qimage.save(buffer, 'PNG')
                    
                    pil_img = Image.open(io.BytesIO(buffer.data()))
                    frames.append(pil_img)
                    durations.append(int(1000 / self._fps) if hasattr(self, '_fps') else 100)
            
            if not frames:
                return (None, target_format)
            
            output = io.BytesIO()
            if target_format == 'webp':
                frames[0].save(
                    output,
                    format='WebP',
                    save_all=True,
                    append_images=frames[1:],
                    duration=durations,
                    loop=0
                )
            else:  # gif
                frames[0].save(
                    output,
                    format='GIF',
                    save_all=True,
                    append_images=frames[1:],
                    duration=durations,
                    loop=0
                )
            
            return (output.getvalue(), target_format)
            
        except Exception as e:
            logger.error(f"Failed to generate cropped animation: {e}")
            return (None, target_format)
    
    def __del__(self):
        """デストラクタ - リソースのクリーンアップ"""
        try:
            if hasattr(self, '_buffer') and self._buffer is not None:
                # QBufferがまだ有効かチェック
                if hasattr(self._buffer, 'isOpen') and self._buffer.isOpen():
                    self._buffer.close()
        except (RuntimeError, AttributeError):
            # QBufferが既に削除されている場合は無視
            pass
