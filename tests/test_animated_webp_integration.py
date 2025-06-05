"""
BeeRef Animated WebP出力機能の統合テスト

設定変更からエクスポートまでの一連の流れをテストし、
既存GIF機能との共存確認を行います。
"""

import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtGui import QUndoStack

from beeref import constants
from beeref.config import BeeSettings
from beeref.items import BeeAnimatedPixmapItem
from beeref.fileio.export import ImagesToDirectoryExporter, SelectedImagesToDirectoryExporter
from beeref.widgets.settings import AnimationFormatWidget, SettingsDialog


@pytest.fixture
def animation_scene(qapp):
    """アニメーションアイテムを含むテストシーンを作成"""
    from beeref.scene import BeeGraphicsScene
    
    scene = BeeGraphicsScene(QUndoStack())
    
    # WebP用アニメーションアイテム
    frames_webp = []
    for i in range(3):
        img = QtGui.QImage(20, 20, QtGui.QImage.Format.Format_ARGB32)
        img.fill(QtGui.QColor(255, i * 80, 0))  # グラデーション
        frames_webp.append(img)
    
    webp_data = {'frames': frames_webp, 'delays': [100, 150, 200]}
    webp_item = BeeAnimatedPixmapItem(webp_data, filename='webp_test.gif')
    webp_item.save_id = 1
    scene.addItem(webp_item)
    
    # GIF用アニメーションアイテム
    frames_gif = []
    for i in range(2):
        img = QtGui.QImage(15, 15, QtGui.QImage.Format.Format_ARGB32)
        img.fill(QtGui.QColor(0, 255, i * 128))  # 異なるグラデーション
        frames_gif.append(img)
    
    gif_data = {'frames': frames_gif, 'delays': [80, 120]}
    gif_item = BeeAnimatedPixmapItem(gif_data, filename='gif_test.gif')
    gif_item.save_id = 2
    scene.addItem(gif_item)
    
    return scene, webp_item, gif_item


