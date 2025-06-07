import json
import os
import os.path
import stat
from unittest.mock import MagicMock, patch

from PyQt6 import QtCore, QtGui
import pytest

from beeref.fileio import schema, is_bee_file
from beeref.fileio.errors import BeeFileIOError
from beeref.fileio.sql import SQLiteIO
from beeref.items import BeePixmapItem, BeeTextItem, BeeErrorItem


@pytest.mark.parametrize('filename,expected',
                         [(os.path.join('foo', 'bar.bee'), True),
                          (os.path.join('foo', 'bar.png'), False),
                          (os.path.join('foo', 'bar'), False)])
def test_is_bee_file(filename, expected):
    assert is_bee_file(filename) is expected


def test_sqliteio_migrate_does_nothing_when_version_ok(tmpfile):
    io = SQLiteIO(tmpfile, MagicMock(), create_new=True)
    io.ex('PRAGMA user_version=%s' % schema.USER_VERSION)
    io.connection.commit()
    del io
    with patch('beeref.fileio.sql.SQLiteIO.ex') as ex_mock:
        SQLiteIO(tmpfile, MagicMock())
        ex_mock.assert_not_called()


@patch('beeref.fileio.sql.USER_VERSION', 3)
@patch('beeref.fileio.sql.MIGRATIONS', {
    2: ['CREATE TABLE foo (col1 INT)',
        'CREATE TABLE bar (baz INT)'],
    3: ['ALTER TABLE foo ADD COLUMN col2 TEXT']})
def test_sqliteio_migrate_migrates(tmpfile):
    io = SQLiteIO(tmpfile, MagicMock(), create_new=True)
    io.ex('PRAGMA user_version=1')
    io.connection.commit()
    del io
    io = SQLiteIO(tmpfile, MagicMock())
    io.ex('INSERT INTO foo (col1, col2) VALUES (22, "hello world")')
    io.ex('INSERT INTO bar (baz) VALUES (55)')
    result = io.fetchone('PRAGMA user_version')
    assert result[0] == 3


@patch('beeref.fileio.sql.USER_VERSION', 3)
@patch('beeref.fileio.sql.MIGRATIONS', {
    2: ['CREATE TABLE foo (col1 INT)',
        'CREATE TABLE bar (baz INT)'],
    3: ['ALTER TABLE foo ADD COLUMN col2 TEXT']})
def test_sqliteio_migrate_migrates_when_file_not_writable(tmpfile):
    io = SQLiteIO(tmpfile, MagicMock(), create_new=True)
    io.ex('PRAGMA user_version=1')
    io.connection.commit()
    del io
    os.chmod(tmpfile, stat.S_IREAD)
    with pytest.raises(PermissionError):
        open(tmpfile, 'w')
    io = SQLiteIO(tmpfile, MagicMock(), readonly=True)
    io.ex('INSERT INTO foo (col1, col2) VALUES (22, "hello world")')
    io.ex('INSERT INTO bar (baz) VALUES (55)')
    result = io.fetchone('PRAGMA user_version')
    assert result[0] == 3
    newdir = io._tmpdir.name
    del io
    assert os.path.exists(newdir) is False


def test_all_migrations(tmpfile):
    io = SQLiteIO(tmpfile, MagicMock(), create_new=True)

    # Set up version 1 bee file
    io.ex('PRAGMA user_version=1')
    io.ex("""
        CREATE TABLE items (
          id INTEGER PRIMARY KEY,
          type TEXT NOT NULL,
          x REAL DEFAULT 0,
          y REAL DEFAULT 0,
          z REAL DEFAULT 0,
          scale REAL DEFAULT 1,
          rotation REAL DEFAULT 0,
          flip INTEGER DEFAULT 1,
          filename TEXT)""")
    io.ex("""
        CREATE TABLE sqlar (
            name TEXT PRIMARY KEY,
            item_id INTEGER NOT NULL,
            mode INT,
            mtime INT default current_timestamp,
            sz INT,
            data BLOB,
            FOREIGN KEY (item_id)
              REFERENCES items (id)
                 ON DELETE CASCADE
                 ON UPDATE NO ACTION)""")
    io.ex('INSERT INTO items '
          '(type, x, y, z, scale, rotation, flip, filename) '
          'VALUES (?, ?, ?, ?, ?, ?, ?, ?) ',
          ('pixmap', 22.2, 33.3, 0.22, 3.4, 45, -1, 'bee.png'))
    io.ex('INSERT INTO sqlar (item_id, data) VALUES (?, ?)',
          (1, b'bla'))
    io.connection.commit()
    del io

    io = SQLiteIO(tmpfile, MagicMock(), create_new=False)
    result = io.fetchone('PRAGMA user_version')
    assert result[0] == schema.USER_VERSION
    result = io.fetchone(
        'SELECT x, y, items.data, sqlar.data FROM items '
        'LEFT OUTER JOIN sqlar on sqlar.item_id = items.id')
    assert result[0] == 22.2
    assert result[1] == 33.3
    assert json.loads(result[2]) == {'filename': 'bee.png'}
    assert result[3] == b'bla'


