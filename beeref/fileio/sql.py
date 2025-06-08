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

"""BeeRef's native file format is using SQLite. Embedded files are
stored in an sqlar table so that they can be extracted using sqlite's
archive command line option.

For more info, see:

https://www.sqlite.org/appfileformat.html
https://www.sqlite.org/sqlar.html
"""

import json
import logging
import os
import pathlib
import shutil
import sqlite3
import tempfile

from PyQt6 import QtGui

from beeref import constants
from beeref.items import (
    BeePixmapItem, BeeAnimatedDataItem, BeeSequenceItem, BeeErrorItem
)
from .errors import BeeFileIOError, IMG_LOADING_ERROR_MSG
from .schema import SCHEMA, USER_VERSION, MIGRATIONS, APPLICATION_ID


logger = logging.getLogger(__name__)


def is_bee_file(path):
    """Check whether the file at the given path is a bee file."""

    return os.path.splitext(path)[1] == '.bee'


def handle_sqlite_errors(func):
    def wrapper(self, *args, **kwargs):
        try:
            func(self, *args, **kwargs)
        except Exception as e:
            logger.exception(f'Error while reading/writing {self.filename}')
            try:
                # Try to roll back transaction if there is any
                if (hasattr(self, '_connection')
                        and self._connection.in_transaction):
                    self.ex('ROLLBACK')
                    logger.debug('Transaction rolled back')
            except sqlite3.Error:
                pass
            self._close_connection()
            if self.worker:
                self.worker.finished.emit(self.filename, [str(e)])
            else:
                raise BeeFileIOError(msg=str(e), filename=self.filename) from e

    return wrapper