class TestSettingsToExportIntegration:
    """設定からエクスポートまでの統合テスト"""
    
    def test_settings_webp_to_export_workflow(self, tmpdir, animation_scene, settings, view):
        """設定変更→WebPエクスポートの完全なワークフロー"""
        scene, webp_item, gif_item = animation_scene
        
        # 1. 設定をWebPに変更
        settings.setValue('Items/animation_export_format', 'webp')
        assert settings.valueOrDefault('Items/animation_export_format') == 'webp'
        
        # 2. 設定ウィジェットで変更が反映されることを確認
        widget = AnimationFormatWidget()
        assert widget.buttons['webp'].isChecked() is True
        assert widget.buttons['gif'].isChecked() is False
        assert widget.title() == 'Animation Export Format: ✎'
        
        # 3. エクスポート実行
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        with patch.object(webp_item, 'to_animated_webp_bytes') as mock_webp, \
             patch.object(gif_item, 'to_animated_webp_bytes') as mock_webp2:
            
            mock_webp.return_value = (b'webp_data_1', 'webp')
            mock_webp2.return_value = (b'webp_data_2', 'webp')
            
            exporter.export()
            
            # 4. 両方のアイテムでWebPエクスポートが呼ばれることを確認
            mock_webp.assert_called_once_with(apply_crop=True)
            mock_webp2.assert_called_once_with(apply_crop=True)
        
        # 5. WebPファイルが作成されることを確認
        files = os.listdir(str(tmpdir))
        webp_files = [f for f in files if f.endswith('.webp')]
        assert len(webp_files) == 2
        assert '0001-webp_test.webp' in webp_files
        assert '0002-gif_test.webp' in webp_files
    
    def test_settings_gif_to_export_workflow(self, tmpdir, animation_scene, settings, view):
        """設定変更→GIFエクスポートの完全なワークフロー"""
        scene, webp_item, gif_item = animation_scene
        
        # 1. 設定をGIFに変更
        settings.setValue('Items/animation_export_format', 'gif')
        assert settings.valueOrDefault('Items/animation_export_format') == 'gif'
        
        # 2. 設定ウィジェットで変更が反映されることを確認
        widget = AnimationFormatWidget()
        assert widget.buttons['gif'].isChecked() is True
        assert widget.buttons['webp'].isChecked() is False
        assert widget.title() == 'Animation Export Format:'
        
        # 3. エクスポート実行
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        with patch.object(webp_item, 'to_animated_gif_bytes') as mock_gif, \
             patch.object(gif_item, 'to_animated_gif_bytes') as mock_gif2:
            
            mock_gif.return_value = (b'gif_data_1', 'gif')
            mock_gif2.return_value = (b'gif_data_2', 'gif')
            
            exporter.export()
            
            # 4. 両方のアイテムでGIFエクスポートが呼ばれることを確認
            mock_gif.assert_called_once_with(apply_crop=True)
            mock_gif2.assert_called_once_with(apply_crop=True)
        
        # 5. GIFファイルが作成されることを確認
        files = os.listdir(str(tmpdir))
        gif_files = [f for f in files if f.endswith('.gif')]
        assert len(gif_files) == 2
        assert '0001-webp_test.gif' in gif_files
        assert '0002-gif_test.gif' in gif_files
    
    def test_settings_change_realtime_effect(self, tmpdir, animation_scene, settings, view):
        """設定変更のリアルタイム効果確認"""
        scene, webp_item, gif_item = animation_scene
        
        # 最初はデフォルト（GIF）
        assert settings.valueOrDefault('Items/animation_export_format') == 'gif'
        
        # GIFエクスポート
        exporter1 = ImagesToDirectoryExporter(scene, str(tmpdir))
        with patch.object(webp_item, 'to_animated_gif_bytes') as mock_gif:
            mock_gif.return_value = (b'gif_data', 'gif')
            exporter1.export()
            mock_gif.assert_called_once()
        
        # 設定をWebPに変更
        settings.setValue('Items/animation_export_format', 'webp')
        
        # 新しいエクスポーターではWebPが使用される
        tmpdir2 = tempfile.mkdtemp()
        exporter2 = ImagesToDirectoryExporter(scene, tmpdir2)
        with patch.object(webp_item, 'to_animated_webp_bytes') as mock_webp:
            mock_webp.return_value = (b'webp_data', 'webp')
            exporter2.export()
            mock_webp.assert_called_once()
        
        # クリーンアップ
        import shutil
        shutil.rmtree(tmpdir2)


