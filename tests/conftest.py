import os.path
import pytest
import uuid

from unittest.mock import MagicMock, patch

from PyQt6 import QtGui, QtWidgets


def pytest_configure(config):
    # Ignore logging configuration for BeeRef during test runs. This
    # avoids logging to the regular log file and spamming test output
    # with debug messages.
    #
    # This needs to be done before the application code is even loaded since
    # logging configuration happens on module level
    import logging.config
    logging.config.dictConfig = MagicMock


@pytest.fixture(autouse=True)
def reset_beeref_actions():
    from beeref.actions.actions import actions
    for key in list(actions.keys()):
        if key.startswith('recent_files_'):
            actions.pop(key)


@pytest.fixture(autouse=True)
def commandline_args():
    config_patcher = patch('beeref.view.commandline_args')
    config_mock = config_patcher.start()
    config_mock.filenames = []
    yield config_mock
    config_patcher.stop()


@pytest.fixture(autouse=True)
def settings(tmpdir):
    from beeref.config import BeeSettings
    dir_patcher = patch('beeref.config.BeeSettings.get_settings_dir',
                        return_value=tmpdir.dirname)
    dir_patcher.start()
    settings = BeeSettings()
    yield settings
    settings.clear()
    dir_patcher.stop()


@pytest.fixture(autouse=True)
def kbsettings(tmpdir):
    from beeref.config import KeyboardSettings
    dir_patcher = patch('beeref.config.BeeSettings.get_settings_dir',
                        return_value=tmpdir.dirname)
    dir_patcher.start()
    kbsettings = KeyboardSettings()
    yield kbsettings
    kbsettings.clear()
    dir_patcher.stop()


@pytest.fixture
def main_window(qtbot):
    from beeref.__main__ import BeeRefMainWindow
    app = QtWidgets.QApplication.instance()
    main = BeeRefMainWindow(app)
    qtbot.addWidget(main)
    yield main


@pytest.fixture
def view(main_window):
    yield main_window.view


@pytest.fixture
def imgfilename3x3():
    root = os.path.dirname(__file__)
    yield os.path.join(root, 'assets', 'test3x3.png')


@pytest.fixture
def imgdata3x3(imgfilename3x3):
    with open(imgfilename3x3, 'rb') as f:
        imgdata3x3 = f.read()
    yield imgdata3x3


@pytest.fixture
def tmpfile(tmpdir):
    yield os.path.join(tmpdir, str(uuid.uuid4()))


@pytest.fixture
def item():
    from beeref.items import BeePixmapItem
    yield BeePixmapItem(QtGui.QImage(10, 10, QtGui.QImage.Format.Format_RGB32))


@pytest.fixture(scope="session")
def qapp():
    from beeref.__main__ import BeeRefApplication
    yield BeeRefApplication([])


@pytest.fixture(autouse=True)
def mock_dialogs():
    """すべてのQtダイアログをモックして自動テストを可能にする"""
    from PyQt6 import QtWidgets
    
    # QMessageBoxをモック
    with patch.object(QtWidgets.QMessageBox, 'question') as question_mock, \
         patch.object(QtWidgets.QMessageBox, 'warning') as warning_mock, \
         patch.object(QtWidgets.QMessageBox, 'information') as info_mock, \
         patch.object(QtWidgets.QMessageBox, 'about') as about_mock, \
         patch.object(QtWidgets.QFileDialog, 'getOpenFileName') as open_file_mock, \
         patch.object(QtWidgets.QFileDialog, 'getSaveFileName') as save_file_mock, \
         patch.object(QtWidgets.QFileDialog, 'getOpenFileNames') as open_files_mock, \
         patch.object(QtWidgets.QFileDialog, 'getExistingDirectory') as get_dir_mock:
        
        # デフォルトの応答を設定
        question_mock.return_value = QtWidgets.QMessageBox.StandardButton.Yes
        warning_mock.return_value = QtWidgets.QMessageBox.StandardButton.Ok
        info_mock.return_value = QtWidgets.QMessageBox.StandardButton.Ok
        about_mock.return_value = None
        
        # ファイルダイアログのデフォルト応答
        open_file_mock.return_value = ('', '')  # (filename, filter)
        save_file_mock.return_value = ('test.bee', 'BeeRef files (*.bee)')
        open_files_mock.return_value = ([], '')  # (filenames, filter)
        get_dir_mock.return_value = ''
        
        yield {
            'question': question_mock,
            'warning': warning_mock,
            'information': info_mock,
            'about': about_mock,
            'open_file': open_file_mock,
            'save_file': save_file_mock,
            'open_files': open_files_mock,
            'get_dir': get_dir_mock,
        }
