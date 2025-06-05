import pytest

from PyQt6.QtGui import QUndoStack
from beeref.fileio.export import (
    exporter_registry,
    SceneToPixmapExporter,
    SceneToSVGExporter,
)


@pytest.mark.parametrize('key,expected',
                         [('png', SceneToPixmapExporter),
                          ('jpg', SceneToPixmapExporter),
                          ('svg', SceneToSVGExporter)])
def test_registry(key, expected):
    exporter_registry[key] == expected


class TestImagesToDirectoryExporter:
    """ImagesToDirectoryExporterのテスト"""
    
    def test_animation_format_selection_webp(self, tmpdir, qapp, settings):
        """設定値に基づくWebP形式選択のテスト"""
        from beeref.fileio.export import ImagesToDirectoryExporter
        from beeref.items import BeeAnimatedPixmapItem
        from beeref.scene import BeeGraphicsScene
        from PyQt6 import QtGui, QtCore
        from unittest.mock import patch, MagicMock
        
        # アニメーション形式をWebPに設定
        settings.setValue('Items/animation_export_format', 'webp')
        
        # シーンとアニメーションアイテムを作成
        scene = BeeGraphicsScene(QUndoStack())
        
        # テスト用のアニメーションデータ
        frames = []
        for i in range(2):
            img = QtGui.QImage(10, 10, QtGui.QImage.Format.Format_ARGB32)
            img.fill(QtGui.QColor(255, 0, 0))
            frames.append(img)
        
        animation_data = {'frames': frames, 'delays': [100, 150]}
        animated_item = BeeAnimatedPixmapItem(animation_data, filename='test.gif')
        animated_item.save_id = 1
        scene.addItem(animated_item)
        
        # エクスポーターを作成
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        # to_animated_webp_bytesが呼ばれることを確認
        with patch.object(animated_item, 'to_animated_webp_bytes') as mock_webp:
            mock_webp.return_value = (b'webp_data', 'webp')
            
            exporter.export()
            
            mock_webp.assert_called_once_with(apply_crop=True)
    
    def test_animation_format_selection_gif(self, tmpdir, qapp, settings):
        """設定値に基づくGIF形式選択のテスト"""
        from beeref.fileio.export import ImagesToDirectoryExporter
        from beeref.items import BeeAnimatedPixmapItem
        from beeref.scene import BeeGraphicsScene
        from PyQt6 import QtGui, QtCore
        from unittest.mock import patch, MagicMock
        
        # アニメーション形式をGIFに設定
        settings.setValue('Items/animation_export_format', 'gif')
        
        # シーンとアニメーションアイテムを作成
        scene = BeeGraphicsScene(QUndoStack())
        
        # テスト用のアニメーションデータ
        frames = []
        for i in range(2):
            img = QtGui.QImage(10, 10, QtGui.QImage.Format.Format_ARGB32)
            img.fill(QtGui.QColor(255, 0, 0))
            frames.append(img)
        
        animation_data = {'frames': frames, 'delays': [100, 150]}
        animated_item = BeeAnimatedPixmapItem(animation_data, filename='test.gif')
        animated_item.save_id = 1
        scene.addItem(animated_item)
        
        # エクスポーターを作成
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        # to_animated_gif_bytesが呼ばれることを確認
        with patch.object(animated_item, 'to_animated_gif_bytes') as mock_gif:
            mock_gif.return_value = (b'gif_data', 'gif')
            
            exporter.export()
            
            mock_gif.assert_called_once_with(apply_crop=True)
    
    def test_animation_format_default_selection(self, tmpdir, qapp, settings):
        """デフォルト設定でのGIF形式選択のテスト"""
        from beeref.fileio.export import ImagesToDirectoryExporter
        from beeref.items import BeeAnimatedPixmapItem
        from beeref.scene import BeeGraphicsScene
        from PyQt6 import QtGui, QtCore
        from unittest.mock import patch, MagicMock
        
        # デフォルト設定のまま（gif）
        assert settings.valueOrDefault('Items/animation_export_format') == 'gif'
        
        # シーンとアニメーションアイテムを作成
        scene = BeeGraphicsScene(QUndoStack())
        
        # テスト用のアニメーションデータ
        frames = []
        for i in range(2):
            img = QtGui.QImage(10, 10, QtGui.QImage.Format.Format_ARGB32)
            img.fill(QtGui.QColor(255, 0, 0))
            frames.append(img)
        
        animation_data = {'frames': frames, 'delays': [100, 150]}
        animated_item = BeeAnimatedPixmapItem(animation_data, filename='test.gif')
        animated_item.save_id = 1
        scene.addItem(animated_item)
        
        # エクスポーターを作成
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        # to_animated_gif_bytesが呼ばれることを確認（デフォルト）
        with patch.object(animated_item, 'to_animated_gif_bytes') as mock_gif:
            mock_gif.return_value = (b'gif_data', 'gif')
            
            exporter.export()
            
            mock_gif.assert_called_once_with(apply_crop=True)
    
    def test_webp_file_extension_generation(self, tmpdir, qapp, settings):
        """WebPファイル拡張子の生成確認テスト"""
        from beeref.fileio.export import ImagesToDirectoryExporter
        from beeref.items import BeeAnimatedPixmapItem
        from beeref.scene import BeeGraphicsScene
        from PyQt6 import QtGui, QtCore
        from unittest.mock import patch
        import os
        
        # アニメーション形式をWebPに設定
        settings.setValue('Items/animation_export_format', 'webp')
        
        # シーンとアニメーションアイテムを作成
        scene = BeeGraphicsScene(QUndoStack())
        
        # テスト用のアニメーションデータ
        frames = []
        for i in range(2):
            img = QtGui.QImage(10, 10, QtGui.QImage.Format.Format_ARGB32)
            img.fill(QtGui.QColor(255, 0, 0))
            frames.append(img)
        
        animation_data = {'frames': frames, 'delays': [100, 150]}
        animated_item = BeeAnimatedPixmapItem(animation_data, filename='test.gif')
        animated_item.save_id = 1
        scene.addItem(animated_item)
        
        # エクスポーターを作成
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        # WebPデータを返すようにモック
        with patch.object(animated_item, 'to_animated_webp_bytes') as mock_webp:
            mock_webp.return_value = (b'webp_data', 'webp')
            
            exporter.export()
            
            # .webp拡張子のファイルが作成されることを確認
            files = os.listdir(str(tmpdir))
            webp_files = [f for f in files if f.endswith('.webp')]
            assert len(webp_files) == 1
            assert webp_files[0] == '0001-test.webp'
    
    def test_gif_file_extension_generation(self, tmpdir, qapp, settings):
        """GIFファイル拡張子の生成確認テスト"""
        from beeref.fileio.export import ImagesToDirectoryExporter
        from beeref.items import BeeAnimatedPixmapItem
        from beeref.scene import BeeGraphicsScene
        from PyQt6 import QtGui, QtCore
        from unittest.mock import patch
        import os
        
        # アニメーション形式をGIFに設定
        settings.setValue('Items/animation_export_format', 'gif')
        
        # シーンとアニメーションアイテムを作成
        scene = BeeGraphicsScene(QUndoStack())
        
        # テスト用のアニメーションデータ
        frames = []
        for i in range(2):
            img = QtGui.QImage(10, 10, QtGui.QImage.Format.Format_ARGB32)
            img.fill(QtGui.QColor(255, 0, 0))
            frames.append(img)
        
        animation_data = {'frames': frames, 'delays': [100, 150]}
        animated_item = BeeAnimatedPixmapItem(animation_data, filename='test.gif')
        animated_item.save_id = 1
        scene.addItem(animated_item)
        
        # エクスポーターを作成
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        # GIFデータを返すようにモック
        with patch.object(animated_item, 'to_animated_gif_bytes') as mock_gif:
            mock_gif.return_value = (b'gif_data', 'gif')
            
            exporter.export()
            
            # .gif拡張子のファイルが作成されることを確認
            files = os.listdir(str(tmpdir))
            gif_files = [f for f in files if f.endswith('.gif')]
            assert len(gif_files) == 1
            assert gif_files[0] == '0001-test.gif'
    
    def test_animation_export_error_handling(self, tmpdir, qapp, settings):
        """アニメーションエクスポートエラーハンドリングのテスト"""
        from beeref.fileio.export import ImagesToDirectoryExporter
        from beeref.items import BeeAnimatedPixmapItem
        from beeref.scene import BeeGraphicsScene
        from PyQt6 import QtGui, QtCore
        from unittest.mock import patch
        import os
        
        # アニメーション形式をWebPに設定
        settings.setValue('Items/animation_export_format', 'webp')
        
        # シーンとアニメーションアイテムを作成
        scene = BeeGraphicsScene(QUndoStack())
        
        # テスト用のアニメーションデータ
        frames = []
        for i in range(2):
            img = QtGui.QImage(10, 10, QtGui.QImage.Format.Format_ARGB32)
            img.fill(QtGui.QColor(255, 0, 0))
            frames.append(img)
        
        animation_data = {'frames': frames, 'delays': [100, 150]}
        animated_item = BeeAnimatedPixmapItem(animation_data, filename='test.gif')
        animated_item.save_id = 1
        scene.addItem(animated_item)
        
        # エクスポーターを作成
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        # WebPエクスポートがNoneを返す場合（エラー）
        with patch.object(animated_item, 'to_animated_webp_bytes') as mock_webp:
            mock_webp.return_value = (None, 'webp')  # エラーケース
            
            exporter.export()
            
            # ファイルが作成されないことを確認
            files = os.listdir(str(tmpdir))
            assert len(files) == 0


