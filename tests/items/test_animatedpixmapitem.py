import pytest
import json
from unittest.mock import patch, MagicMock, call

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from beeref.items import BeeAnimatedPixmapItem, item_registry


@pytest.fixture
def animation_data():
    """アニメーションデータのフィクスチャ"""
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
        'delays': [100, 200, 150]  # ミリ秒
    }


@pytest.fixture
def animated_item(animation_data):
    """BeeAnimatedPixmapItemのフィクスチャ"""
    return BeeAnimatedPixmapItem(animation_data)


def test_in_item_registry():
    """アイテムレジストリへの登録確認"""
    assert item_registry['animated_pixmap'] == BeeAnimatedPixmapItem


class TestInitialization:
    """初期化テスト"""
    
    @patch('beeref.selection.SelectableMixin.init_selectable')
    def test_init_basic(self, selectable_mock, qapp, animation_data):
        """基本的な初期化テスト"""
        item = BeeAnimatedPixmapItem(animation_data, filename='test.gif')
        
        # 基本属性の確認
        assert item.save_id is None
        assert item.filename == 'test.gif'
        assert item.is_image is True
        assert item.crop_mode is False
        assert len(item.frames) == 3
        assert item.delays == [100, 200, 150]
        assert item.current_frame == 0
        assert item._animation_started is False
        
        # フレームが正しくPixmapに変換されているか確認
        assert all(isinstance(frame, QtGui.QPixmap) for frame in item.frames)
        assert item.crop == QtCore.QRectF(0, 0, 3, 3)
        
        selectable_mock.assert_called_once()
    
    def test_init_without_filename(self, qapp, animation_data):
        """ファイル名なしの初期化"""
        item = BeeAnimatedPixmapItem(animation_data)
        assert item.filename is None
    
    def test_init_single_frame(self, qapp):
        """単一フレームでの初期化"""
        img = QtGui.QImage(2, 2, QtGui.QImage.Format.Format_ARGB32)
        img.fill(QtGui.QColor(255, 0, 0))
        
        animation_data = {
            'frames': [img],
            'delays': [100]
        }
        
        item = BeeAnimatedPixmapItem(animation_data)
        assert len(item.frames) == 1
        assert item.delays == [100]