def test_sqliteio_write_meta_application_id(tmpfile):
    io = SQLiteIO(tmpfile, MagicMock(), create_new=True)
    io.write_meta()
    result = io.fetchone('PRAGMA application_id')
    assert result[0] == schema.APPLICATION_ID


def test_sqliteio_write_meta_user_version(tmpfile):
    io = SQLiteIO(tmpfile, MagicMock(), create_new=True)
    io.write_meta()
    result = io.fetchone('PRAGMA user_version')
    assert result[0] == schema.USER_VERSION


def test_sqliteio_write_meta_foreign_keys(tmpfile):
    io = SQLiteIO(tmpfile, MagicMock(), create_new=True)
    io.write_meta()
    result = io.fetchone('PRAGMA foreign_keys')
    assert result[0] == 1


def test_sqliteio_create_schema_on_new_when_create_new(tmpfile):
    scene_mock = MagicMock()
    io = SQLiteIO(tmpfile, scene_mock, create_new=True)
    io.create_schema_on_new()
    result = io.fetchone(
        'SELECT COUNT(*) FROM sqlite_master '
        'WHERE type="table" AND name NOT LIKE "sqlite_%"')
    assert result[0] == 2
    scene_mock.clear_save_ids.assert_called_once()


@patch('beeref.fileio.sql.SQLiteIO._migrate')
def test_sqliteio_create_schema_on_new_when_not_create_new(
        migrate_mock, tmpfile):
    scene_mock = MagicMock()
    io = SQLiteIO(tmpfile, scene_mock, create_new=False)
    io.create_schema_on_new()
    result = io.fetchone(
        'SELECT COUNT(*) FROM sqlite_master '
        'WHERE type="table" AND name NOT LIKE "sqlite_%"')
    assert result[0] == 0
    scene_mock.clear_save_ids.assert_not_called()


def test_sqliteio_readonly_doesnt_allow_write(view, tmpfile):
    with open(tmpfile, 'w') as f:
        f.write('foobar')
    io = SQLiteIO(tmpfile, view.scene, readonly=True)

    with pytest.raises(BeeFileIOError) as exinfo:
        io.write()

    assert exinfo.value.filename == tmpfile
    with open(tmpfile, 'r') as f:
        f.read() == 'foobar'


def test_sqliteio_write_calls_create_schema_on_new(tmpfile, view):
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    with patch.object(io, 'create_schema_on_new') as crmock:
        with patch.object(io, 'fetchall'):
            with patch.object(io, 'exmany'):
                io.write()
                crmock.assert_called_once()


def test_sqliteio_write_calls_write_meta(tmpfile, view):
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    with patch.object(io, 'write_meta') as metamock:
        with patch.object(io, 'fetchall'):
            with patch.object(io, 'exmany'):
                io.write()
                metamock.assert_called_once()


def test_sqliteio_write_inserts_new_text_item(tmpfile, view):
    item = BeeTextItem(text='foo bar')
    view.scene.addItem(item)
    item.setScale(1.3)
    item.setPos(44, 55)
    item.setZValue(0.22)
    item.setRotation(33)
    item.do_flip()
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.write()

    assert item.save_id == 1
    result = io.fetchone(
        'SELECT x, y, z, scale, rotation, flip, items.data, type, '
        'sqlar.data, sqlar.name '
        'FROM items '
        'LEFT OUTER JOIN sqlar on sqlar.item_id = items.id')
    assert result[0] == 44.0
    assert result[1] == 55.0
    assert result[2] == 0.22
    assert result[3] == 1.3
    assert result[4] == 33
    assert result[5] == -1
    assert json.loads(result[6]) == {'text': 'foo bar'}
    assert result[7] == 'text'
    assert result[8] is None
    assert result[9] is None