class TestGifWebpCoexistence:
    """GIFとWebP機能の共存テスト"""
    
    def test_gif_webp_methods_both_available(self, animation_scene):
        """GIFとWebPの両方のメソッドが利用可能であることを確認"""
        scene, webp_item, gif_item = animation_scene
        
        # 両方のメソッドが存在することを確認
        assert hasattr(webp_item, 'to_animated_gif_bytes')
        assert hasattr(webp_item, 'to_animated_webp_bytes')
        assert hasattr(gif_item, 'to_animated_gif_bytes')
        assert hasattr(gif_item, 'to_animated_webp_bytes')
        
        # 両方のメソッドが呼び出し可能であることを確認
        assert callable(webp_item.to_animated_gif_bytes)
        assert callable(webp_item.to_animated_webp_bytes)
        assert callable(gif_item.to_animated_gif_bytes)
        assert callable(gif_item.to_animated_webp_bytes)
    
    def test_gif_webp_export_consistency(self, animation_scene):
        """GIFとWebPエクスポートの一貫性確認"""
        scene, webp_item, gif_item = animation_scene
        
        # 同じアイテムから両形式でエクスポート
        gif_data, gif_format = webp_item.to_animated_gif_bytes()
        webp_data, webp_format = webp_item.to_animated_webp_bytes()
        
        # 両方とも成功することを確認
        assert gif_data is not None
        assert webp_data is not None
        assert gif_format == 'gif'
        assert webp_format == 'webp'
        
        # データが異なることを確認（異なる形式なので）
        assert gif_data != webp_data
    
    def test_format_switching_no_interference(self, tmpdir, animation_scene, settings):
        """形式切り替え時の相互干渉がないことを確認"""
        scene, webp_item, gif_item = animation_scene
        
        # GIF → WebP → GIF の順で切り替え
        formats = ['gif', 'webp', 'gif']
        expected_methods = ['to_animated_gif_bytes', 'to_animated_webp_bytes', 'to_animated_gif_bytes']
        
        for format_name, expected_method in zip(formats, expected_methods):
            settings.setValue('Items/animation_export_format', format_name)
            
            # エクスポート実行
            tmpdir_format = tempfile.mkdtemp()
            exporter = ImagesToDirectoryExporter(scene, tmpdir_format)
            
            # 対応するメソッドが呼ばれることを確認
            with patch.object(webp_item, expected_method) as mock_method:
                if format_name == 'gif':
                    mock_method.return_value = (b'gif_data', 'gif')
                else:
                    mock_method.return_value = (b'webp_data', 'webp')
                
                exporter.export()
                mock_method.assert_called_once_with(apply_crop=True)
            
            # クリーンアップ
            import shutil
            shutil.rmtree(tmpdir_format)
    
    def test_mixed_format_export_not_supported(self, tmpdir, animation_scene, settings):
        """混合形式エクスポートが適切に処理されることを確認"""
        # 注：現在の実装では、すべてのアニメーションアイテムが
        # 同じ形式でエクスポートされる（混合形式はサポートしない）
        scene, webp_item, gif_item = animation_scene
        
        # WebP設定でエクスポート
        settings.setValue('Items/animation_export_format', 'webp')
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        with patch.object(webp_item, 'to_animated_webp_bytes') as mock_webp1, \
             patch.object(gif_item, 'to_animated_webp_bytes') as mock_webp2:
            
            mock_webp1.return_value = (b'webp_data_1', 'webp')
            mock_webp2.return_value = (b'webp_data_2', 'webp')
            
            exporter.export()
            
            # 両方のアイテムで同じ形式（WebP）が使用される
            mock_webp1.assert_called_once()
            mock_webp2.assert_called_once()
        
        # すべて.webp拡張子で出力される
        files = os.listdir(str(tmpdir))
        webp_files = [f for f in files if f.endswith('.webp')]
        gif_files = [f for f in files if f.endswith('.gif')]
        assert len(webp_files) == 2
        assert len(gif_files) == 0


class TestSelectedItemsIntegration:
    """選択アイテムエクスポートの統合テスト"""
    
    def test_selected_items_webp_export_integration(self, tmpdir, animation_scene, settings, view):
        """選択アイテムのWebPエクスポート統合テスト"""
        scene, webp_item, gif_item = animation_scene
        
        # viewをシーンに関連付け（選択機能にビューが必要）
        view.setScene(scene)
        
        # WebP設定
        settings.setValue('Items/animation_export_format', 'webp')
        
        # 1つのアイテムのみ選択
        webp_item.setSelected(True)
        gif_item.setSelected(False)
        
        # 選択アイテムエクスポート
        exporter = SelectedImagesToDirectoryExporter(scene, str(tmpdir))
        
        with patch.object(webp_item, 'to_animated_webp_bytes') as mock_webp:
            mock_webp.return_value = (b'webp_data', 'webp')
            
            exporter.export()
            
            # 選択されたアイテムのみエクスポートされる
            mock_webp.assert_called_once_with(apply_crop=True)
        
        # 1つのWebPファイルのみ作成される
        files = os.listdir(str(tmpdir))
        webp_files = [f for f in files if f.endswith('.webp')]
        assert len(webp_files) == 1
        assert '0001-webp_test.webp' in webp_files
    
    def test_no_selection_export_integration(self, tmpdir, animation_scene, settings):
        """選択なしエクスポートの統合テスト"""
        scene, webp_item, gif_item = animation_scene
        
        # 両方のアイテムを非選択
        webp_item.setSelected(False)
        gif_item.setSelected(False)
        
        # 選択アイテムエクスポート
        exporter = SelectedImagesToDirectoryExporter(scene, str(tmpdir))
        exporter.export()
        
        # ファイルが作成されない
        files = os.listdir(str(tmpdir))
        assert len(files) == 0


