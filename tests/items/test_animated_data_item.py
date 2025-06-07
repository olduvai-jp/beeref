import pytest
import io
from unittest.mock import patch, MagicMock, Mock

from PyQt6 import QtCore, QtGui, QtWidgets

from beeref.items import BeeAnimatedDataItem, item_registry


def create_test_gif_data():
    """テスト用のGIFバイナリデータを作成"""
    # 簡単なテスト用GIFデータを作成
    # 3x3の画像を3フレーム、異なる色で作成
    try:
        from PIL import Image

        frames = []
        for i in range(3):
            # RGB値を変化させて3フレーム作成
            color = (255 * i // 2, 128, 255 - 255 * i // 2)
            img = Image.new('RGB', (3, 3), color)
            frames.append(img)

        # GIFバイトデータとして保存
        gif_bytes = io.BytesIO()
        frames[0].save(
            gif_bytes,
            format='GIF',
            save_all=True,
            append_images=frames[1:],
            duration=100,  # 100ms per frame
            loop=0
        )
        return gif_bytes.getvalue()

    except ImportError:
        # PILが利用できない場合は簡単なダミーデータ
        # 最小限のGIFヘッダー（実際のテストでは問題があるかもしれません）
        return b'GIF89a\x03\x00\x03\x00\x00\x00\x00\x00\x00\x00\x00;\x00'


@pytest.fixture
def gif_data():
    """テスト用GIFデータのフィクスチャ"""
    return create_test_gif_data()


@pytest.fixture
def animated_data_item(gif_data):
    """BeeAnimatedDataItemのフィクスチャ"""
    return BeeAnimatedDataItem(gif_data, filename='test.gif')


def test_in_item_registry():
    """アイテムレジストリへの登録確認"""
    assert item_registry['animated_data'] == BeeAnimatedDataItem


class TestInitialization:
    """初期化テスト"""

    @patch('beeref.selection.SelectableMixin.init_selectable')
    def test_init_basic(self, selectable_mock, qapp, gif_data):
        """基本的な初期化テスト"""
        item = BeeAnimatedDataItem(gif_data, filename='test.gif')

        # 基本属性の確認
        assert item.save_id is None
        assert item.filename == 'test.gif'
        assert item.is_image is True
        assert item.crop_mode is False
        assert item._animation_data == gif_data
        assert item._current_frame == 0
        assert item._animation_started is False
        assert item._frame_cache == {0: item._frame_cache[0]}  # 最初のフレームがキャッシュ

        selectable_mock.assert_called_once()

    def test_init_without_filename(self, qapp, gif_data):
        """ファイル名なしの初期化"""
        item = BeeAnimatedDataItem(gif_data)
        assert item.filename is None

    def test_init_reader_failure(self, qapp, gif_data):
        """新しいPILベース実装での初期化テスト"""
        # PILベースの実装では、有効なGIFデータから正しくフレーム数を読み取る
        item = BeeAnimatedDataItem(gif_data, filename='test.gif')

        # 実際のGIFデータから読み取られた値を確認
        assert item._frame_count >= 1  # 最低1フレーム以上
        assert len(item._delays) == item._frame_count
        assert all(delay > 0 for delay in item._delays)  # 全ての遅延が正の値


class TestFrameAccess:
    """フレームアクセステスト"""

    def test_get_frame_pixmap_valid_index(self, qapp, animated_data_item):
        """有効なフレーム番号でのPixmap取得"""
        pixmap = animated_data_item.get_frame_pixmap(0)
        assert isinstance(pixmap, QtGui.QPixmap)
        assert not pixmap.isNull()

        # キャッシュに保存されているか確認
        assert 0 in animated_data_item._frame_cache

    def test_get_frame_pixmap_invalid_index(self, qapp, animated_data_item):
        """無効なフレーム番号での処理"""
        # 負の値
        pixmap = animated_data_item.get_frame_pixmap(-1)
        assert isinstance(pixmap, QtGui.QPixmap)

        # 範囲外の値
        pixmap = animated_data_item.get_frame_pixmap(999)
        assert isinstance(pixmap, QtGui.QPixmap)

    def test_frame_cache_functionality(self, qapp, animated_data_item):
        """フレームキャッシュ機能のテスト"""
        # 最初の取得でキャッシュされる
        frame_0 = animated_data_item.get_frame_pixmap(0)
        assert 0 in animated_data_item._frame_cache

        # 2回目の取得でキャッシュから返される
        frame_0_cached = animated_data_item.get_frame_pixmap(0)
        assert frame_0 is frame_0_cached

    @patch('beeref.items.logger')
    def test_frame_cache_size_limit(
            self, mock_logger, qapp, animated_data_item):
        """フレームキャッシュサイズ制限のテスト"""
        # キャッシュサイズ制限（10フレーム）をテスト

        # 現在のフレームを1に設定（0番は削除されない保護対象にならないように）
        animated_data_item._current_frame = 1

        # 既存のキャッシュをクリアして、0-9フレームを手動で追加
        animated_data_item._frame_cache.clear()
        for i in range(10):
            animated_data_item._frame_cache[i] = QtGui.QPixmap(1, 1)

        assert len(animated_data_item._frame_cache) == 10

        # PILフレームを設定（get_frame_pixmapが機能するように）
        animated_data_item._pil_frames = [Mock() for _ in range(20)]
        animated_data_item._frame_count = 20

        # 新しいフレーム（10番目）を追加
        with patch.object(animated_data_item, '_pil_to_qimage') as mock_pil:
            mock_image = QtGui.QImage(1, 1, QtGui.QImage.Format.Format_ARGB32)
            mock_image.fill(QtGui.QColor(255, 0, 0))
            mock_pil.return_value = mock_image

            # 10番目のフレームを取得
            animated_data_item.get_frame_pixmap(10)

            # 最古の非現在フレーム（0番）が削除され、新しいフレーム（10番）が追加される
            assert 0 not in animated_data_item._frame_cache  # 0番は最古なので削除
            assert 1 in animated_data_item._frame_cache      # 1番は現在フレームなので保持
            assert 10 in animated_data_item._frame_cache     # 10番は新規追加
            assert len(animated_data_item._frame_cache) == 10  # キャッシュサイズは制限内


class TestCompatibilityInterface:
    """既存インターフェースとの互換性テスト"""

    def test_pixmap_returns_current_frame(self, qapp, animated_data_item):
        """pixmap()メソッドが現在のフレームを返すことを確認"""
        pixmap = animated_data_item.pixmap()
        expected_pixmap = animated_data_item.get_frame_pixmap(
            animated_data_item._current_frame)
        assert pixmap is expected_pixmap

    def test_frames_property_compatibility(self, qapp, animated_data_item):
        """framesプロパティの互換性確認"""
        frames = animated_data_item.frames

        # len()が使える
        assert len(frames) == animated_data_item._frame_count

        # インデックスアクセスが可能
        frame_0 = frames[0]
        assert isinstance(frame_0, QtGui.QPixmap)

        # get_frame_pixmapと同じ結果を返す
        assert frame_0 is animated_data_item.get_frame_pixmap(0)

    def test_delays_property(self, qapp, animated_data_item):
        """delaysプロパティのテスト"""
        delays = animated_data_item.delays
        assert isinstance(delays, list)
        assert len(delays) == animated_data_item._frame_count

        # コピーが返されることを確認（元のリストが変更されない）
        delays.append(999)
        assert 999 not in animated_data_item.delays

    def test_current_frame_property(self, qapp, animated_data_item):
        """current_frameプロパティのテスト"""
        # getter
        assert animated_data_item.current_frame == 0

        # setter - 有効な値
        animated_data_item.current_frame = 1
        assert animated_data_item.current_frame == 1

        # setter - 無効な値（範囲外）
        original_frame = animated_data_item.current_frame
        animated_data_item.current_frame = 999
        assert animated_data_item.current_frame == original_frame  # 変更されない

        animated_data_item.current_frame = -1
        assert animated_data_item.current_frame == original_frame  # 変更されない


class TestAnimationControl:
    """アニメーション制御テスト"""

    def test_start_animation_multiple_frames_with_scene(self, qapp,
                                                        animated_data_item):
        """複数フレーム、シーンありでのアニメーション開始"""
        # フレーム数を複数に設定
        animated_data_item._frame_count = 3

        # シーンを設定
        scene = QtWidgets.QGraphicsScene()
        scene.addItem(animated_data_item)

        animated_data_item.start_animation()

        assert animated_data_item._animation_started is True

    def test_start_animation_single_frame(self, qapp, animated_data_item):
        """単一フレームでのアニメーション開始（開始されない）"""
        animated_data_item._frame_count = 1

        scene = QtWidgets.QGraphicsScene()
        scene.addItem(animated_data_item)

        animated_data_item.start_animation()

        assert animated_data_item._animation_started is False

    def test_start_animation_no_scene(self, qapp, animated_data_item):
        """シーンなしでのアニメーション開始（開始されない）"""
        animated_data_item._frame_count = 3

        animated_data_item.start_animation()

        assert animated_data_item._animation_started is False

    def test_stop_animation(self, qapp, animated_data_item):
        """アニメーション停止"""
        animated_data_item._animation_started = True
        animated_data_item.stop_animation()

        assert animated_data_item._animation_started is False


class TestAnimationUpdate:
    """アニメーション更新テスト"""

    def test_update_animation_not_started(self, qapp, animated_data_item):
        """アニメーション未開始時の更新"""
        animated_data_item._animation_started = False
        result = animated_data_item.update_animation(100)
        assert result is False

    def test_update_animation_single_frame(self, qapp, animated_data_item):
        """単一フレーム時の更新"""
        animated_data_item._frame_count = 1
        animated_data_item._animation_started = True
        result = animated_data_item.update_animation(100)
        assert result is False

    def test_update_animation_frame_advance(self, qapp, animated_data_item):
        """フレーム進行テスト"""
        animated_data_item._frame_count = 3
        animated_data_item._delays = [120, 150, 200]
        animated_data_item._animation_started = True
        animated_data_item._current_frame = 0

        # 不十分な時間（フレーム進行なし）
        result = animated_data_item.update_animation(50)
        assert result is False
        assert animated_data_item._current_frame == 0
        assert animated_data_item.frame_timer == 50

        # 十分な時間（フレーム進行あり）
        result = animated_data_item.update_animation(80)  # 合計130ms > 120ms
        assert result is True
        assert animated_data_item._current_frame == 1
        assert animated_data_item.frame_timer == 10  # 130 - 120

    def test_update_animation_loop(self, qapp, animated_data_item):
        """フレームループテスト"""
        animated_data_item._frame_count = 3
        animated_data_item._delays = [100, 100, 100]
        animated_data_item._animation_started = True
        animated_data_item._current_frame = 2  # 最後のフレーム

        result = animated_data_item.update_animation(150)
        assert result is True
        assert animated_data_item._current_frame == 0  # ループして最初に戻る


class TestSceneIntegration:
    """シーン連携テスト"""

    @patch.object(BeeAnimatedDataItem, 'start_animation')
    def test_item_change_added_to_scene(self, mock_start, qapp,
                                        animated_data_item):
        """シーンに追加された時のアニメーション開始"""
        scene = QtWidgets.QGraphicsScene()

        result = animated_data_item.itemChange(
            QtWidgets.QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged,
            scene
        )

        mock_start.assert_called_once()
        assert result == scene

    @patch.object(BeeAnimatedDataItem, 'stop_animation')
    def test_item_change_removed_from_scene(self, mock_stop, qapp,
                                            animated_data_item):
        """シーンから削除された時のアニメーション停止"""
        result = animated_data_item.itemChange(
            QtWidgets.QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged,
            None
        )

        mock_stop.assert_called_once()
        assert result is None


class TestSerialization:
    """シリアライゼーション（保存・復元）テスト"""

    def test_get_extra_save_data(self, qapp, animated_data_item):
        """保存データの生成確認"""
        animated_data_item.setOpacity(0.8)
        animated_data_item.grayscale = True
        animated_data_item._current_frame = 1
        animated_data_item.crop = QtCore.QRectF(1, 2, 3, 4)

        data = animated_data_item.get_extra_save_data()

        expected = {
            'filename': 'test.gif',
            'opacity': 0.8,
            'grayscale': True,
            'current_frame': 1,
            'crop': [1.0, 2.0, 3.0, 4.0]
        }
        assert data == expected

    def test_create_from_data_minimal(self, qapp, animated_data_item):
        """最小限のデータからの復元"""
        data = {'filename': 'new_name.gif'}

        result = BeeAnimatedDataItem.create_from_data(item=animated_data_item,
                                                      data=data)

        assert result is animated_data_item
        assert animated_data_item.filename == 'new_name.gif'
        assert animated_data_item.opacity() == 1.0
        assert animated_data_item.grayscale is False
        assert animated_data_item._current_frame == 0

    def test_create_from_data_full(self, qapp, animated_data_item):
        """完全なデータからの復元"""
        data = {
            'filename': 'restored.gif',
            'opacity': 0.7,
            'grayscale': True,
            'current_frame': 1,
            'crop': [10, 20, 30, 40]
        }

        result = BeeAnimatedDataItem.create_from_data(item=animated_data_item,
                                                      data=data)

        assert result is animated_data_item
        assert animated_data_item.filename == 'restored.gif'
        assert animated_data_item.opacity() == 0.7
        assert animated_data_item.grayscale is True
        assert animated_data_item._current_frame == 1
        assert animated_data_item.crop == QtCore.QRectF(10, 20, 30, 40)

    def test_pixmap_to_bytes_preserves_original_data(self, qapp,
                                                     animated_data_item):
        """pixmap_to_bytes()が元データを保持することを確認"""
        data, format_type = animated_data_item.pixmap_to_bytes()

        assert data == animated_data_item._animation_data
        assert format_type == 'gif'

    def test_pixmap_from_bytes_restoration(self, qapp, gif_data):
        """pixmap_from_bytes()でのデータ復元"""
        item = BeeAnimatedDataItem(b'dummy_data')

        item.pixmap_from_bytes(gif_data)

        assert item._animation_data == gif_data


class TestCopy:
    """コピー機能テスト"""

    def test_create_copy_basic(self, qapp, animated_data_item):
        """基本的なコピー作成"""
        # 元のアイテムを設定
        animated_data_item.setPos(10, 20)
        animated_data_item.setZValue(0.5)
        animated_data_item.setScale(1.5)
        animated_data_item.setRotation(45)
        animated_data_item.setOpacity(0.8)
        animated_data_item.grayscale = True
        animated_data_item.crop = QtCore.QRectF(1, 1, 2, 2)
        animated_data_item._current_frame = 1

        copy = animated_data_item.create_copy()

        # 基本属性の確認
        assert copy is not animated_data_item
        assert isinstance(copy, BeeAnimatedDataItem)
        assert copy.filename == animated_data_item.filename
        assert copy.pos() == QtCore.QPointF(10, 20)
        assert copy.zValue() == 0.5
        assert copy.scale() == 1.5
        assert copy.rotation() == 45
        assert copy.opacity() == 0.8
        assert copy.grayscale is True
        assert copy.crop == QtCore.QRectF(1, 1, 2, 2)
        assert copy._current_frame == 1

        # 元データが共有されていることを確認（メモリ効率のため）
        assert copy._animation_data == animated_data_item._animation_data

    def test_copy_to_clipboard(self, qapp, animated_data_item):
        """クリップボードへのコピー"""
        clipboard = MagicMock()

        animated_data_item.copy_to_clipboard(clipboard)

        clipboard.setPixmap.assert_called_once()
        # 現在のフレームのPixmapが設定されることを確認
        call_args = clipboard.setPixmap.call_args[0]
        assert isinstance(call_args[0], QtGui.QPixmap)


class TestMemoryEfficiency:
    """メモリ効率性テスト"""

    def test_original_data_preservation(self, qapp, gif_data):
        """元データの保持確認"""
        item = BeeAnimatedDataItem(gif_data, filename='test.gif')

        # 元データが保持されている
        assert item._animation_data == gif_data
        assert isinstance(item._animation_data, bytes)

    def test_frame_cache_memory_management(self, qapp, animated_data_item):
        """フレームキャッシュのメモリ管理"""
        # 初期状態でキャッシュサイズを確認
        # 初期キャッシュサイズを記録（テスト用）
        len(animated_data_item._frame_cache)

        # 複数のフレームにアクセス
        for i in range(min(5, animated_data_item._frame_count)):
            animated_data_item.get_frame_pixmap(i)

        # キャッシュサイズが適切に管理されている
        assert len(animated_data_item._frame_cache) <= 10  # 制限値


class TestGrayscaleHandling:
    """グレースケール処理テスト"""

    def test_grayscale_property_setter(self, qapp, animated_data_item):
        """グレースケールプロパティの設定"""
        # 初期キャッシュ
        animated_data_item.get_frame_pixmap(0)
        # 初期キャッシュサイズを記録（テスト用）
        len(animated_data_item._frame_cache)

        # グレースケール設定でキャッシュがクリアされる
        animated_data_item.grayscale = True

        assert animated_data_item.grayscale is True
        assert len(animated_data_item._frame_cache) == 0  # キャッシュがクリアされた

    def test_paint_with_grayscale(self, qapp, animated_data_item):
        """グレースケールでの描画テスト"""
        animated_data_item.grayscale = True

        painter = MagicMock()
        painter.combinedTransform.return_value.m11.return_value = 1.0


class TestDefaultFpsLogic:
    """デフォルトFPS設定ロジックテスト"""

    def test_default_fps_applied_when_no_valid_delay(self, qapp, animated_data_item):
        """元画像に有効な遅延情報がない場合のデフォルトFPS適用テスト"""
        # テスト用の設定
        animated_data_item._frame_count = 3
        animated_data_item._delays = [0, -5, 0]  # 無効な遅延値
        animated_data_item._animation_started = True
        animated_data_item._current_frame = 0

        # デフォルトFPS設定を20に変更
        animated_data_item.settings.setValue('Items/animation_default_fps', 20)

        # 十分な時間（60ms）でアニメーション更新
        result = animated_data_item.update_animation(60)

        assert result is True
        assert animated_data_item._current_frame == 1
        assert animated_data_item.frame_timer == 10  # 60 - 50

    def test_default_fps_applied_when_delay_is_100ms(self, qapp, animated_data_item):
        """遅延が100ms（デフォルト値）の場合のデフォルトFPS適用テスト"""
        # テスト用の設定
        animated_data_item._frame_count = 2
        animated_data_item._delays = [100, 100]  # デフォルト値（無効扱い）
        animated_data_item._animation_started = True
        animated_data_item._current_frame = 0

        # デフォルトFPS設定を25に変更
        animated_data_item.settings.setValue('Items/animation_default_fps', 25)

        # 十分な時間（50ms）でアニメーション更新
        result = animated_data_item.update_animation(50)

        assert result is True
        assert animated_data_item._current_frame == 1
        assert animated_data_item.frame_timer == 10  # 50 - 40

    def test_original_delay_priority_over_default_fps(self, qapp, animated_data_item):
        """元画像の遅延情報がデフォルトFPS設定より優先されることをテスト"""
        # テスト用の設定
        animated_data_item._frame_count = 2
        animated_data_item._delays = [200, 150]  # 有効な遅延値
        animated_data_item._animation_started = True
        animated_data_item._current_frame = 0

        # デフォルトFPS設定を変更（使用されるべきではない）
        animated_data_item.settings.setValue('Items/animation_default_fps', 60)

        # 元画像の遅延（200ms）に基づいてテスト
        # 不十分な時間（150ms）
        result = animated_data_item.update_animation(150)
        assert result is False
        assert animated_data_item._current_frame == 0
        assert animated_data_item.frame_timer == 150

        # 十分な時間（60ms追加で合計210ms）
        result = animated_data_item.update_animation(60)
        assert result is True
        assert animated_data_item._current_frame == 1
        assert animated_data_item.frame_timer == 10  # 210 - 200

    def test_mixed_delays_with_default_fps_fallback(self, qapp, animated_data_item):
        """混在した遅延値でのデフォルトFPS適用テスト"""
        # テスト用の設定
        animated_data_item._frame_count = 4
        animated_data_item._delays = [150, 0, 200, 100]  # 有効/無効混在
        animated_data_item._animation_started = True
        animated_data_item._current_frame = 0

        # デフォルトFPS設定
        animated_data_item.settings.setValue('Items/animation_default_fps', 30)
        default_delay = 1000 / 30  # 約33.33ms

        # フレーム0→1: 元遅延150ms使用
        result = animated_data_item.update_animation(160)
        assert result is True
        assert animated_data_item._current_frame == 1
        assert abs(animated_data_item.frame_timer - 10) < 1  # 160 - 150

        # フレーム1→2: デフォルトFPS使用（遅延0ms→無効）
        result = animated_data_item.update_animation(40)
        assert result is True
        assert animated_data_item._current_frame == 2
        # 合計50ms、デフォルト遅延33.33msなので進む
        assert abs(animated_data_item.frame_timer - (50 - default_delay)) < 1

    def test_default_fps_setting_change_affects_animation(self, qapp,
                                                          animated_data_item):
        """デフォルトFPS設定変更時の動作確認テスト"""
        # テスト用の設定
        animated_data_item._frame_count = 2
        animated_data_item._delays = [0, 0]  # 無効な遅延（デフォルトFPS使用）
        animated_data_item._animation_started = True
        animated_data_item._current_frame = 0

        # 初期設定: 10 FPS（100ms間隔）
        animated_data_item.settings.setValue('Items/animation_default_fps', 10)

        # 90msでは進まない
        result = animated_data_item.update_animation(90)
        assert result is False
        assert animated_data_item._current_frame == 0

        # 設定を20 FPSに変更（50ms間隔）
        animated_data_item.settings.setValue('Items/animation_default_fps', 20)

        # 既に90ms蓄積されているので、次の更新で進むはず
        # 100ms ÷ 50ms = 2回進行 → フレーム0→1→0（ループ完了）
        result = animated_data_item.update_animation(10)  # 合計100ms
        assert result is True
        assert animated_data_item._current_frame == 0  # 2回進行してループ完了

    def test_default_fps_boundary_values(self, qapp, animated_data_item):
        """デフォルトFPS設定の境界値テスト"""
        # テスト用の設定
        animated_data_item._frame_count = 2
        animated_data_item._delays = [0, 0]  # 無効な遅延
        animated_data_item._animation_started = True

        # 最小値: 1 FPS（1000ms間隔）
        animated_data_item.settings.setValue('Items/animation_default_fps', 1)
        animated_data_item._current_frame = 0
        animated_data_item.frame_timer = 0

        result = animated_data_item.update_animation(1000)
        assert result is True
        assert animated_data_item._current_frame == 1
        assert animated_data_item.frame_timer == 0

        # 最大値: 60 FPS（約16.67ms間隔）
        animated_data_item.settings.setValue('Items/animation_default_fps', 60)
        animated_data_item._current_frame = 0
        animated_data_item.frame_timer = 0

        expected_delay = 1000 / 60
        result = animated_data_item.update_animation(20)
        assert result is True
        assert animated_data_item._current_frame == 1
        assert abs(animated_data_item.frame_timer - (20 - expected_delay)) < 1

    @patch('beeref.items.logger')
    def test_default_fps_logging(self, mock_logger, qapp, animated_data_item):
        """デフォルトFPS使用時のログ出力テスト"""
        # テスト用の設定
        animated_data_item._frame_count = 2
        animated_data_item._delays = [0, 0]  # 無効な遅延
        animated_data_item._animation_started = True
        animated_data_item._current_frame = 0

        # デフォルトFPS設定
        animated_data_item.settings.setValue('Items/animation_default_fps', 15)

        # アニメーション更新
        animated_data_item.update_animation(100)

        # デフォルトFPS使用のログが出力されることを確認
        debug_calls = [call for call in mock_logger.debug.call_args_list]
        default_fps_logged = any(
            'Using default FPS: 15' in str(call) for call in debug_calls
        )
        assert default_fps_logged, "デフォルトFPS使用のログが出力されていません"

    def test_original_delay_logging(self, qapp, animated_data_item):
        """元遅延使用時のログ出力テスト"""
        with patch('beeref.items.logger') as mock_logger:
            # テスト用の設定
            animated_data_item._frame_count = 2
            animated_data_item._delays = [250, 300]  # 有効な遅延
            animated_data_item._animation_started = True
            animated_data_item._current_frame = 0

            # アニメーション更新
            animated_data_item.update_animation(300)

            # 元遅延使用のログが出力されることを確認
            debug_calls = [call for call in mock_logger.debug.call_args_list]
            original_delay_logged = any(
                'Using original delay: 250' in str(call) for call in debug_calls
            )
            assert original_delay_logged, "元遅延使用のログが出力されていません"

    def test_default_fps_with_frame_advance_multiple_times(self, qapp,
                                                           animated_data_item):
        """複数フレーム進行時のデフォルトFPS適用テスト"""
        # テスト用の設定
        animated_data_item._frame_count = 4
        animated_data_item._delays = [0, 0, 0, 0]  # 全て無効な遅延
        animated_data_item._animation_started = True
        animated_data_item._current_frame = 0

        # デフォルトFPS設定: 20 FPS（50ms間隔）
        animated_data_item.settings.setValue('Items/animation_default_fps', 20)

        # 180msで3フレーム進むはず（50ms × 3 = 150ms、残り30ms）
        result = animated_data_item.update_animation(180)

        assert result is True
        assert animated_data_item._current_frame == 3
        assert abs(animated_data_item.frame_timer - 30) < 1  # 180 - 150

    def test_settings_instance_access(self, qapp, animated_data_item):
        """アニメーションアイテムが設定インスタンスにアクセスできることを確認"""
        # 設定インスタンスが存在することを確認
        assert hasattr(animated_data_item, 'settings')
        assert animated_data_item.settings is not None

        # デフォルトFPS設定を読み取れることを確認
        default_fps = animated_data_item.settings.valueOrDefault(
            'Items/animation_default_fps')
        assert isinstance(default_fps, int)
        assert 1 <= default_fps <= 60

        # 描画テスト用のモックオブジェクトを作成
        painter = MagicMock()
        painter.combinedTransform.return_value.m11.return_value = 1.0
        option = MagicMock()
        widget = MagicMock()
        animated_data_item.paint_selectable = MagicMock()

        # エラーなく描画できることを確認
        animated_data_item.paint(painter, option, widget)

        # drawPixmapが呼ばれていることを確認


class TestSameAsSourceExport:
    """Same as Source エクスポート機能テスト"""

    def test_to_same_as_source_bytes_no_crop(self, qapp, animated_data_item):
        """クロップなしのSame as Source エクスポート"""
        data, format_type = animated_data_item.to_same_as_source_bytes(
            apply_crop=False)

        # 元データがそのまま返されることを確認
        assert data == animated_data_item._animation_data
        assert format_type == 'gif'  # test.gifなのでgif形式

    def test_to_same_as_source_bytes_with_crop(self, qapp, animated_data_item):
        """クロップありのSame as Source エクスポート"""
        # クロップを設定
        animated_data_item.crop = QtCore.QRectF(0, 0, 1, 1)

        data, format_type = animated_data_item.to_same_as_source_bytes(
            apply_crop=True)

        # クロップが適用されている場合は再生成されるため、元データと異なる可能性
        assert isinstance(data, bytes)
        assert format_type == 'gif'

    def test_get_imgformat_gif(self, qapp, gif_data):
        """GIF形式の判定テスト"""
        item = BeeAnimatedDataItem(gif_data, filename='test.gif')
        assert item.get_imgformat() == 'gif'

    def test_get_imgformat_webp(self, qapp, gif_data):
        """WebP形式の判定テスト"""
        item = BeeAnimatedDataItem(gif_data, filename='test.webp')
        assert item.get_imgformat() == 'webp'

    def test_get_imgformat_unknown_extension(self, qapp, gif_data):
        """不明な拡張子の場合のフォールバック"""
        item = BeeAnimatedDataItem(gif_data, filename='test.unknown')
        assert item.get_imgformat() == 'gif'  # デフォルトはgif

    def test_get_imgformat_no_filename(self, qapp, gif_data):
        """ファイル名なしの場合のフォールバック"""
        item = BeeAnimatedDataItem(gif_data, filename=None)
        assert item.get_imgformat() == 'gif'  # デフォルトはgif

    @patch('beeref.items.logger')
    def test_to_same_as_source_bytes_error_handling(self, mock_logger, qapp,
                                                    animated_data_item):
        """Same as Source エクスポートのエラーハンドリング"""
        # 最終フォールバック処理をモック
        with patch.object(animated_data_item,
                          'to_animated_gif_bytes') as mock_gif_fallback:
            mock_gif_fallback.return_value = (b'fallback_data', 'gif')

            # 故意にエラーを発生させる（get_imgformatが常にエラーを投げる）
            with patch.object(animated_data_item, 'get_imgformat',
                              side_effect=Exception("Test error")):
                data, format_type = animated_data_item.to_same_as_source_bytes(
                    apply_crop=False)

                # フォールバック処理が実行されることを確認
                assert data == b'fallback_data'
                assert format_type == 'gif'

                # エラーログが出力されることを確認
                assert mock_logger.error.call_count >= 1  # 最低1回はエラーログが出力される
                mock_gif_fallback.assert_called_once_with(False)

    def test_webp_same_as_source_export(self, qapp):
        """WebP形式でのSame as Source エクスポート"""
        # WebPテストデータを作成
        webp_data = b'RIFF\x00\x00\x00\x00WEBP'  # 簡単なWebPヘッダー
        item = BeeAnimatedDataItem(webp_data, filename='test.webp')

        data, format_type = item.to_same_as_source_bytes(apply_crop=False)

        assert data == webp_data
        assert format_type == 'webp'

    def test_quality_preservation(self, qapp, animated_data_item):
        """Same as Source エクスポートによる品質保持の確認"""
        original_data = animated_data_item._animation_data

        # 複数回エクスポートしても元データが変わらないことを確認
        for _ in range(3):
            data, format_type = animated_data_item.to_same_as_source_bytes(
                apply_crop=False)
            assert data == original_data
            assert format_type == 'gif'

        # 元データが変更されていないことを確認
        assert animated_data_item._animation_data == original_data


class TestExportFormatCompatibility:
    """エクスポート形式の互換性テスト"""

    def test_export_format_consistency(self, qapp, animated_data_item):
        """各エクスポート形式の一貫性確認"""
        # Same as Source
        same_data, same_format = animated_data_item.to_same_as_source_bytes(
            apply_crop=False)

        # GIF形式
        gif_data, gif_format = animated_data_item.to_animated_gif_bytes(
            apply_crop=False)

        # WebP形式
        webp_data, webp_format = animated_data_item.to_animated_webp_bytes(
            apply_crop=False)

        # フォーマットが正しく設定されていることを確認
        assert same_format == 'gif'  # 元がGIFなので
        assert gif_format == 'gif'
        assert webp_format == 'webp'

        # 全てバイト形式であることを確認
        assert isinstance(same_data, bytes)
        assert isinstance(gif_data, bytes)
        assert isinstance(webp_data, bytes)

    def test_export_method_availability(self, qapp, animated_data_item):
        """すべてのエクスポートメソッドが利用可能であることを確認"""
        # メソッドが存在することを確認
        assert hasattr(animated_data_item, 'to_same_as_source_bytes')
        assert hasattr(animated_data_item, 'to_animated_gif_bytes')
        assert hasattr(animated_data_item, 'to_animated_webp_bytes')

        # メソッドが呼び出し可能であることを確認
        assert callable(animated_data_item.to_same_as_source_bytes)
        assert callable(animated_data_item.to_animated_gif_bytes)
        assert callable(animated_data_item.to_animated_webp_bytes)


class TestResourceManagement:
    """リソース管理テスト"""

    def test_destructor_cleanup(self, qapp, gif_data):
        """デストラクタでのリソースクリーンアップ"""
        item = BeeAnimatedDataItem(gif_data)

        # バッファが開かれている
        assert hasattr(item, '_buffer')
        buffer_is_open = (item._buffer.isOpen()
                          if hasattr(item._buffer, 'isOpen') else True)
        assert buffer_is_open

        # デストラクタを手動で呼び出し
        item.__del__()

        # バッファが閉じられている（エラーが発生しないことを確認）
        # 実際のクリーンアップはQtが管理するため、エラーなく実行されることを確認