def test_sqliteio_write_inserts_new_pixmap_item_png(tmpfile, view):
    item = BeePixmapItem(QtGui.QImage(), filename='bee.jpg')
    view.scene.addItem(item)
    item.setOpacity(0.66)
    item.setScale(1.3)
    item.setPos(44, 55)
    item.setZValue(0.22)
    item.setRotation(33)
    item.do_flip()
    item.crop = QtCore.QRectF(5, 5, 100, 80)
    item.grayscale = True
    item.pixmap_to_bytes = MagicMock(return_value=(b'abc', 'png'))
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.write()

    assert item.save_id == 1
    result = io.fetchone(
        'SELECT x, y, z, scale, rotation, flip, items.data, type, '
        'sqlar.data, sqlar.name '
        'FROM items '
        'INNER JOIN sqlar on sqlar.item_id = items.id')
    assert result[0] == 44.0
    assert result[1] == 55.0
    assert result[2] == 0.22
    assert result[3] == 1.3
    assert result[4] == 33
    assert result[5] == -1
    assert json.loads(result[6]) == {
        'filename': 'bee.jpg',
        'crop': [5, 5, 100, 80],
        'opacity': 0.66,
        'grayscale': True,
    }
    assert result[7] == 'pixmap'
    assert result[8] == b'abc'
    assert result[9] == '0001-bee.png'


def test_sqliteio_write_inserts_new_pixmap_item_jpg(tmpfile, view):
    item = BeePixmapItem(QtGui.QImage(), filename='bee.jpg')
    view.scene.addItem(item)
    item.pixmap_to_bytes = MagicMock(return_value=(b'abc', 'jpg'))
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.write()

    assert item.save_id == 1
    result = io.fetchone(
        'SELECT type, sqlar.data, sqlar.name '
        'FROM items '
        'INNER JOIN sqlar on sqlar.item_id = items.id')
    assert result[0] == 'pixmap'
    assert result[1] == b'abc'
    assert result[2] == '0001-bee.jpg'


def test_sqliteio_write_inserts_new_pixmap_item_without_filename(
        tmpfile, view, item):
    view.scene.addItem(item)
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.write()

    assert item.save_id == 1
    result = io.fetchone(
        'SELECT items.data, sqlar.name FROM items '
        'INNER JOIN sqlar on sqlar.item_id = items.id')
    assert json.loads(result[0])['filename'] is None
    assert result[1] == '0001.png'


def test_sqliteio_write_updates_existing_text_item(tmpfile, view):
    item = BeeTextItem(text='foo bar')
    view.scene.addItem(item)
    item.setScale(1.3)
    item.setPos(44, 55)
    item.setZValue(0.22)
    item.setRotation(33)
    item.save_id = 1
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.write()
    assert io.fetchone('SELECT COUNT(*) from items') == (1,)

    item.setScale(0.7)
    item.setPos(20, 30)
    item.setZValue(0.33)
    item.setRotation(100)
    item.do_flip()
    item.setPlainText('updated')
    io.create_new = False
    io.write()

    assert io.fetchone('SELECT COUNT(*) from items') == (1,)
    result = io.fetchone(
        'SELECT x, y, z, scale, rotation, flip, items.data, sqlar.data '
        'FROM items '
        'LEFT OUTER JOIN sqlar on sqlar.item_id = items.id')
    assert result[0] == 20
    assert result[1] == 30
    assert result[2] == 0.33
    assert result[3] == 0.7
    assert result[4] == 100
    assert result[5] == -1
    assert json.loads(result[6]) == {'text': 'updated'}
    assert result[7] is None


def test_sqliteio_write_updates_existing_pixmap_item(tmpfile, view):
    item = BeePixmapItem(QtGui.QImage(), filename='bee.png')
    view.scene.addItem(item)
    item.setScale(1.3)
    item.setPos(44, 55)
    item.setZValue(0.22)
    item.setRotation(33)
    item.setOpacity(0.2)
    item.save_id = 1
    item.crop = QtCore.QRectF(5, 5, 80, 100)
    item.pixmap_to_bytes = MagicMock(return_value=(b'abc', 'png'))
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.write()
    assert io.fetchone('SELECT COUNT(*) from items') == (1,)

    item.setScale(0.7)
    item.setPos(20, 30)
    item.setZValue(0.33)
    item.setRotation(100)
    item.setOpacity(0.75)
    item.do_flip()
    item.crop = QtCore.QRectF(1, 2, 30, 40)
    item.grayscale = True
    item.filename = 'new.png'
    item.pixmap_to_bytes.return_value = b'updated'
    io.create_new = False
    io.write()

    assert io.fetchone('SELECT COUNT(*) from items') == (1,)
    result = io.fetchone(
        'SELECT x, y, z, scale, rotation, flip, items.data, sqlar.data '
        'FROM items '
        'INNER JOIN sqlar on sqlar.item_id = items.id')
    assert result[0] == 20
    assert result[1] == 30
    assert result[2] == 0.33
    assert result[3] == 0.7
    assert result[4] == 100
    assert result[5] == -1
    assert json.loads(result[6]) == {
        'filename': 'new.png',
        'crop': [1, 2, 30, 40],
        'opacity': 0.75,
        'grayscale': True,
    }
    assert result[7] == b'abc'