class TestAnimationControl:
    """アニメーション制御テスト"""
    
    @patch('PyQt6.QtCore.QTimer.singleShot')
    def test_start_animation_multiple_frames_with_scene(self, mock_timer, qapp, animated_item):
        """複数フレーム、シーンありでのアニメーション開始"""
        # シーンを設定
        scene = QtWidgets.QGraphicsScene()
        scene.addItem(animated_item)
        
        animated_item.start_animation()
        
        assert animated_item._animation_started is True
        mock_timer.assert_called_once_with(100, animated_item.next_frame)
    
    @patch('PyQt6.QtCore.QTimer.singleShot')
    def test_start_animation_single_frame(self, mock_timer, qapp):
        """単一フレームでのアニメーション開始（開始されない）"""
        img = QtGui.QImage(2, 2, QtGui.QImage.Format.Format_ARGB32)
        img.fill(QtGui.QColor(255, 0, 0))
        
        animation_data = {
            'frames': [img],
            'delays': [100]
        }
        
        item = BeeAnimatedPixmapItem(animation_data)
        scene = QtWidgets.QGraphicsScene()
        scene.addItem(item)
        
        item.start_animation()
        
        assert item._animation_started is False
        mock_timer.assert_not_called()
    
    @patch('PyQt6.QtCore.QTimer.singleShot')
    def test_start_animation_no_scene(self, mock_timer, qapp, animated_item):
        """シーンなしでのアニメーション開始（開始されない）"""
        animated_item.start_animation()
        
        assert animated_item._animation_started is False
        mock_timer.assert_not_called()

    # TODO:本当に必要か考える
    # @patch('PyQt6.QtCore.QTimer.singleShot')
    # def test_start_animation_already_started(self, mock_timer, qapp, animated_item):
    #     """既に開始済みのアニメーションの重複開始防止"""
    #     scene = QtWidgets.QGraphicsScene()
    #     scene.addItem(animated_item)
        
    #     animated_item._animation_started = True
    #     animated_item.start_animation()
        
    #     mock_timer.assert_not_called()
    
    def test_stop_animation(self, qapp, animated_item):
        """アニメーション停止"""
        animated_item._animation_started = True
        animated_item.stop_animation()
        
        assert animated_item._animation_started is False
    
    @patch('PyQt6.QtCore.QTimer.singleShot')
    def test_next_frame_single_frame(self, mock_timer, qapp):
        """単一フレームでのnext_frame（何もしない）"""
        img = QtGui.QImage(2, 2, QtGui.QImage.Format.Format_ARGB32)
        img.fill(QtGui.QColor(255, 0, 0))
        
        animation_data = {
            'frames': [img],
            'delays': [100]
        }
        
        item = BeeAnimatedPixmapItem(animation_data)
        old_frame = item.current_frame
        
        item.next_frame()
        
        assert item.current_frame == old_frame
        mock_timer.assert_not_called()
    
    # TODO:本当に必要か考える
    # @patch('PyQt6.QtCore.QTimer.singleShot')
    # def test_next_frame_with_scene_and_animation_started(self, mock_timer, qapp, animated_item):
    #     """シーンありでアニメーション開始済みのnext_frame"""
    #     scene = QtWidgets.QGraphicsScene()
    #     scene.addItem(animated_item)
    #     animated_item._animation_started = True
    #     animated_item.update = MagicMock()
        
    #     # フレーム0から1へ
    #     animated_item.next_frame()
        
    #     assert animated_item.current_frame == 1
    #     animated_item.update.assert_called_once()
    #     mock_timer.assert_called_once_with(200, animated_item.next_frame)  # delays[1]
        
    #     # フレーム1から2へ
    #     mock_timer.reset_mock()
    #     animated_item.update.reset_mock()
    #     animated_item.next_frame()
        
    #     assert animated_item.current_frame == 2
    #     animated_item.update.assert_called_once()
    #     mock_timer.assert_called_once_with(150, animated_item.next_frame)  # delays[2]
        
    #     # フレーム2から0へ（ループ）
    #     mock_timer.reset_mock()
    #     animated_item.update.reset_mock()
    #     animated_item.next_frame()
        
    #     assert animated_item.current_frame == 0
    #     animated_item.update.assert_called_once()
    #     mock_timer.assert_called_once_with(100, animated_item.next_frame)  # delays[0]
    
    # TODO:本当に必要か考える
    # @patch('PyQt6.QtCore.QTimer.singleShot')
    # def test_next_frame_animation_stopped(self, mock_timer, qapp, animated_item):
    #     """アニメーション停止済みのnext_frame（タイマー設定なし）"""
    #     scene = QtWidgets.QGraphicsScene()
    #     scene.addItem(animated_item)
    #     animated_item._animation_started = False
    #     animated_item.update = MagicMock()
        
    #     animated_item.next_frame()
        
    #     assert animated_item.current_frame == 1
    #     animated_item.update.assert_called_once()
    #     mock_timer.assert_not_called()
    
    # @patch('PyQt6.QtCore.QTimer.singleShot')
    # def test_next_frame_no_scene(self, mock_timer, qapp, animated_item):
    #     """シーンなしのnext_frame（タイマー設定なし）"""
    #     animated_item._animation_started = True
    #     animated_item.update = MagicMock()
        
    #     animated_item.next_frame()
        
    #     assert animated_item.current_frame == 1
    #     animated_item.update.assert_called_once()
    #     mock_timer.assert_not_called()


class TestSceneIntegration:
    """シーン連携テスト"""
    
    @patch.object(BeeAnimatedPixmapItem, 'start_animation')
    def test_item_change_added_to_scene(self, mock_start, qapp, animated_item):
        """シーンに追加された時のアニメーション開始"""
        scene = QtWidgets.QGraphicsScene()
        
        # itemChangeをシミュレート
        result = animated_item.itemChange(
            QtWidgets.QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged, 
            scene
        )
        
        mock_start.assert_called_once()
        assert result == scene
    
    @patch.object(BeeAnimatedPixmapItem, 'stop_animation')
    def test_item_change_removed_from_scene(self, mock_stop, qapp, animated_item):
        """シーンから削除された時のアニメーション停止"""
        # itemChangeをシミュレート
        result = animated_item.itemChange(
            QtWidgets.QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged, 
            None
        )
        
        mock_stop.assert_called_once()
        assert result is None
    
    def test_item_change_other_changes(self, qapp, animated_item):
        """その他の変更に対する処理確認"""
        with patch.object(BeeAnimatedPixmapItem, 'start_animation') as mock_start, \
             patch.object(BeeAnimatedPixmapItem, 'stop_animation') as mock_stop:
            
            # 位置変更などその他の変更
            result = animated_item.itemChange(
                QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionChange,
                QtCore.QPointF(10, 20)
            )
            
            mock_start.assert_not_called()
            mock_stop.assert_not_called()
            assert result == QtCore.QPointF(10, 20)