class TestSelectedImagesToDirectoryExporter:
    """SelectedImagesToDirectoryExporterのテスト"""
    
    def test_selected_animation_webp_export(self, tmpdir, qapp, settings):
        """選択されたアニメーションのWebPエクスポートテスト"""
        from beeref.fileio.export import SelectedImagesToDirectoryExporter
        from beeref.items import BeeAnimatedPixmapItem
        from beeref.scene import BeeGraphicsScene
        from PyQt6 import QtGui, QtCore
        from unittest.mock import patch
        import os
        
        # アニメーション形式をWebPに設定
        settings.setValue('Items/animation_export_format', 'webp')
        
        # シーンとアニメーションアイテムを作成
        scene = BeeGraphicsScene(QUndoStack())
        
        # テスト用のアニメーションデータ
        frames = []
        for i in range(2):
            img = QtGui.QImage(10, 10, QtGui.QImage.Format.Format_ARGB32)
            img.fill(QtGui.QColor(255, 0, 0))
            frames.append(img)
        
        animation_data = {'frames': frames, 'delays': [100, 150]}
        animated_item = BeeAnimatedPixmapItem(animation_data, filename='selected.gif')
        animated_item.save_id = 1
        scene.addItem(animated_item)
        
        # アイテムを選択
        animated_item.setSelected(True)
        
        # エクスポーターを作成
        exporter = SelectedImagesToDirectoryExporter(scene, str(tmpdir))
        
        # WebPデータを返すようにモック
        with patch.object(animated_item, 'to_animated_webp_bytes') as mock_webp:
            mock_webp.return_value = (b'webp_data', 'webp')
            
            exporter.export()
            
            # WebPファイルが作成されることを確認
            files = os.listdir(str(tmpdir))
            webp_files = [f for f in files if f.endswith('.webp')]
            assert len(webp_files) == 1
            assert webp_files[0] == '0001-selected.webp'
    
    def test_no_selected_items_export(self, tmpdir, qapp, settings):
        """選択されたアイテムがない場合のエクスポートテスト"""
        from beeref.fileio.export import SelectedImagesToDirectoryExporter
        from beeref.items import BeeAnimatedPixmapItem
        from beeref.scene import BeeGraphicsScene
        from PyQt6 import QtGui, QtCore
        import os
        
        # シーンとアニメーションアイテムを作成（選択なし）
        scene = BeeGraphicsScene(QUndoStack())
        
        # テスト用のアニメーションデータ
        frames = []
        for i in range(2):
            img = QtGui.QImage(10, 10, QtGui.QImage.Format.Format_ARGB32)
            img.fill(QtGui.QColor(255, 0, 0))
            frames.append(img)
        
        animation_data = {'frames': frames, 'delays': [100, 150]}
        animated_item = BeeAnimatedPixmapItem(animation_data, filename='unselected.gif')
        animated_item.save_id = 1
        scene.addItem(animated_item)
        
        # アイテムを選択しない
        animated_item.setSelected(False)
        
        # エクスポーターを作成
        exporter = SelectedImagesToDirectoryExporter(scene, str(tmpdir))
        
        exporter.export()
        
        # ファイルが作成されないことを確認
        files = os.listdir(str(tmpdir))
        assert len(files) == 0