def test_sqliteio_write_keeps_pixmap_item_of_error_item(tmpfile, view):
    item = BeePixmapItem(QtGui.QImage(), filename='bee.png')
    view.scene.addItem(item)
    item.setScale(1.3)
    item.setPos(44, 55)
    item.setZValue(0.22)
    item.setRotation(33)
    item.setOpacity(0.2)
    item.save_id = 1
    item.crop = QtCore.QRectF(5, 5, 80, 100)
    item.pixmap_to_bytes = MagicMock(return_value=(b'abc', 'png'))
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.write()
    view.scene.removeItem(item)
    assert io.fetchone('SELECT COUNT(*) from items') == (1,)

    err_item = BeeErrorItem('errormsg')
    err_item.original_save_id = 1
    err_item.setScale(0.7)
    err_item.setPos(20, 30)
    err_item.setZValue(0.33)
    err_item.setRotation(100)
    view.scene.addItem(err_item)
    io.create_new = False
    io.write()

    assert io.fetchone('SELECT COUNT(*) from items') == (1,)
    result = io.fetchone(
        'SELECT x, y, z, scale, rotation, flip, items.data, sqlar.data '
        'FROM items '
        'INNER JOIN sqlar on sqlar.item_id = items.id')
    assert result[0] == 44
    assert result[1] == 55
    assert result[2] == 0.22
    assert result[3] == 1.3
    assert result[4] == 33
    assert result[5] == 1
    assert json.loads(result[6]) == {
        'filename': 'bee.png',
        'crop': [5, 5, 80, 100],
        'opacity': 0.2,
        'grayscale': False,
    }
    assert result[7] == b'abc'


def test_sqliteio_doesnt_write_error_item_to_new_file(tmpfile, view):
    err_item = BeeErrorItem('errormsg')
    err_item.original_save_id = 1
    view.scene.addItem(err_item)
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.create_new = True
    io.write()
    assert io.fetchone('SELECT COUNT(*) from items') == (0,)


def test_sqliteio_write_removes_nonexisting_text_item(tmpfile, view):
    item = BeeTextItem('foo bar')
    item.setScale(1.3)
    item.setPos(44, 55)
    view.scene.addItem(item)
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.write()

    view.scene.removeItem(item)
    io.create_new = False
    io.write()

    assert io.fetchone('SELECT COUNT(*) from items') == (0,)
    assert io.fetchone('SELECT COUNT(*) from sqlar') == (0,)


def test_sqliteio_write_removes_nonexisting_pixmap_item(tmpfile, view):
    item = BeePixmapItem(QtGui.QImage(), filename='bee.png')
    item.setScale(1.3)
    item.setPos(44, 55)
    view.scene.addItem(item)
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.write()
    assert io.fetchone('SELECT COUNT(*) from items') == (1,)
    assert io.fetchone('SELECT COUNT(*) from sqlar') == (1,)

    view.scene.removeItem(item)

    io = SQLiteIO(tmpfile, view.scene, create_new=False)
    io.create_new = False
    io.write()

    assert io.fetchone('SELECT COUNT(*) from items') == (0,)
    assert io.fetchone('SELECT COUNT(*) from sqlar') == (0,)


def test_sqliteio_write_update_recovers_from_borked_file(view, tmpfile):
    item = BeePixmapItem(QtGui.QImage(), filename='bee.png')
    item.save_id = 1
    view.scene.addItem(item)

    with open(tmpfile, 'w') as f:
        f.write('foobar')

    io = SQLiteIO(tmpfile, view.scene, create_new=False)
    io.write()
    result = io.fetchone('SELECT COUNT(*) FROM items')
    assert result[0] == 1


def test_sqliteio_write_update_recovers_from_nonexisting_file(view, tmpfile):
    item = BeePixmapItem(QtGui.QImage(), filename='bee.png')
    item.save_id = 1
    view.scene.addItem(item)
    io = SQLiteIO(tmpfile, view.scene, create_new=False)
    io.write()
    result = io.fetchone('SELECT COUNT(*) FROM items')
    assert result[0] == 1


def test_sqliteio_write_updates_progress(tmpfile, view):
    worker = MagicMock(canceled=False)
    io = SQLiteIO(tmpfile, view.scene, create_new=True, worker=worker)
    item = BeePixmapItem(QtGui.QImage())
    view.scene.addItem(item)
    io.write()
    worker.begin_processing.emit.assert_called_once_with(1)
    worker.progress.emit.assert_called_once_with(0)
    worker.finished.emit.assert_called_once_with(tmpfile, [])


