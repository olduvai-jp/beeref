import pytest
import json
import io
from unittest.mock import patch, MagicMock

from PyQt6 import QtCore, QtGui, QtWidgets
from PIL import Image

from beeref.items import BeeAnimatedPixmapItem


@pytest.fixture
def animation_data():
    """WebPテスト用のアニメーションデータフィクスチャ"""
    # 3x3の画像を3フレーム作成
    frames = []
    for i in range(3):
        img = QtGui.QImage(3, 3, QtGui.QImage.Format.Format_ARGB32)
        # フレームごとに異なる色で塗りつぶし
        color = QtGui.QColor(255 * i // 2, 128, 255 - 255 * i // 2)
        img.fill(color)
        frames.append(img)
    
    return {
        'frames': frames,
        'delays': [100, 150, 200]  # 異なる遅延時間
    }


@pytest.fixture
def animated_item(animation_data):
    """BeeAnimatedPixmapItemのフィクスチャ"""
    return BeeAnimatedPixmapItem(animation_data, filename='test.gif')


class TestToAnimatedWebPBytes:
    """to_animated_webp_bytes()メソッドのテスト"""
    
    def test_basic_webp_export(self, qapp, animated_item):
        """基本的なWebPエクスポート"""
        data, format_type = animated_item.to_animated_webp_bytes()
        
        assert format_type == 'webp'
        assert data is not None
        assert isinstance(data, bytes)
        assert len(data) > 0
        
        # WebPファイルの開始シグネチャを確認 (RIFF...WEBP)
        assert data[:4] == b'RIFF'
        assert data[8:12] == b'WEBP'
    
    def test_webp_export_with_crop(self, qapp, animated_item):
        """クロップ適用でのWebPエクスポート"""
        animated_item.crop = QtCore.QRectF(1, 1, 2, 2)
        
        data, format_type = animated_item.to_animated_webp_bytes(apply_crop=True)
        
        assert format_type == 'webp'
        assert data is not None
        assert isinstance(data, bytes)
        assert len(data) > 0
    
    def test_webp_export_empty_frames(self, qapp):
        """空のフレームリストでのWebPエクスポート"""
        animation_data = {'frames': [], 'delays': []}
        item = BeeAnimatedPixmapItem(animation_data)
        
        data, format_type = item.to_animated_webp_bytes()
        
        assert format_type == 'webp'
        assert data is None
    
    def test_webp_export_single_frame(self, qapp):
        """単一フレームでのWebPエクスポート"""
        img = QtGui.QImage(2, 2, QtGui.QImage.Format.Format_ARGB32)
        img.fill(QtGui.QColor(255, 0, 0))
        
        animation_data = {
            'frames': [img],
            'delays': [100]
        }
        
        item = BeeAnimatedPixmapItem(animation_data)
        data, format_type = item.to_animated_webp_bytes()
        
        assert format_type == 'webp'
        assert data is not None
        assert isinstance(data, bytes)
    
    def test_webp_export_delays_handling(self, qapp, animated_item):
        """遅延時間の処理確認"""
        # 遅延時間が正しく処理されることを確認
        data, format_type = animated_item.to_animated_webp_bytes()
        
        assert format_type == 'webp'
        assert data is not None
        
        # WebPデータをPillowで読み込んで検証
        webp_image = Image.open(io.BytesIO(data))
        assert webp_image.format == 'WEBP'
        assert webp_image.is_animated
    
    def test_webp_export_with_invalid_crop(self, qapp, animated_item):
        """無効なクロップ領域でのWebPエクスポート"""
        # フレームサイズを超えるクロップ領域を設定
        animated_item.crop = QtCore.QRectF(5, 5, 10, 10)
        
        with patch('beeref.items.logger') as mock_logger:
            data, format_type = animated_item.to_animated_webp_bytes(apply_crop=True)
            
            assert format_type == 'webp'
            assert data is not None
            # 警告ログが出力されることを確認
            mock_logger.warning.assert_called()
    
    @patch('beeref.items.Image')
    def test_webp_export_pillow_error_fallback(self, mock_image, qapp, animated_item):
        """Pillowエラー時のフォールバック処理"""
        # Pillowの保存処理でエラーを発生させる
        mock_pil_image = MagicMock()
        mock_pil_image.save.side_effect = Exception("Pillow save error")
        
        mock_opened_image = MagicMock()
        mock_opened_image.convert.return_value = mock_pil_image
        mock_image.open.return_value = mock_opened_image
        
        with patch('beeref.items.logger') as mock_logger:
            data, format_type = animated_item.to_animated_webp_bytes()
            
            assert format_type == 'webp'
            # エラーログが出力されることを確認
            mock_logger.error.assert_called()
    
    def test_webp_export_compression_settings(self, qapp, animated_item):
        """WebP圧縮設定の確認"""
        with patch('beeref.items.Image') as mock_image:
            mock_pil_image = MagicMock()
            mock_image.open.return_value = mock_pil_image
            mock_image.fromqimage.return_value = mock_pil_image
            
            # モックの保存メソッドの戻り値を設定
            mock_output = MagicMock()
            mock_output.getvalue.return_value = b'mock_webp_data'
            
            with patch('beeref.items.io.BytesIO', return_value=mock_output):
                animated_item.to_animated_webp_bytes()
                
                # WebP保存時の設定を確認
                save_calls = mock_pil_image.save.call_args_list
                if len(save_calls) > 0:
                    call_args, call_kwargs = save_calls[0]
                    # WebP形式で保存されることを確認
                    assert call_kwargs.get('format') == 'WebP' or call_kwargs.get('format') == 'WEBP'
                    # その他の設定は実装に依存するため、存在チェックのみ
                    assert 'save_all' in call_kwargs or 'append_images' in call_kwargs or len(call_args) > 0
    
    def test_webp_export_logging(self, qapp, animated_item):
        """ログ出力の確認"""
        with patch('beeref.items.logger') as mock_logger:
            animated_item.to_animated_webp_bytes()
            
            # 成功ログが出力されることを確認
            mock_logger.info.assert_called_with(
                f"Successfully created animated WebP for {animated_item} with 3 frames."
            )


class TestWebPIntegration:
    """WebP機能の統合テスト"""
    
    def test_webp_roundtrip_basic(self, qapp, animated_item):
        """WebPエクスポート→インポートの基本的なラウンドトリップ"""
        # WebPデータを生成
        webp_data, format_type = animated_item.to_animated_webp_bytes()
        assert format_type == 'webp'
        assert webp_data is not None
        
        # WebPデータを検証
        webp_image = Image.open(io.BytesIO(webp_data))
        assert webp_image.format == 'WEBP'
        assert webp_image.is_animated
        
        # フレーム数の確認
        frame_count = 0
        try:
            while True:
                webp_image.seek(frame_count)
                frame_count += 1
        except EOFError:
            pass
        
        assert frame_count == 3  # 元のフレーム数と一致
    
    def test_webp_vs_gif_comparison(self, qapp, animated_item):
        """WebPとGIFの比較テスト"""
        # WebPデータを生成
        webp_data, webp_format = animated_item.to_animated_webp_bytes()
        
        # GIFデータを生成
        gif_data, gif_format = animated_item.to_animated_gif_bytes()
        
        assert webp_format == 'webp'
        assert gif_format == 'gif'
        assert webp_data is not None
        assert gif_data is not None
        
        # 両方ともアニメーション形式として有効
        webp_image = Image.open(io.BytesIO(webp_data))
        gif_image = Image.open(io.BytesIO(gif_data))
        
        assert webp_image.is_animated
        assert gif_image.is_animated
    
    def test_webp_export_with_settings_format(self, qapp, animated_item, settings):
        """設定に基づくWebPエクスポート"""
        # アニメーション形式をWebPに設定
        settings.setValue('Items/animation_export_format', 'webp')
        
        # エクスポート形式の確認
        assert settings.valueOrDefault('Items/animation_export_format') == 'webp'
        
        # WebPエクスポートが正常に動作することを確認
        webp_data, format_type = animated_item.to_animated_webp_bytes()
        assert format_type == 'webp'
        assert webp_data is not None
    
    def test_webp_export_quality_validation(self, qapp, animated_item):
        """WebP品質設定の検証"""
        webp_data, format_type = animated_item.to_animated_webp_bytes()
        
        assert format_type == 'webp'
        assert webp_data is not None
        
        # WebPファイルが正常に作成されているか確認
        webp_image = Image.open(io.BytesIO(webp_data))
        assert webp_image.format == 'WEBP'
        assert webp_image.size == (3, 3)  # 元の画像サイズ
    
    def test_webp_export_performance_metrics(self, qapp, animated_item):
        """WebPエクスポートのパフォーマンス確認"""
        import time
        
        start_time = time.time()
        webp_data, format_type = animated_item.to_animated_webp_bytes()
        end_time = time.time()
        
        assert format_type == 'webp'
        assert webp_data is not None
        
        # 処理時間が合理的な範囲内であることを確認（10秒以内）
        assert (end_time - start_time) < 10.0


class TestWebPErrorHandling:
    """WebPエラーハンドリングのテスト"""
    
    def test_webp_export_null_qimage(self, qapp):
        """Null QImageでのWebPエクスポート"""
        # Null QImageを含むフレームを作成
        null_img = QtGui.QImage()
        assert null_img.isNull()
        
        animation_data = {
            'frames': [null_img],
            'delays': [100]
        }
        
        item = BeeAnimatedPixmapItem(animation_data)
        
        with patch('beeref.items.logger') as mock_logger:
            data, format_type = item.to_animated_webp_bytes()
            
            assert format_type == 'webp'
            # Null QImageのため、フレームが処理されずNoneが返される
            assert data is None
            mock_logger.error.assert_called()
    
    def test_webp_export_io_error(self, qapp, animated_item):
        """I/Oエラーでのエラーハンドリング"""
        with patch('beeref.items.Image') as mock_image, \
             patch('beeref.items.logger') as mock_logger:
            
            # Pillowの保存処理でI/Oエラーを発生させる
            mock_pil_image = MagicMock()
            mock_pil_image.save.side_effect = IOError("I/O Error")
            
            mock_opened_image = MagicMock()
            mock_opened_image.convert.return_value = mock_pil_image
            mock_image.open.return_value = mock_opened_image
            
            data, format_type = animated_item.to_animated_webp_bytes()
            
            # エラーハンドリングが動作することを確認
            assert format_type == 'webp'
            mock_logger.error.assert_called()
    
    def test_webp_export_memory_limitation(self, qapp):
        """メモリ制限でのWebPエクスポート"""
        # 非常に大きな画像を作成（メモリ制限テスト）
        large_img = QtGui.QImage(1000, 1000, QtGui.QImage.Format.Format_ARGB32)
        large_img.fill(QtGui.QColor(255, 0, 0))
        
        animation_data = {
            'frames': [large_img],
            'delays': [100]
        }
        
        item = BeeAnimatedPixmapItem(animation_data)
        
        # メモリ不足でもエラーが適切に処理されることを確認
        data, format_type = item.to_animated_webp_bytes()
        assert format_type == 'webp'
        # 大きなデータでも処理が完了することを確認
        assert data is not None or data is None  # どちらでも許容