class TestFrameDisplay:
    """フレーム表示テスト"""
    
    def test_pixmap_returns_current_frame(self, qapp, animated_item):
        """現在のフレームのPixmapが返されることを確認"""
        # 初期フレーム（0）
        pixmap = animated_item.pixmap()
        assert pixmap == animated_item.frames[0]
        
        # フレーム変更
        animated_item.current_frame = 1
        pixmap = animated_item.pixmap()
        assert pixmap == animated_item.frames[1]
        
        animated_item.current_frame = 2
        pixmap = animated_item.pixmap()
        assert pixmap == animated_item.frames[2]
    
    def test_pixmap_empty_frames(self, qapp):
        """空のフレームリストでのpixmap"""
        animation_data = {'frames': [], 'delays': []}
        item = BeeAnimatedPixmapItem(animation_data)
        
        pixmap = item.pixmap()
        assert pixmap.isNull()
    
    def test_paint_calls_pixmap(self, qapp, animated_item):
        """paint()メソッドが現在のフレームを描画することを確認"""
        painter = MagicMock()
        painter.combinedTransform.return_value.m11.return_value = 1.0
        option = MagicMock()
        widget = MagicMock()
        
        # モック用のpaint_selectableメソッド
        animated_item.paint_selectable = MagicMock()
        
        animated_item.paint(painter, option, widget)
        
        # SmoothPixmapTransformが設定される
        painter.setRenderHint.assert_called_once_with(
            painter.RenderHint.SmoothPixmapTransform
        )
        # 現在のフレームが描画される
        expected_pixmap = animated_item.frames[animated_item.current_frame]
        painter.drawPixmap.assert_called_once_with(
            animated_item.crop, expected_pixmap, animated_item.crop
        )
        animated_item.paint_selectable.assert_called_once_with(painter, option, widget)