def test_sqliteio_write_canceled(tmpfile, view):
    worker = MagicMock(canceled=True)
    io = SQLiteIO(tmpfile, view.scene, create_new=True, worker=worker)
    item = BeePixmapItem(QtGui.QImage())
    view.scene.addItem(item)
    item = BeePixmapItem(QtGui.QImage())
    view.scene.addItem(item)
    io.write()
    worker.begin_processing.emit.assert_called_once_with(2)
    worker.progress.emit.assert_called_once_with(0)
    worker.finished.emit.assert_called_once_with(tmpfile, [])


def test_sqliteio_read_reads_readonly_text_item(tmpfile, view):
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.create_schema_on_new()
    io.ex('INSERT INTO items '
          '(type, x, y, z, scale, rotation, flip, data) '
          'VALUES (?, ?, ?, ?, ?, ?, ?, ?) ',
          ('text', 22.2, 33.3, 0.22, 3.4, 45, -1,
           json.dumps({'text': 'foo bar'})))
    io.connection.commit()
    del io

    io = SQLiteIO(tmpfile, view.scene, readonly=True)
    io.read()
    view.scene.add_queued_items()
    assert len(view.scene.items()) == 1
    item = view.scene.items()[0]
    assert isinstance(item, BeeTextItem)
    assert item.isSelected() is False
    assert item.save_id == 1
    assert item.pos().x() == 22.2
    assert item.pos().y() == 33.3
    assert item.zValue() == 0.22
    assert item.scale() == 3.4
    assert item.rotation() == 45
    assert item.flip() == -1
    assert item.toPlainText() == 'foo bar'
    assert view.scene.items_to_add.empty() is True


def test_sqliteio_read_reads_readonly_pixmap_item(tmpfile, view, imgdata3x3):
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.create_schema_on_new()
    io.ex('INSERT INTO items '
          '(type, x, y, z, scale, rotation, flip, data) '
          'VALUES (?, ?, ?, ?, ?, ?, ?, ?) ',
          ('pixmap', 22.2, 33.3, 0.22, 3.4, 45, -1,
           json.dumps({'filename': 'bee.png'})))
    io.ex('INSERT INTO sqlar (item_id, data) VALUES (?, ?)',
          (1, imgdata3x3))
    io.connection.commit()
    del io

    io = SQLiteIO(tmpfile, view.scene, readonly=True)
    io.read()
    view.scene.add_queued_items()
    assert len(view.scene.items()) == 1
    item = view.scene.items()[0]
    assert isinstance(item, BeePixmapItem)
    assert item.isSelected() is False
    assert item.save_id == 1
    assert item.pos().x() == 22.2
    assert item.pos().y() == 33.3
    assert item.zValue() == 0.22
    assert item.scale() == 3.4
    assert item.rotation() == 45
    assert item.flip() == -1
    assert item.filename == 'bee.png'
    assert item.width == 3
    assert item.height == 3
    assert item.crop == QtCore.QRectF(0, 0, 3, 3)
    assert item.opacity() == 1
    assert item.grayscale is False
    assert view.scene.items_to_add.empty() is True


def test_sqliteio_read_reads_readonly_pixmap_item_error(tmpfile, view):
    io = SQLiteIO(tmpfile, view.scene, create_new=True)
    io.create_schema_on_new()
    io.ex('INSERT INTO items '
          '(type, x, y, z, scale, rotation, flip, data) '
          'VALUES (?, ?, ?, ?, ?, ?, ?, ?) ',
          ('pixmap', 22.2, 33.3, 0.22, 3.4, 45, -1,
           json.dumps({'filename': 'bee.png'})))
    io.ex('INSERT INTO sqlar (item_id, data) VALUES (?, ?)',
          (1, b'not an image'))
    io.connection.commit()
    del io

    io = SQLiteIO(tmpfile, view.scene, readonly=True)
    io.read()
    view.scene.add_queued_items()
    assert len(view.scene.items()) == 1
    item = view.scene.items()[0]
    assert isinstance(item, BeeErrorItem)
    item.toPlainText().startswith('Unknown')
    assert view.scene.items_to_add.empty() is True


