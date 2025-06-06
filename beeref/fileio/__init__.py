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

from PyQt6 import QtCore

from beeref import commands
from beeref.fileio.errors import BeeFileIOError
from beeref.fileio.image import load_image
from beeref.fileio.sql import SQLiteIO, is_bee_file
from beeref.fileio.folder_import import import_folder_images, FolderImportOptions
from beeref.items import BeePixmapItem, BeeAnimatedDataItem


__all__ = [
    'is_bee_file',
    'load_bee',
    'save_bee',
    'load_images',
    'ThreadedLoader',
    'BeeFileIOError',
]

logger = logging.getLogger(__name__)


def load_bee(filename, scene, worker=None):
    """Load BeeRef native file."""
    logger.info(f'Loading from file {filename}...')
    io = SQLiteIO(filename, scene, readonly=True, worker=worker)
    return io.read()


def save_bee(filename, scene, create_new=False, worker=None):
    """Save BeeRef native file."""
    logger.info(f'Saving to file {filename}...')
    logger.debug(f'Create new: {create_new}')
    io = SQLiteIO(filename, scene, create_new, worker=worker)
    io.write()
    logger.info('End save')


def load_images(filenames, pos, scene, worker):
    """Add images to existing scene."""

    errors = []
    items = []
    worker.begin_processing.emit(len(filenames))
    for i, filename in enumerate(filenames):
        logger.info(f'Loading image from file {filename}')
        data, filename = load_image(filename)
        worker.progress.emit(i)

        # アニメーションデータの場合
        if isinstance(data, dict) and data.get('type') == 'animated_data':
            # 新しいBeeAnimatedDataItem用
            if not data.get('file_data'):
                logger.info(f'No file data found in animated file {filename}')
                errors.append(filename)
                continue

            logger.info(f'Creating new animated data item for {filename}')
            item = BeeAnimatedDataItem(data['file_data'], filename)
            item.set_pos_center(pos)
            scene.add_item_later(
                {'item': item, 'type': 'animated_data'}, selected=True)
            items.append(item)
        else:
            # 静止画の場合
            if data.isNull():
                logger.info(f'Could not load file {filename}')
                errors.append(filename)
                continue

            item = BeePixmapItem(data, filename)
            item.set_pos_center(pos)
            scene.add_item_later(
                {'item': item, 'type': 'pixmap'}, selected=True)
            items.append(item)

        if worker.canceled:
            break
        # Give main thread time to process items:
        worker.msleep(10)

    scene.undo_stack.push(
        commands.InsertItems(scene, items, ignore_first_redo=True))
    worker.finished.emit('', errors)


def load_folder_images(folder_path, pos, scene, worker):
    """Add images from folder to existing scene."""
    
    try:
        logger.info(f'Loading images from folder {folder_path}')
        
        # フォルダインポート実行
        options = FolderImportOptions()
        import_result = import_folder_images(folder_path, (pos.x(), pos.y()), options)
        
        if not import_result.items and not import_result.errors:
            logger.info(f'No images found in folder {folder_path}')
            worker.finished.emit('', [])
            return
        
        worker.begin_processing.emit(len(import_result.items))
        
        items = []
        errors = import_result.errors.copy()
        
        for i, item_data in enumerate(import_result.items):
            try:
                worker.progress.emit(i)
                
                if item_data['type'] == 'animated_data':
                    # BeeAnimatedDataItemを作成
                    animation_data = item_data['data']
                    if animation_data and animation_data.get('file_data'):
                        item = BeeAnimatedDataItem(
                            animation_data['file_data'],
                            item_data['filename']
                        )
                        item.set_pos_center(pos)
                        scene.add_item_later(
                            {'item': item, 'type': 'animated_data'}, selected=True)
                        items.append(item)
                    else:
                        logger.warning(f"Invalid animation data: {item_data['filename']}")
                        errors.append(item_data['filename'])
                        
                elif item_data['type'] == 'pixmap':
                    # BeePixmapItemを作成
                    item = BeePixmapItem(item_data['data'], item_data['filename'])
                    item.set_pos_center(pos)
                    scene.add_item_later(
                        {'item': item, 'type': 'pixmap'}, selected=True)
                    items.append(item)
                    
                else:
                    logger.warning(f"Unknown item type: {item_data['type']}")
                    errors.append(item_data.get('filename', 'unknown'))
                    
            except Exception as e:
                logger.error(f"Error creating item from data: {e}")
                errors.append(item_data.get('filename', 'unknown'))
            
            if worker.canceled:
                break
            # Give main thread time to process items:
            worker.msleep(10)
        
        if items:
            from beeref import commands
            scene.undo_stack.push(
                commands.InsertItems(scene, items, ignore_first_redo=True))
        
        # 結果をログに出力
        logger.info(
            f"Folder import completed: {import_result.animations_created} animations, "
            f"{import_result.static_images} static images, {len(errors)} errors"
        )
        
        worker.finished.emit('', errors)
        
    except Exception as e:
        logger.error(f"Error during folder import: {e}")
        worker.finished.emit('', [str(e)])


class ThreadedIO(QtCore.QThread):
    """Dedicated thread for loading and saving."""

    progress = QtCore.pyqtSignal(int)
    finished = QtCore.pyqtSignal(str, list)
    begin_processing = QtCore.pyqtSignal(int)
    user_input_required = QtCore.pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.kwargs['worker'] = self
        self.canceled = False

    def run(self):
        self.func(*self.args, **self.kwargs)

    def on_canceled(self):
        self.canceled = True