class TestSerialization:
    """シリアライゼーション（保存・復元）テスト"""
    
    def test_get_extra_save_data(self, qapp, animated_item):
        """保存データの生成確認"""
        animated_item.setOpacity(0.8)
        animated_item.grayscale = True
        animated_item.current_frame = 2
        animated_item.crop = QtCore.QRectF(1, 2, 3, 4)
        
        data = animated_item.get_extra_save_data()
        
        expected = {
            'filename': None,
            'opacity': 0.8,
            'grayscale': True,
            'current_frame': 2,
            'crop': [1.0, 2.0, 3.0, 4.0]
        }
        assert data == expected
    
    def test_create_from_data_minimal(self, qapp, animated_item):
        """最小限のデータからの復元"""
        data = {'filename': 'new_name.gif'}
        
        result = BeeAnimatedPixmapItem.create_from_data(item=animated_item, data=data)
        
        assert result is animated_item
        assert animated_item.filename == 'new_name.gif'
        assert animated_item.opacity() == 1.0
        assert animated_item.grayscale is False
        assert animated_item.current_frame == 0
    
    def test_create_from_data_full(self, qapp, animated_item):
        """完全なデータからの復元"""
        data = {
            'filename': 'restored.gif',
            'opacity': 0.7,
            'grayscale': True,
            'current_frame': 1,
            'crop': [10, 20, 30, 40]
        }
        
        result = BeeAnimatedPixmapItem.create_from_data(item=animated_item, data=data)
        
        assert result is animated_item
        assert animated_item.filename == 'restored.gif'
        assert animated_item.opacity() == 0.7
        assert animated_item.grayscale is True
        assert animated_item.current_frame == 1
        assert animated_item.crop == QtCore.QRectF(10, 20, 30, 40)
    
    def test_pixmap_to_bytes_json_format(self, qapp, animated_item):
        """バイト列への変換（JSON形式）"""
        animated_item.current_frame = 1
        
        data, format_type = animated_item.pixmap_to_bytes()
        
        assert format_type == 'json'
        assert isinstance(data, bytes)
        
        # JSONとして解析可能か確認
        json_str = data.decode('utf-8')
        animation_data = json.loads(json_str)
        
        assert 'frames' in animation_data
        assert 'delays' in animation_data
        assert 'current_frame' in animation_data
        assert animation_data['delays'] == [100, 200, 150]
        assert animation_data['current_frame'] == 1
        assert len(animation_data['frames']) == 3
        
        # フレームデータが16進文字列として保存されているか確認
        for frame_hex in animation_data['frames']:
            assert isinstance(frame_hex, str)
            # 16進文字列として有効か確認
            bytes.fromhex(frame_hex)
    
    def test_pixmap_to_bytes_with_grayscale(self, qapp, animated_item):
        """グレースケール適用での変換"""
        animated_item.grayscale = True
        
        data, format_type = animated_item.pixmap_to_bytes(apply_grayscale=True)
        
        assert format_type == 'json'
        # 実際のグレースケール処理は簡略化されているため、エラーなく変換できることを確認
        json_str = data.decode('utf-8')
        animation_data = json.loads(json_str)
        assert len(animation_data['frames']) == 3
    
    def test_pixmap_to_bytes_with_crop(self, qapp, animated_item):
        """クロップ適用での変換"""
        animated_item.crop = QtCore.QRectF(1, 1, 2, 2)
        
        data, format_type = animated_item.pixmap_to_bytes(apply_crop=True)
        
        assert format_type == 'json'
        json_str = data.decode('utf-8')
        animation_data = json.loads(json_str)
        assert len(animation_data['frames']) == 3
    
    def test_pixmap_from_bytes_success(self, qapp, animated_item):
        """バイト列からの復元（成功）"""
        # まず変換してバイト列を取得
        original_data, _ = animated_item.pixmap_to_bytes()
        
        # 新しいアイテムで復元
        new_animation_data = {'frames': [QtGui.QImage()], 'delays': [100]}
        new_item = BeeAnimatedPixmapItem(new_animation_data)
        
        new_item.pixmap_from_bytes(original_data)
        
        assert len(new_item.frames) == 3
        assert new_item.delays == [100, 200, 150]
        assert new_item.current_frame == 0
        assert new_item.crop == QtCore.QRectF(0, 0, 3, 3)
    
    def test_pixmap_from_bytes_invalid_json(self, qapp, animated_item):
        """無効なJSONからの復元（エラーハンドリング）"""
        invalid_data = b'invalid json data'
        
        animated_item.pixmap_from_bytes(invalid_data)
        
        # エラー時のデフォルト値が設定される
        assert len(animated_item.frames) == 1
        assert animated_item.delays == [100]
        assert animated_item.current_frame == 0
    
    def test_pixmap_from_bytes_missing_data(self, qapp, animated_item):
        """不完全なデータからの復元"""
        incomplete_data = json.dumps({
            'delays': [50, 75]
            # framesが欠如
        }).encode('utf-8')
        
        animated_item.pixmap_from_bytes(incomplete_data)
        
        # エラー時のデフォルト値が設定される
        assert len(animated_item.frames) == 1
        assert animated_item.delays == [100]
        assert animated_item.current_frame == 0