def test_sqliteio_read_updates_progress(tmpfile, view):
    worker = MagicMock(canceled=False)
    io = SQLiteIO(tmpfile, view.scene, create_new=True,
                  worker=worker)

    io.create_schema_on_new()
    io.ex('INSERT INTO items (type, x, y, z, scale, data) '
          'VALUES (?, ?, ?, ?, ?, ?) ',
          ('pixmap', 0, 0, 0, 1, json.dumps({'filename': 'bee.png'})))
    io.ex('INSERT INTO sqlar (item_id, data) VALUES (?, ?)', (1, b''))
    io.connection.commit()

    io.read()
    worker.begin_processing.emit.assert_called_once_with(1)
    worker.progress.emit.assert_called_once_with(0)
    worker.finished.emit.assert_called_once_with(tmpfile, [])


def test_sqliteio_read_canceled(tmpfile, view):
    worker = MagicMock(canceled=True)
    io = SQLiteIO(tmpfile, view.scene, create_new=True, worker=worker)
    io.create_schema_on_new()
    io.ex('INSERT INTO items (type, x, y, z, scale, data) '
          'VALUES (?, ?, ?, ?, ?, ?) ',
          ('pixmap', 0, 0, 0, 1, json.dumps({'filename': 'bee.png'})))
    io.ex('INSERT INTO sqlar (item_id, data) VALUES (?, ?)', (1, b''))
    io.ex('INSERT INTO items (type, x, y, z, scale, data) '
          'VALUES (?, ?, ?, ?, ?, ?) ',
          ('pixmap', 50, 50, 0, 1, json.dumps({'filename': 'bee2.png'})))
    io.ex('INSERT INTO sqlar (item_id, data) VALUES (?, ?)', (2, b''))
    io.connection.commit()

    io.read()
    worker.begin_processing.emit.assert_called_once_with(2)
    worker.progress.emit.assert_called_once_with(0)
    worker.finished.emit.assert_called_once_with('', [])


def test_sqliteio_read_raises_error_when_file_borked(view, tmpfile):
    with open(tmpfile, 'w') as f:
        f.write('foobar')

    io = SQLiteIO(tmpfile, view.scene, readonly=True)
    with pytest.raises(BeeFileIOError) as exinfo:
        io.read()
    assert exinfo.value.filename == tmpfile


def test_sqliteio_read_emits_error_message_when_file_borked(view, tmpfile):
    with open(tmpfile, 'w') as f:
        f.write('foobar')

    worker = MagicMock()
    io = SQLiteIO(tmpfile, view.scene, readonly=True, worker=worker)
    io.read()
    worker.finished.emit.assert_called_once()
    args = worker.finished.emit.call_args_list[0][0]
    assert args[0] == tmpfile
    assert len(args[1]) == 1


def test_sqliteio_read_raises_error_when_file_empty(view, tmpfile):
    io = SQLiteIO(tmpfile, view.scene, readonly=True)
    with pytest.raises(BeeFileIOError) as exinfo:
        io.read()
    assert exinfo.value.filename == tmpfile

    # should not create a file on reading!
    assert os.path.isfile(tmpfile) is False


