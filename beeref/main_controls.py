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

import logging
from pathlib import Path

from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt

from beeref import commands, widgets
from beeref.items import BeePixmapItem
from beeref import fileio


logger = logging.getLogger(__name__)


class MainControlsMixin:
    """Basic controls shared by the main view and the welcome overlay:

    * Right-click menu
    * Dropping files
    * Moving the window without title bar
    """

    def init_main_controls(self, main_window):
        self.main_window = main_window
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            self.control_target.on_context_menu)
        self.setAcceptDrops(True)
        self.movewin_active = False

    def on_action_movewin_mode(self):
        if self.movewin_active:
            # Pressing the same shortcut again should end the action
            self.exit_movewin_mode()
        else:
            self.enter_movewin_mode()

    @property
    def viewport_or_self(self):
        if hasattr(self, 'viewport'):
            return self.viewport()
        return self

    def enter_movewin_mode(self, event=None):
        logger.debug('Entering movewin mode')
        self.setMouseTracking(True)
        self.movewin_active = True
        self.viewport_or_self.setCursor(Qt.CursorShape.SizeAllCursor)
        if event is not None:
            self.event_start = event.position()
        else:
            # Fallback for backward compatibility - convert to local coords
            global_pos = QtCore.QPointF(self.cursor().pos())
            self.event_start = self.mapFromGlobal(global_pos)
        if hasattr(self, 'disable_mouse_events'):
            self.disable_mouse_events()

    def exit_movewin_mode(self):
        logger.debug('Exiting movewin mode')
        self.setMouseTracking(False)
        self.movewin_active = False
        self.viewport_or_self.unsetCursor()
        if hasattr(self, 'enable_mouse_events'):
            self.enable_mouse_events()

    def dragEnterEvent(self, event):
        mimedata = event.mimeData()
        logger.debug(f'Drag enter event: {mimedata.formats()}')
        if mimedata.hasUrls():
            # URLからパスを取得して判定
            urls = mimedata.urls()
            valid_items = []
            for url in urls:
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.is_dir() or fileio.is_image_file(
                            str(path)) or fileio.is_bee_file(str(path)):
                        valid_items.append(path)

            if valid_items:
                event.acceptProposedAction()
            else:
                msg = 'ドロップされたファイル/フォルダは対応していません'
                logger.info(msg)
                widgets.BeeNotification(self.control_target, msg)
        elif mimedata.hasImage():
            event.acceptProposedAction()
        else:
            msg = 'Attempted drop not an image or image too big'
            logger.info(msg)
            widgets.BeeNotification(self.control_target, msg)

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        mimedata = event.mimeData()
        logger.debug(f'Handling file drop: {mimedata.formats()}')
        pos = QtCore.QPoint(round(event.position().x()),
                            round(event.position().y()))
        if mimedata.hasUrls():
            logger.debug(f'Found dropped urls: {mimedata.urls()}')

            # URLからパスを取得してフォルダとファイルを分離
            folders = []
            files = []

            for url in mimedata.urls():
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.is_dir():
                        folders.append(path)
                    elif path.is_file():
                        files.append(url)

            # フォルダが存在する場合はフォルダを優先処理
            if folders:
                # 複数フォルダの場合は最初の1つのみ処理
                folder_path = folders[0]
                logger.info(f'フォルダをインポート中: {folder_path}')
                try:
                    if hasattr(self.control_target, 'do_import_folder'):
                        self.control_target.do_import_folder(str(folder_path))
                    else:
                        # フォールバック: actionsモジュール経由でフォルダインポートを実行
                        from beeref.actions import actions
                        action = actions.ImportFolderAction(
                            self.control_target)
                        action.trigger_from_path(str(folder_path))

                    msg = f'フォルダ "{folder_path.name}" をインポートしました'
                    widgets.BeeNotification(self.control_target, msg)
                except Exception as e:
                    msg = f'フォルダのインポートに失敗しました: {str(e)}'
                    logger.error(msg)
                    widgets.BeeNotification(self.control_target, msg)
                return

            # フォルダがない場合はファイル処理
            if files:
                if not self.control_target.scene.items():
                    # Check if we have a bee file we can open directly
                    path = files[0]
                    if (path.isLocalFile()
                            and fileio.is_bee_file(path.toLocalFile())):
                        self.control_target.open_from_file(path.toLocalFile())
                        return
                self.control_target.do_insert_images(files, pos)
            else:
                msg = '有効なファイルまたはフォルダが見つかりませんでした'
                logger.info(msg)
                widgets.BeeNotification(self.control_target, msg)

        elif mimedata.hasImage():
            img = QtGui.QImage(mimedata.imageData())
            item = BeePixmapItem(img)
            pos = self.control_target.mapToScene(pos)
            self.control_target.undo_stack.push(
                commands.InsertItems(self.control_target.scene, [item], pos))
        else:
            logger.info('Drop not an image')

    def mousePressEventMainControls(self, event):
        if self.movewin_active:
            self.exit_movewin_mode()
            event.accept()
            return True

        action, inverted =\
            self.control_target.keyboard_settings.mouse_action_for_event(event)
        if action == 'movewindow':
            self.enter_movewin_mode(event)
            event.accept()
            return True

    def mouseMoveEventMainControls(self, event):
        if self.movewin_active:
            pos = event.position()
            delta = pos - self.event_start
            self.event_start = pos
            self.main_window.move(self.main_window.x() + int(delta.x()),
                                  self.main_window.y() + int(delta.y()))
            event.accept()
            return True

    def mouseReleaseEventMainControls(self, event):
        if self.movewin_active:
            self.exit_movewin_mode()
            event.accept()
            return True

    def keyPressEventMainControls(self, event):
        if self.movewin_active:
            self.exit_movewin_mode()
            event.accept()
            return True