class SQLiteIO:

    def __init__(self, filename, scene, create_new=False, readonly=False,
                 worker=None):
        self.scene = scene
        self.create_new = create_new
        self.filename = filename
        self.readonly = readonly
        self.worker = worker
        self.retry = False

    def __del__(self):
        self._close_connection()

    def _close_connection(self):
        if hasattr(self, '_connection'):
            self._connection.close()
            delattr(self, '_connection')
        if hasattr(self, '_cursor'):
            delattr(self, '_cursor')
        if hasattr(self, '_tmpdir'):
            self._tmpdir.cleanup()
            delattr(self, '_tmpdir')

    def _establish_connection(self):
        if (self.create_new
                and not self.readonly
                and os.path.exists(self.filename)):
            os.remove(self.filename)

        if self.create_new:
            self.scene.clear_save_ids()

        uri = pathlib.Path(self.filename).resolve().as_uri()
        if self.readonly:
            uri = f'{uri}?mode=rw'
        self._connection = sqlite3.connect(uri, uri=True)
        self._cursor = self.connection.cursor()
        if not self.create_new:
            try:
                self._migrate()
            except Exception:
                # Updating a file failed; try creating it from scratch instead
                logger.exception('Error migrating bee file')
                self.create_new = True
                self._establish_connection()

    def _migrate(self):
        """Migrate database if necessary."""

        version = self.fetchone('PRAGMA user_version')[0]
        logger.debug(f'Found bee file version: {version}')
        if version >= USER_VERSION:
            logger.debug('Version ok; no migrations necessary')
            return

        if self.readonly:
            try:
                # See whether file is writable so we can migrate it directly
                self.ex('PRAGMA application_id=%s' % APPLICATION_ID)
            except sqlite3.Error:
                logger.debug('File not writable; use temporary copy instead')
                self._connection.close()
                self._tmpdir = tempfile.TemporaryDirectory(
                    prefix=constants.APPNAME)
                tmpname = os.path.join(self._tmpdir.name, 'mig.bee')
                shutil.copyfile(self.filename, tmpname)
                self._connection = sqlite3.connect(tmpname)
                self._cursor = self.connection.cursor()

        self.ex('BEGIN TRANSACTION')
        for i in range(version, USER_VERSION):
            logger.debug(f'Migrating from version {i} to {i + 1}...')
            for migration in MIGRATIONS[i + 1]:
                self.ex(migration)
        self.write_meta()
        self.connection.commit()
        logger.debug('Migration finished')

    @property
    def connection(self):
        if not hasattr(self, '_connection'):
            self._establish_connection()
        return self._connection

    @property
    def cursor(self):
        if not hasattr(self, '_cursor'):
            self._establish_connection()
        return self._cursor

    def ex(self, *args, **kwargs):
        return self.cursor.execute(*args, **kwargs)

    def exmany(self, *args, **kwargs):
        return self.cursor.executemany(*args, **kwargs)

    def fetchone(self, *args, **kwargs):
        self.ex(*args, **kwargs)
        return self.cursor.fetchone()

    def fetchall(self, *args, **kwargs):
        self.ex(*args, **kwargs)
        return self.cursor.fetchall()

    def write_meta(self):
        self.ex('PRAGMA application_id=%s' % APPLICATION_ID)
        self.ex('PRAGMA user_version=%s' % USER_VERSION)
        self.ex('PRAGMA foreign_keys=ON')

    def create_schema_on_new(self):
        if self.create_new:
            self.write_meta()
            for schema in SCHEMA:
                self.ex(schema)

    @handle_sqlite_errors
    def read(self):
        # まずアイテム一覧を取得
        item_rows = self.fetchall(
            'SELECT id, type, x, y, z, scale, rotation, flip, data '
            'FROM items ORDER BY id')

        if self.worker:
            self.worker.begin_processing.emit(len(item_rows))

        for i, item_row in enumerate(item_rows):
            item_id = item_row[0]
            data = {
                'save_id': item_id,
                'type': item_row[1],
                'x': item_row[2],
                'y': item_row[3],
                'z': item_row[4],
                'scale': item_row[5],
                'rotation': item_row[6],
                'flip': item_row[7],
                'data': json.loads(item_row[8]) if item_row[8] else {},
            }

            if data['type'] == 'text':
                # テキストアイテムはsqlarデータ不要
                data['item'] = None  # シーンで後で作成される
            elif data['type'] == 'pixmap':
                # 単一画像アイテム
                sqlar_data = self.fetchone(
                    'SELECT data FROM sqlar WHERE item_id = ? LIMIT 1',
                    (item_id,))
                if sqlar_data and sqlar_data[0]:
                    item = BeePixmapItem(QtGui.QImage())
                    item.pixmap_from_bytes(sqlar_data[0])
                    if item.pixmap().isNull():
                        data['data']['text'] = (
                            f'Image could not be loaded: {item.filename}\n'
                            + IMG_LOADING_ERROR_MSG)
                        data['type'] = BeeErrorItem.TYPE
                    data['item'] = item
                else:
                    logger.error(
                        f'No sqlar data found for pixmap item {item_id}')
                    data['data']['text'] = (
                        f'Image data not found for item {item_id}\n'
                        + IMG_LOADING_ERROR_MSG)
                    data['type'] = BeeErrorItem.TYPE
            elif data['type'] == 'animated_data':
                # アニメーション画像アイテム
                sqlar_data = self.fetchone(
                    'SELECT data FROM sqlar WHERE item_id = ? LIMIT 1',
                    (item_id,))
                if sqlar_data and sqlar_data[0]:
                    try:
                        item = BeeAnimatedDataItem(
                            sqlar_data[0],
                            filename=data['data'].get('filename'))

                        if (not hasattr(item, '_frame_count') or
                                item._frame_count <= 0):
                            data['data']['text'] = (
                                f'Animated image could not be loaded: '
                                f'{item.filename}\n' + IMG_LOADING_ERROR_MSG)
                            data['type'] = BeeErrorItem.TYPE
                            item = BeeErrorItem(**data['data'])
                        data['item'] = item
                    except Exception as e:
                        logger.error(
                            f'Failed to restore animated data item: {e}')
                        data['data']['text'] = (
                            f'Animated image could not be loaded: '
                            f'{data["data"].get("filename", "Unknown")}\n'
                            + IMG_LOADING_ERROR_MSG)
                        data['type'] = BeeErrorItem.TYPE
                        item = BeeErrorItem(**data['data'])
                        data['item'] = item
                else:
                    logger.error(
                        f'No sqlar data found for animated_data item '
                        f'{item_id}')
                    data['data']['text'] = (
                        f'Animation data not found for item {item_id}\n'
                        + IMG_LOADING_ERROR_MSG)
                    data['type'] = BeeErrorItem.TYPE
            elif data['type'] == 'sequence':
                # 連番画像アイテム - itemsのdataからフレーム情報を取得
                try:
                    item_data_json = data['data']

                    if 'frame_files' in item_data_json:
                        # フレームファイル名のリスト（順序付き）
                        frame_files = item_data_json['frame_files']
                        item = BeeSequenceItem()
                        frame_data = []

                        for frame_index, frame_filename in enumerate(
                                frame_files):
                            # sqlarからフレームデータを取得
                            sqlar_row = self.fetchone(
                                'SELECT data FROM sqlar WHERE item_id = ? '
                                'AND name = ?',
                                (item_id, frame_filename))

                            if sqlar_row and sqlar_row[0]:
                                frame_bytes = sqlar_row[0]

                                frame_info = {
                                    'filename': frame_filename,
                                    'sqlar_name': frame_filename,
                                    'duration': item_data_json.get(
                                        'frame_duration', 83),
                                    'size': None,  # 後で設定
                                    'format': 'png',
                                    'data': frame_bytes
                                }

                                # フレームサイズを取得
                                temp_pixmap = QtGui.QPixmap()
                                temp_pixmap.loadFromData(frame_bytes)
                                if not temp_pixmap.isNull():
                                    frame_info['size'] = (
                                        temp_pixmap.width(),
                                        temp_pixmap.height())

                                frame_data.append(frame_info)
                                logger.debug(
                                    f'Loaded frame {frame_index}: '
                                    f'{frame_filename}')
                            else:
                                logger.warning(
                                    f'Frame data not found in sqlar: '
                                    f'{frame_filename} for item {item_id}')

                        # フレームデータとメタデータを設定
                        if frame_data:
                            item._frame_data = frame_data
                            item._frame_count = len(frame_data)

                            # 保存されたメタデータがあれば復元
                            if 'frame_metadata' in item_data_json:
                                item._frame_metadata.update(
                                    item_data_json['frame_metadata'])

                            logger.debug(
                                f'Restored sequence item {item_id} with '
                                f'{len(frame_data)} frames')
                            data['item'] = item
                        else:
                            # フレームデータが見つからない場合はエラーアイテムを作成
                            logger.error(
                                f'No valid frame data found for sequence item '
                                f'{item_id}')
                            data['data']['text'] = (
                                f'Sequence frame data not found for item '
                                f'{item_id}\n' + IMG_LOADING_ERROR_MSG)
                            data['type'] = BeeErrorItem.TYPE
                            item = BeeErrorItem(**data['data'])
                            data['item'] = item
                    else:
                        logger.error(
                            f'No frame_files found in data for sequence '
                            f'item {item_id}')
                        data['data']['text'] = (
                            f'Sequence frame information not found for '
                            f'item {item_id}\n' + IMG_LOADING_ERROR_MSG)
                        data['type'] = BeeErrorItem.TYPE
                        item = BeeErrorItem(**data['data'])
                        data['item'] = item

                except Exception as e:
                    logger.error(
                        f'Failed to restore sequence item {item_id}: {e}')
                    data['data']['text'] = (
                        f'Sequence could not be loaded: '
                        f'{data["data"].get("filename", "Unknown")}\n'
                        + IMG_LOADING_ERROR_MSG)
                    data['type'] = BeeErrorItem.TYPE
                    item = BeeErrorItem(**data['data'])
                    data['item'] = item

            self.scene.add_item_later(data)

            if self.worker:
                logger.trace(f'Emit progress: {i}')
                self.worker.progress.emit(i)
                if self.worker.canceled:
                    self.worker.finished.emit('', [])
                    return
                # Give main thread time to process items:
                self.worker.msleep(10)
        if self.worker:
            self.worker.finished.emit(self.filename, [])

    @handle_sqlite_errors
    def write(self):
        if self.readonly:
            raise sqlite3.OperationalError(
                'Attempt to write to a readonly database')
        try:
            self.create_schema_on_new()
            self.write_data()
        except Exception:
            if self.retry:
                # Trying to recover failed
                raise
            else:
                self.retry = True
                # Try creating file from scratch and save again
                logger.exception(
                    f'Updating to existing file {self.filename} failed')
                self.create_new = True
                self._close_connection()
                self.write()

    def write_data(self):
        to_delete = {row[0] for row in self.fetchall('SELECT id from ITEMS')}
        # We don't want to touch existing items that are displayed as errors:
        keep = {item.original_save_id
                for item in self.scene.items_by_type(BeeErrorItem.TYPE)}
        logger.debug(f'Not saving error items: {keep}')
        to_delete = to_delete - keep

        to_save = list(self.scene.items_for_save())
        if self.worker:
            self.worker.begin_processing.emit(len(to_save))
        for i, item in enumerate(to_save):
            logger.debug(f'Saving {item} with id {item.save_id}')
            if item.save_id:
                self.update_item(item)
                to_delete.remove(item.save_id)
            else:
                self.insert_item(item)
            if self.worker:
                self.worker.progress.emit(i)
                if self.worker.canceled:
                    break
        self.delete_items(to_delete)
        self.ex('VACUUM')
        self.connection.commit()
        if self.worker:
            self.worker.finished.emit(self.filename, [])

    def delete_items(self, to_delete):
        to_delete = [(pk,) for pk in to_delete]
        # itemsテーブルから削除（CASCADE設定によりsqlarも自動削除される）
        self.exmany('DELETE FROM items WHERE id=?', to_delete)
        # 念のため明示的にsqlarからも削除（複数フレーム対応）
        self.exmany('DELETE FROM sqlar WHERE item_id=?', to_delete)
        self.connection.commit()

    def insert_item(self, item):
        self.ex(
            'INSERT INTO items (type, x, y, z, scale, rotation, flip, '
            'data) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (item.TYPE, item.pos().x(), item.pos().y(), item.zValue(),
             item.scale(), item.rotation(), item.flip(),
             json.dumps(item.get_extra_save_data())))
        item.save_id = self.cursor.lastrowid

        if item.TYPE == 'sequence':
            # BeeSequenceItem: 各フレームを個別にsqlarに保存
            if hasattr(item, '_frame_data') and item._frame_data:
                for frame_index, frame_info in enumerate(item._frame_data):
                    frame_data = frame_info.get('data')
                    if frame_data:
                        frame_name = frame_info.get(
                            'sqlar_name',
                            f'sequence_frame_{frame_index:04d}.png')
                        self.ex(
                            'INSERT INTO sqlar (name, item_id, mode, sz, '
                            'data) VALUES (?, ?, ?, ?, ?)',
                            (frame_name,
                             item.save_id,
                             0o644,
                             len(frame_data),
                                frame_data))
                        logger.debug(
                            f'Saved frame {frame_index} as {frame_name} for '
                            f'sequence item {item.save_id}')
            else:
                logger.warning(
                    f'No frame data found for sequence item {item.save_id}')
        elif hasattr(item, 'pixmap_to_bytes'):
            # 通常のpixmapアイテム（BeePixmapItem, BeeAnimatedDataItem）
            pixmap, imgformat = item.pixmap_to_bytes()
            name = item.get_filename_for_export(imgformat)
            self.ex(
                'INSERT INTO sqlar (name, item_id, mode, sz, data) '
                'VALUES (?, ?, ?, ?, ?)',
                (name, item.save_id, 0o644, len(pixmap), pixmap))
        self.connection.commit()

    def update_item(self, item):
        """Update item data.

        We only update the item data, not the pixmap data, as pixmap
        data never changes and is also time-consuming to save.

        Exception: BeeSequenceItem may have frame data changes.
        """
        self.ex(
            'UPDATE items SET x=?, y=?, z=?, scale=?, rotation=?, flip=?, '
            'data=? '
            'WHERE id=?',
            (item.pos().x(), item.pos().y(), item.zValue(), item.scale(),
             item.rotation(), item.flip(),
             json.dumps(item.get_extra_save_data()),
             item.save_id))

        # BeeSequenceItemの場合はフレームデータも更新
        if item.TYPE == 'sequence':
            # 既存のsqlarレコードを削除
            self.ex('DELETE FROM sqlar WHERE item_id = ?', (item.save_id,))

            # 新しいフレームデータを挿入
            if hasattr(item, '_frame_data') and item._frame_data:
                for frame_index, frame_info in enumerate(item._frame_data):
                    frame_data = frame_info.get('data')
                    if frame_data:
                        frame_name = frame_info.get(
                            'sqlar_name',
                            f'sequence_frame_{frame_index:04d}.png')
                        self.ex(
                            'INSERT INTO sqlar (name, item_id, mode, sz, '
                            'data) VALUES (?, ?, ?, ?, ?)',
                            (frame_name,
                             item.save_id,
                             0o644,
                             len(frame_data),
                                frame_data))
                        logger.debug(
                            f'Updated frame {frame_index} as {frame_name} for '
                            f'sequence item {item.save_id}')

        self.connection.commit()