class TestSQLiteIOSequenceItem:
    """BeeSequenceItemのSQL関連テスト"""

    def create_test_pixmap(self, width=10, height=10, color=QtCore.Qt.GlobalColor.red):
        """テスト用のQPixmapを作成"""
        pixmap = QtGui.QPixmap(width, height)
        pixmap.fill(color)
        return pixmap

    def test_sqliteio_write_inserts_new_sequence_item(self, tmpfile, view):
        """新しいBeeSequenceItemの保存テスト"""
        from beeref.items import BeeSequenceItem

        item = BeeSequenceItem()
        item.filename = 'test_sequence.png'

        # フレームを追加
        for i in range(3):
            pixmap = self.create_test_pixmap(color=[
                QtCore.Qt.GlobalColor.red,
                QtCore.Qt.GlobalColor.green,
                QtCore.Qt.GlobalColor.blue
            ][i])
            item.add_frame(pixmap, f'frame_{i:03d}.png', 100)

        # 位置・変形設定
        view.scene.addItem(item)
        item.setScale(1.3)
        item.setPos(44, 55)
        item.setZValue(0.22)
        item.setRotation(33)
        item.setOpacity(0.8)
        item.grayscale = True
        item.crop = QtCore.QRectF(5, 5, 100, 80)
        item._current_frame = 1

        io = SQLiteIO(tmpfile, view.scene, create_new=True)
        io.write()

        assert item.save_id == 1

        # itemsテーブルの確認
        result = io.fetchone(
            'SELECT x, y, z, scale, rotation, flip, items.data, type '
            'FROM items WHERE id = ?', (1,))
        assert result[0] == 44.0
        assert result[1] == 55.0
        assert result[2] == 0.22
        assert result[3] == 1.3
        assert result[4] == 33
        assert result[5] == 1
        assert result[7] == 'sequence'

        data = json.loads(result[6])
        assert data['filename'] == 'test_sequence.png'
        assert data['opacity'] == 0.8
        assert data['grayscale'] is True
        assert data['current_frame'] == 1
        assert data['crop'] == [5, 5, 100, 80]
        assert data['frame_count'] == 3
        assert len(data['frame_files']) == 3
        assert 'frame_metadata' in data

        # sqlarテーブルの確認（フレームデータ）
        sqlar_results = io.fetchall(
            'SELECT name, data FROM sqlar WHERE item_id = ? ORDER BY name', (1,))
        assert len(sqlar_results) == 3

        # フレームファイルが正しく保存されている
        for i, (name, data) in enumerate(sqlar_results):
            assert name == f'sequence_frame_{i:04d}.png'
            assert isinstance(data, bytes)
            assert len(data) > 0

    def test_sqliteio_write_updates_existing_sequence_item(self, tmpfile, view):
        """既存のBeeSequenceItemの更新テスト"""
        from beeref.items import BeeSequenceItem

        item = BeeSequenceItem()
        item.filename = 'original_sequence.png'

        # 最初のフレームを追加
        pixmap = self.create_test_pixmap()
        item.add_frame(pixmap, 'frame_001.png', 100)

        view.scene.addItem(item)
        item.setScale(1.0)
        item.setPos(10, 10)
        item.save_id = 1

        io = SQLiteIO(tmpfile, view.scene, create_new=True)
        io.write()
        assert io.fetchone('SELECT COUNT(*) from items') == (1,)

        # アイテムを更新
        item.filename = 'updated_sequence.png'
        item.setScale(2.0)
        item.setPos(20, 30)
        item.setOpacity(0.5)
        item._current_frame = 0

        # 新しいフレームを追加
        new_pixmap = self.create_test_pixmap(color=QtCore.Qt.GlobalColor.yellow)
        item.add_frame(new_pixmap, 'frame_002.png', 120)

        io.create_new = False
        io.write()

        assert io.fetchone('SELECT COUNT(*) from items') == (1,)
        result = io.fetchone(
            'SELECT x, y, scale, items.data FROM items WHERE id = ?', (1,))
        assert result[0] == 20
        assert result[1] == 30
        assert result[2] == 2.0

        data = json.loads(result[3])
        assert data['filename'] == 'updated_sequence.png'
        assert data['opacity'] == 0.5
        assert data['frame_count'] == 2

        # sqlarテーブルの確認（フレーム数が増えている）
        sqlar_count = io.fetchone('SELECT COUNT(*) FROM sqlar WHERE item_id = ?', (1,))
        assert sqlar_count[0] == 2

    def test_sqliteio_read_reads_readonly_sequence_item(self, tmpfile, view):
        """BeeSequenceItemの読み込みテスト"""
        from beeref.items import BeeSequenceItem

        io = SQLiteIO(tmpfile, view.scene, create_new=True)
        io.create_schema_on_new()

        # テストデータを準備
        frame_data = [
            {'filename': 'frame_001.png', 'duration': 100,
                'sqlar_name': 'sequence_frame_0000.png'},
            {'filename': 'frame_002.png', 'duration': 120,
                'sqlar_name': 'sequence_frame_0001.png'}
        ]

        sequence_data = {
            'filename': 'test_sequence.png',
            'opacity': 0.7,
            'grayscale': True,
            'current_frame': 1,
            'crop': [10, 20, 30, 40],
            'frame_count': 2,
            'frame_files': ['sequence_frame_0000.png', 'sequence_frame_0001.png'],
            'frame_metadata': {'fps': 24, 'loop': True},
            'frame_data': frame_data
        }

        # itemsテーブルに挿入
        io.ex('INSERT INTO items '
              '(type, x, y, z, scale, rotation, flip, data) '
              'VALUES (?, ?, ?, ?, ?, ?, ?, ?) ',
              ('sequence', 50.0, 60.0, 0.5, 1.5, 90, 1, json.dumps(sequence_data)))

        # sqlarテーブルにフレームデータを挿入
        for i, frame_info in enumerate(frame_data):
            # テスト用の画像データを作成
            pixmap = self.create_test_pixmap()
            barray = QtCore.QByteArray()
            buffer = QtCore.QBuffer(barray)
            buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
            pixmap.save(buffer, 'PNG')
            frame_bytes = barray.data()

            io.ex('INSERT INTO sqlar (item_id, name, data) VALUES (?, ?, ?)',
                  (1, frame_info['sqlar_name'], frame_bytes))

        io.connection.commit()
        del io

        # 読み込みテスト
        io = SQLiteIO(tmpfile, view.scene, readonly=True)
        io.read()
        view.scene.add_queued_items()

        assert len(view.scene.items()) == 1
        item = view.scene.items()[0]
        assert isinstance(item, BeeSequenceItem)
        assert item.isSelected() is False
        assert item.save_id == 1
        assert item.pos().x() == 50.0
        assert item.pos().y() == 60.0
        assert item.zValue() == 0.5
        assert item.scale() == 1.5
        assert item.rotation() == 90
        assert item.flip() == 1
        assert item.filename == 'test_sequence.png'
        assert item.opacity() == 0.7
        assert item.grayscale is True
        assert item._current_frame == 1
        assert item.crop == QtCore.QRectF(10, 20, 30, 40)
        assert item.get_frame_count() == 2
        assert item._frame_metadata['fps'] == 24
        assert view.scene.items_to_add.empty() is True

    def test_sqliteio_read_reads_readonly_sequence_item_error(self, tmpfile, view):
        """破損データでのBeeSequenceItem読み込みエラーテスト"""
        from beeref.items import BeeErrorItem

        io = SQLiteIO(tmpfile, view.scene, create_new=True)
        io.create_schema_on_new()

        # 不正なsequenceデータ
        invalid_data = {
            'filename': 'broken_sequence.png',
            'frame_count': 1,
            'frame_files': ['missing_frame.png']
        }

        io.ex('INSERT INTO items '
              '(type, x, y, z, scale, rotation, flip, data) '
              'VALUES (?, ?, ?, ?, ?, ?, ?, ?) ',
              ('sequence', 22.2, 33.3, 0.22, 3.4, 45, -1, json.dumps(invalid_data)))
        # sqlarデータは意図的に入れない（フレームデータが欠損）
        io.connection.commit()
        del io

        io = SQLiteIO(tmpfile, view.scene, readonly=True)
        io.read()
        view.scene.add_queued_items()

        assert len(view.scene.items()) == 1
        item = view.scene.items()[0]
        assert isinstance(item, BeeErrorItem)
        assert 'sequence' in item.toPlainText().lower()
        assert view.scene.items_to_add.empty() is True

    def test_sqliteio_write_removes_nonexisting_sequence_item(self, tmpfile, view):
        """削除されたBeeSequenceItemの処理テスト"""
        from beeref.items import BeeSequenceItem

        item = BeeSequenceItem()
        item.filename = 'to_be_removed.png'
        pixmap = self.create_test_pixmap()
        item.add_frame(pixmap, 'frame_001.png', 100)

        view.scene.addItem(item)
        io = SQLiteIO(tmpfile, view.scene, create_new=True)
        io.write()

        # アイテムとフレームデータが保存されている
        assert io.fetchone('SELECT COUNT(*) from items') == (1,)
        assert io.fetchone('SELECT COUNT(*) from sqlar') == (1,)

        # シーンからアイテムを削除
        view.scene.removeItem(item)

        io = SQLiteIO(tmpfile, view.scene, create_new=False)
        io.write()

        # データベースからも削除されている
        assert io.fetchone('SELECT COUNT(*) from items') == (0,)
        assert io.fetchone('SELECT COUNT(*) from sqlar') == (0,)

    def test_sqliteio_sequence_item_frame_data_integrity(self, tmpfile, view):
        """フレームデータの整合性テスト"""
        from beeref.items import BeeSequenceItem

        item = BeeSequenceItem()
        item.filename = 'integrity_test.png'

        # 異なるサイズ・色のフレームを追加
        colors = [QtCore.Qt.GlobalColor.red,
                  QtCore.Qt.GlobalColor.green, QtCore.Qt.GlobalColor.blue]
        sizes = [(10, 10), (20, 15), (15, 20)]

        for i, (color, size) in enumerate(zip(colors, sizes)):
            pixmap = self.create_test_pixmap(size[0], size[1], color)
            item.add_frame(pixmap, f'frame_{i+1:03d}.png', 100 + i * 10)

        view.scene.addItem(item)
        io = SQLiteIO(tmpfile, view.scene, create_new=True)
        io.write()
        del io

        # 読み込み後にフレームデータが正しく復元されるかテスト
        io = SQLiteIO(tmpfile, view.scene, readonly=True)
        io.read()
        view.scene.add_queued_items()

        loaded_item = view.scene.items()[0]
        assert loaded_item.get_frame_count() == 3

        # 各フレームが正しく読み込まれるかテスト
        for i in range(3):
            pixmap = loaded_item.get_frame_pixmap(i)
            assert isinstance(pixmap, QtGui.QPixmap)
            assert not pixmap.isNull()
            # フレームがキャッシュされている
            assert i in loaded_item._frame_cache