class TestErrorHandlingIntegration:
    """エラーハンドリングの統合テスト"""
    
    def test_webp_export_error_graceful_handling(self, tmpdir, animation_scene, settings):
        """WebPエクスポートエラーの適切な処理"""
        scene, webp_item, gif_item = animation_scene
        
        # WebP設定
        settings.setValue('Items/animation_export_format', 'webp')
        
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        # WebPエクスポートでエラーが発生
        with patch.object(webp_item, 'to_animated_webp_bytes') as mock_webp, \
             patch.object(gif_item, 'to_animated_webp_bytes') as mock_webp2, \
             patch('beeref.fileio.export.logger') as mock_logger:
            
            mock_webp.return_value = (None, 'webp')  # エラーケース
            mock_webp2.return_value = (b'webp_data', 'webp')  # 正常ケース
            
            exporter.export()
            
            # エラーログが出力される
            mock_logger.warning.assert_called()
            
            # 正常なアイテムは処理される
            mock_webp2.assert_called_once()
        
        # 正常なアイテムのファイルのみ作成される
        files = os.listdir(str(tmpdir))
        webp_files = [f for f in files if f.endswith('.webp')]
        assert len(webp_files) == 1
    
    def test_settings_corruption_fallback(self, tmpdir, animation_scene, settings):
        """設定値破損時のフォールバック処理"""
        scene, webp_item, gif_item = animation_scene
        
        # 無効な設定値を設定
        settings.setValue('Items/animation_export_format', 'invalid_format')
        
        # バリデーションによりデフォルト値（gif）が返される
        assert settings.valueOrDefault('Items/animation_export_format') == 'gif'
        
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        with patch.object(webp_item, 'to_animated_gif_bytes') as mock_gif:
            mock_gif.return_value = (b'gif_data', 'gif')
            exporter.export()
            # デフォルトのGIF形式が使用される
            mock_gif.assert_called_once()


class TestPerformanceIntegration:
    """パフォーマンス統合テスト"""
    
    def test_large_scene_export_performance(self, tmpdir, settings, qapp):
        """大きなシーンでのエクスポートパフォーマンス"""
        from beeref.scene import BeeGraphicsScene
        import time
        
        # 大きなシーンを作成（多数のアニメーションアイテム）
        scene = BeeGraphicsScene(QUndoStack())
        items = []
        
        for i in range(10):  # 10個のアニメーションアイテム
            frames = []
            for j in range(3):
                img = QtGui.QImage(50, 50, QtGui.QImage.Format.Format_ARGB32)
                img.fill(QtGui.QColor(i * 25, j * 85, 100))
                frames.append(img)
            
            animation_data = {'frames': frames, 'delays': [100, 150, 200]}
            item = BeeAnimatedPixmapItem(animation_data, filename=f'item_{i}.gif')
            item.save_id = i + 1
            scene.addItem(item)
            items.append(item)
        
        # WebP設定
        settings.setValue('Items/animation_export_format', 'webp')
        
        # エクスポート実行時間を測定
        start_time = time.time()
        
        exporter = ImagesToDirectoryExporter(scene, str(tmpdir))
        
        # すべてのアイテムでWebPエクスポートをモック
        patches = []
        for item in items:
            patch_obj = patch.object(item, 'to_animated_webp_bytes')
            mock_webp = patch_obj.start()
            mock_webp.return_value = (b'webp_data', 'webp')
            patches.append(patch_obj)
        
        try:
            exporter.export()
            end_time = time.time()
            
            # 処理時間が合理的範囲内であることを確認（30秒以内）
            elapsed_time = end_time - start_time
            assert elapsed_time < 30.0, f"Export took too long: {elapsed_time} seconds"
            
            # すべてのアイテムが処理されることを確認
            files = os.listdir(str(tmpdir))
            webp_files = [f for f in files if f.endswith('.webp')]
            assert len(webp_files) == 10
            
        finally:
            # モックをクリーンアップ
            for patch_obj in patches:
                patch_obj.stop()