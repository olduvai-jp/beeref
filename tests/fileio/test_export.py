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
    
    
    def test_animation_format_same_as_source_with_data_item(self, tmpdir, qapp, settings):
        """Same as Source形式でのBeeAnimatedDataItemエクスポートテスト"""
        from beeref.fileio.export import ImagesToDirectoryExporter
        from beeref.items import BeeAnimatedDataItem
        from beeref.scene import BeeGraphicsScene
        from PyQt6 import QtGui, QtCore
        from unittest.mock import patch, MagicMock
        
        # アニメーション形式をSame as Sourceに設定
        settings.setValue('Items/animation_export_format', 'same_as_source')
        
        # シーンとアニメーションアイテムを作成
        scene = BeeGraphicsScene(QUndoStack())
        
        # テスト用のGIFデータ
        gif_data = b'GIF89a\x03\x00\x03\x00\x00\x00\x00\x00\x00\x00\x00;\x00'
        animated_item = BeeAnimatedDataItem(gif_data, filename='test.gif')
        animated_item.save_id = 1
        scene.addItem(animated_item)
        
        # エクスポーターを作成
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        # to_same_as_source_bytesが呼ばれることを確認
        with patch.object(animated_item, 'to_same_as_source_bytes') as mock_same:
            mock_same.return_value = (gif_data, 'gif')
            
            exporter.export()
            
            mock_same.assert_called_once_with(apply_crop=True)
    
    
    def test_animation_format_default_selection(self, tmpdir, qapp, settings):
        """デフォルト設定での形式選択のテスト（Same as Source）"""
        from beeref.fileio.export import ImagesToDirectoryExporter
        from beeref.items import BeeAnimatedDataItem
        from beeref.scene import BeeGraphicsScene
        from PyQt6 import QtGui, QtCore
        from unittest.mock import patch, MagicMock
        
        # デフォルト設定を確認（Same as Sourceになっているはず）
        default_format = settings.valueOrDefault('Items/animation_export_format')
        assert default_format == 'same_as_source'
        
        # シーンとアニメーションアイテムを作成
        scene = BeeGraphicsScene(QUndoStack())
        
        # テスト用のWebPデータ
        webp_data = b'RIFF\x00\x00\x00\x00WEBP'
        animated_item = BeeAnimatedDataItem(webp_data, filename='test.webp')
        animated_item.save_id = 1
        scene.addItem(animated_item)
        
        # エクスポーターを作成
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        # デフォルト設定でto_same_as_source_bytesが呼ばれることを確認
        with patch.object(animated_item, 'to_same_as_source_bytes') as mock_same:
            mock_same.return_value = (webp_data, 'webp')
            
            exporter.export()
            
            mock_same.assert_called_once_with(apply_crop=True)
    
    def test_quality_preservation_with_same_as_source(self, tmpdir, qapp, settings):
        """Same as Source エクスポートによる品質保持テスト"""
        from beeref.fileio.export import ImagesToDirectoryExporter
        from beeref.items import BeeAnimatedDataItem
        from beeref.scene import BeeGraphicsScene
        from unittest.mock import patch
        import os
        
        # Same as Source設定
        settings.setValue('Items/animation_export_format', 'same_as_source')
        
        # シーンとアニメーションアイテムを作成
        scene = BeeGraphicsScene(QUndoStack())
        
        # テスト用の高品質データ（仮想的な大きなファイル）
        original_data = b'HIGH_QUALITY_GIF_DATA' * 100  # 大きなデータを模擬
        animated_item = BeeAnimatedDataItem(original_data, filename='high_quality.gif')
        animated_item.save_id = 1
        scene.addItem(animated_item)
        
        # エクスポーターを作成してエクスポート実行
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        exporter.export()
        
        # ファイルが作成されていることを確認
        exported_files = os.listdir(str(tmpdir))
        assert len(exported_files) == 1
        
        # エクスポートされたファイルサイズが元データと同じであることを確認
        exported_file_path = os.path.join(str(tmpdir), exported_files[0])
        with open(exported_file_path, 'rb') as f:
            exported_data = f.read()
        
        # Same as Sourceでは元データがそのまま保存される
        assert exported_data == original_data



class TestSelectedImagesToDirectoryExporter:
    """SelectedImagesToDirectoryExporterのテスト"""
    