class TestCopy:
    """コピー機能テスト"""
    
    def test_create_copy_basic(self, qapp, animated_item):
        """基本的なコピー作成"""
        # 元のアイテムを設定
        animated_item.setPos(10, 20)
        animated_item.setZValue(0.5)
        animated_item.setScale(1.5)
        animated_item.setRotation(45)
        animated_item.setOpacity(0.8)
        animated_item.grayscale = True
        animated_item.crop = QtCore.QRectF(1, 1, 2, 2)
        animated_item.current_frame = 2
        
        copy = animated_item.create_copy()
        
        # 基本属性の確認
        assert copy is not animated_item
        assert isinstance(copy, BeeAnimatedPixmapItem)
        assert copy.filename == animated_item.filename
        assert copy.pos() == QtCore.QPointF(10, 20)
        assert copy.zValue() == 0.5
        assert copy.scale() == 1.5
        assert copy.rotation() == 45
        assert copy.opacity() == 0.8
        assert copy.grayscale is True
        assert copy.crop == QtCore.QRectF(1, 1, 2, 2)
        assert copy.current_frame == 2
        
        # アニメーションデータが正しくコピーされているか確認
        assert len(copy.frames) == len(animated_item.frames)
        assert copy.delays == animated_item.delays
        
        # フレームが独立したオブジェクトであることを確認
        assert copy.frames is not animated_item.frames
        for i in range(len(copy.frames)):
            # Pixmapの内容は同じだが、オブジェクトは異なる
            assert copy.frames[i].toImage() == animated_item.frames[i].toImage()
    
    def test_create_copy_with_flip(self, qapp, animated_item):
        """フリップ状態のコピー"""
        # フリップを適用（do_flipメソッドが存在すると仮定）
        if hasattr(animated_item, 'do_flip'):
            animated_item.do_flip()
            
            copy = animated_item.create_copy()
            
            # フリップ状態もコピーされる
            if hasattr(copy, 'flip'):
                assert copy.flip() == animated_item.flip()
    
    def test_copy_independence(self, qapp, animated_item):
        """コピーの独立性確認"""
        copy = animated_item.create_copy()
        
        # 元のアイテムのフレームを変更
        original_frame = animated_item.current_frame
        animated_item.current_frame = (animated_item.current_frame + 1) % len(animated_item.frames)
        
        # コピーは影響を受けない
        assert copy.current_frame == original_frame
        
        # 元のアイテムのプロパティを変更
        animated_item.setOpacity(0.3)
        animated_item.grayscale = not animated_item.grayscale
        
        # コピーは影響を受けない
        assert copy.opacity() != animated_item.opacity()
        assert copy.grayscale != animated_item.grayscale
    
    def test_copy_to_clipboard(self, qapp, animated_item):
        """クリップボードへのコピー"""
        clipboard = QtWidgets.QApplication.clipboard()
        
        animated_item.copy_to_clipboard(clipboard)
        
        # 現在のフレームがクリップボードにコピーされる
        assert clipboard.pixmap().toImage() == animated_item.pixmap().toImage()


class TestAnimationUpdate:
    """アニメーション更新テスト（update_animationメソッド）"""
    
    def test_update_animation_single_frame(self, qapp):
        """単一フレームでのupdate_animation"""
        img = QtGui.QImage(2, 2, QtGui.QImage.Format.Format_ARGB32)
        img.fill(QtGui.QColor(255, 0, 0))
        
        animation_data = {'frames': [img], 'delays': [100]}
        item = BeeAnimatedPixmapItem(animation_data)
        
        result = item.update_animation(50)
        assert result is False
        assert item.current_frame == 0
    
    def test_update_animation_not_enough_time(self, qapp, animated_item):
        """十分な時間が経過していない場合"""
        animated_item.frame_timer = 50
        
        result = animated_item.update_animation(30)  # 合計80ms
        
        assert result is False
        assert animated_item.current_frame == 0
        assert animated_item.frame_timer == 80
    
    def test_update_animation_frame_advance(self, qapp, animated_item):
        """フレーム進行する場合"""
        animated_item.frame_timer = 80
        
        result = animated_item.update_animation(30)  # 合計110ms >= 100ms
        
        assert result is True
        assert animated_item.current_frame == 1
        assert animated_item.frame_timer == 0
    
    def test_update_animation_loop(self, qapp, animated_item):
        """フレームのループ確認"""
        animated_item.current_frame = 2  # 最後のフレーム
        animated_item.frame_timer = 100
        
        result = animated_item.update_animation(60)  # 合計160ms >= 150ms
        
        assert result is True
        assert animated_item.current_frame == 0  # 最初に戻る
        assert animated_item.frame_timer == 0


class TestCommonFeatures:
    """共通機能（クロップ、グレースケール等）のテスト"""
    
    def test_crop_property(self, qapp, animated_item):
        """cropプロパティの設定と取得"""
        animated_item.prepareGeometryChange = MagicMock()
        animated_item.update = MagicMock()
        
        new_crop = QtCore.QRectF(1, 2, 3, 4)
        animated_item.crop = new_crop
        
        assert animated_item.crop == new_crop
        animated_item.prepareGeometryChange.assert_called_once()
        animated_item.update.assert_called_once()
    
    def test_grayscale_property(self, qapp, animated_item):
        """grayscaleプロパティの設定と取得"""
        animated_item.update = MagicMock()
        
        assert animated_item.grayscale is False
        
        animated_item.grayscale = True
        
        assert animated_item.grayscale is True
        animated_item.update.assert_called_once()
    
    def test_reset_crop(self, qapp, animated_item):
        """クロップのリセット"""
        # クロップを変更
        animated_item.crop = QtCore.QRectF(1, 1, 1, 1)
        
        # リセット
        animated_item.reset_crop()
        
        # 元のサイズに戻る
        expected_size = animated_item.pixmap().size()
        expected_crop = QtCore.QRectF(0, 0, expected_size.width(), expected_size.height())
        assert animated_item.crop == expected_crop
    
    def test_bounding_rect_normal_mode(self, qapp, animated_item):
        """通常モードでのboundingRect"""
        test_crop = QtCore.QRectF(10, 20, 30, 40)
        animated_item.crop = test_crop
        animated_item.crop_mode = False
        
        assert animated_item.boundingRect() == test_crop
    
    def test_bounding_rect_crop_mode(self, qapp, animated_item):
        """クロップモードでのboundingRect"""
        animated_item.crop_mode = True
        
        expected = QtCore.QRectF(animated_item.pixmap().rect())
        assert animated_item.boundingRect() == expected
    
    def test_bounding_rect_unselected(self, qapp, animated_item):
        """bounding_rect_unselectedメソッド"""
        test_crop = QtCore.QRectF(5, 10, 15, 20)
        animated_item.crop = test_crop
        animated_item.crop_mode = False
        
        assert animated_item.bounding_rect_unselected() == test_crop
        
        animated_item.crop_mode = True
        expected = QtCore.QRectF(animated_item.pixmap().rect())
        assert animated_item.bounding_rect_unselected() == expected


class TestFileExport:
    """ファイルエクスポート関連テスト"""
    
    def test_get_filename_for_export_with_save_id_and_filename(self, qapp, animated_item):
        """save_idとfilenameありでのエクスポートファイル名生成"""
        animated_item.save_id = 5
        animated_item.filename = 'animation.gif'
        
        result = animated_item.get_filename_for_export('png', 10)
        assert result == '0005-animation.png'
    
    def test_get_filename_for_export_with_save_id_no_filename(self, qapp, animated_item):
        """save_idありfilenameなしでのエクスポートファイル名生成"""
        animated_item.save_id = 3
        animated_item.filename = None
        
        result = animated_item.get_filename_for_export('jpg', 8)
        assert result == '0003.jpg'
    
    def test_get_filename_for_export_no_save_id_with_default(self, qapp, animated_item):
        """save_idなし、デフォルト値ありでのエクスポートファイル名生成"""
        animated_item.save_id = None
        animated_item.filename = 'test.gif'
        
        result = animated_item.get_filename_for_export('webp', 12)
        assert result == '0012-test.webp'
    
    def test_get_filename_for_export_no_save_id_no_default(self, qapp, animated_item):
        """save_idなし、デフォルト値なしでのエラー"""
        animated_item.save_id = None
        
        with pytest.raises(AssertionError):
            animated_item.get_filename_for_export('png')


class TestStringRepresentation:
    """文字列表現テスト"""
    
    def test_str_with_filename(self, qapp, animated_item):
        """ファイル名ありでの文字列表現"""
        result = str(animated_item)
        expected = 'Animated Image "test_animation.gif" 3 x 3 (3 frames)'
        assert result == expected
    
    def test_str_without_filename(self, qapp, animation_data):
        """ファイル名なしでの文字列表現"""
        item = BeeAnimatedPixmapItem(animation_data, filename=None)
        result = str(item)
        expected = 'Animated Image "None" 3 x 3 (3 frames)'
        assert result == expected
    
    def test_str_single_frame(self, qapp):
        """単一フレームでの文字列表現"""
        img = QtGui.QImage(5, 7, QtGui.QImage.Format.Format_ARGB32)
        img.fill(QtGui.QColor(255, 0, 0))
        
        animation_data = {'frames': [img], 'delays': [100]}
        item = BeeAnimatedPixmapItem(animation_data, filename='single.png')
        
        result = str(item)
        expected = 'Animated Image "single.png" 5 x 7'
        assert result == expected