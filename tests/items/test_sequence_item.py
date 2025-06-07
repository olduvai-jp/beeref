import pytest
import os
from unittest.mock import patch, MagicMock, Mock

from PyQt6 import QtCore, QtGui, QtWidgets

from beeref.items import BeeSequenceItem, item_registry


def create_test_pixmap(width=10, height=10, color=QtCore.Qt.GlobalColor.red):
    """テスト用のQPixmapを作成"""
    pixmap = QtGui.QPixmap(width, height)
    pixmap.fill(color)
    return pixmap


@pytest.fixture
def test_assets_dir():
    """テストアセットディレクトリのパス"""
    return os.path.join(os.path.dirname(__file__), '..', 'assets')


@pytest.fixture
def sequence_item():
    """BeeSequenceItemのフィクスチャ"""
    return BeeSequenceItem()


@pytest.fixture
def sequence_item_with_frames(sequence_item):
    """フレームが追加済みのBeeSequenceItemフィクスチャ"""
    # 3つのフレームを追加
    for i in range(3):
        pixmap = create_test_pixmap(color=[
            QtCore.Qt.GlobalColor.red, 
            QtCore.Qt.GlobalColor.green, 
            QtCore.Qt.GlobalColor.blue
        ][i])
        sequence_item.add_frame(pixmap, f'frame_{i:03d}.png', 100)
    return sequence_item


def test_in_item_registry():
    """アイテムレジストリへの登録確認"""
    assert item_registry['sequence'] == BeeSequenceItem


class TestInitialization:
    """初期化テスト"""

    @patch('beeref.selection.SelectableMixin.init_selectable')
    def test_init_basic(self, selectable_mock, qapp):
        """基本的な初期化テスト"""
        item = BeeSequenceItem()

        # 基本属性の確認
        assert item.save_id is None
        assert item.filename is None
        assert item.is_image is True
        assert item.crop_mode is False
        assert item._frame_data == []
        assert item._current_frame == 0
        assert item.get_frame_count() == 0
        assert item._frame_cache == {}
        assert item._frame_metadata['fps'] == 12
        assert item._frame_metadata['loop'] is True

        selectable_mock.assert_called_once()

    def test_init_with_kwargs(self, qapp):
        """キーワード引数付きの初期化"""
        item = BeeSequenceItem(filename='test_sequence.png')
        assert item.filename == 'test_sequence.png'

    def test_str_representation(self, qapp, sequence_item_with_frames):
        """文字列表現のテスト"""
        sequence_item_with_frames.filename = 'test.png'
        str_repr = str(sequence_item_with_frames)
        assert 'test.png' in str_repr
        assert '3 frames' in str_repr
        assert '12 fps' in str_repr


class TestFrameManagement:
    """フレーム管理テスト"""

    def test_add_frame_basic(self, qapp, sequence_item):
        """基本的なフレーム追加"""
        pixmap = create_test_pixmap()
        
        sequence_item.add_frame(pixmap, 'test.png', 100)
        
        assert sequence_item.get_frame_count() == 1
        assert len(sequence_item._frame_data) == 1
        assert sequence_item._frame_data[0]['filename'] == 'test.png'
        assert sequence_item._frame_data[0]['duration'] == 100
        assert sequence_item._frame_data[0]['size'] == (10, 10)

    def test_add_frame_without_duration(self, qapp, sequence_item):
        """duration指定なしでのフレーム追加（FPSから自動計算）"""
        pixmap = create_test_pixmap()
        sequence_item._frame_metadata['fps'] = 24
        
        sequence_item.add_frame(pixmap, 'test.png')
        
        # 1000ms / 24fps = 約41ms
        expected_duration = int(1000 / 24)
        assert sequence_item._frame_data[0]['duration'] == expected_duration

    def test_add_multiple_frames(self, qapp, sequence_item):
        """複数フレームの追加"""
        for i in range(5):
            pixmap = create_test_pixmap()
            sequence_item.add_frame(pixmap, f'frame_{i}.png', 100)
        
        assert sequence_item.get_frame_count() == 5
        assert len(sequence_item._frame_data) == 5
        assert sequence_item._frame_count == 5

    def test_remove_frame_valid_index(self, qapp, sequence_item_with_frames):
        """有効なインデックスでのフレーム削除"""
        initial_count = sequence_item_with_frames.get_frame_count()
        
        sequence_item_with_frames.remove_frame(1)
        
        assert sequence_item_with_frames.get_frame_count() == initial_count - 1
        assert len(sequence_item_with_frames._frame_data) == initial_count - 1

    def test_remove_frame_invalid_index(self, qapp, sequence_item_with_frames):
        """無効なインデックスでのフレーム削除"""
        initial_count = sequence_item_with_frames.get_frame_count()
        
        # 範囲外のインデックス
        sequence_item_with_frames.remove_frame(10)
        sequence_item_with_frames.remove_frame(-1)
        
        # フレーム数は変わらない
        assert sequence_item_with_frames.get_frame_count() == initial_count

    def test_remove_frame_cache_update(self, qapp, sequence_item_with_frames):
        """フレーム削除時のキャッシュ更新"""
        # キャッシュにフレームを追加
        sequence_item_with_frames.get_frame_pixmap(0)
        sequence_item_with_frames.get_frame_pixmap(1)
        sequence_item_with_frames.get_frame_pixmap(2)
        
        # インデックス1を削除
        sequence_item_with_frames.remove_frame(1)
        
        # キャッシュのインデックスが調整されているか確認
        # 元の2番目のフレームが1番目になる
        assert 0 in sequence_item_with_frames._frame_cache
        assert 1 in sequence_item_with_frames._frame_cache

    def test_remove_frame_current_frame_adjustment(self, qapp, sequence_item_with_frames):
        """フレーム削除時の現在フレーム位置調整"""
        sequence_item_with_frames._current_frame = 2
        
        # インデックス1を削除
        sequence_item_with_frames.remove_frame(1)
        
        # 現在フレームが調整される
        assert sequence_item_with_frames._current_frame == 1


class TestFrameAccess:
    """フレームアクセステスト"""

    def test_get_frame_pixmap_valid_index(self, qapp, sequence_item_with_frames):
        """有効なフレーム番号でのPixmap取得"""
        pixmap = sequence_item_with_frames.get_frame_pixmap(0)
        assert isinstance(pixmap, QtGui.QPixmap)
        assert not pixmap.isNull()

        # キャッシュに保存されているか確認
        assert 0 in sequence_item_with_frames._frame_cache

    def test_get_frame_pixmap_invalid_index(self, qapp, sequence_item_with_frames):
        """無効なフレーム番号での処理"""
        # 負の値
        pixmap = sequence_item_with_frames.get_frame_pixmap(-1)
        assert isinstance(pixmap, QtGui.QPixmap)

        # 範囲外の値
        pixmap = sequence_item_with_frames.get_frame_pixmap(999)
        assert isinstance(pixmap, QtGui.QPixmap)

    def test_get_frame_pixmap_empty_sequence(self, qapp, sequence_item):
        """空のシーケンスでのPixmap取得"""
        pixmap = sequence_item.get_frame_pixmap(0)
        assert isinstance(pixmap, QtGui.QPixmap)
        assert pixmap.size() == QtCore.QSize(100, 100)  # デフォルトサイズ

    def test_frame_cache_functionality(self, qapp, sequence_item_with_frames):
        """フレームキャッシュ機能のテスト"""
        # 最初の取得でキャッシュされる
        frame_0 = sequence_item_with_frames.get_frame_pixmap(0)
        assert 0 in sequence_item_with_frames._frame_cache

        # 2回目の取得でキャッシュから返される
        frame_0_cached = sequence_item_with_frames.get_frame_pixmap(0)
        assert frame_0 is frame_0_cached

    def test_frame_cache_size_limit(self, qapp, sequence_item):
        """フレームキャッシュサイズ制限のテスト"""
        # 15フレーム追加（制限の10を超える）
        for i in range(15):
            pixmap = create_test_pixmap()
            sequence_item.add_frame(pixmap, f'frame_{i}.png', 100)

        # 現在のフレームを5に設定
        sequence_item._current_frame = 5

        # 全フレームにアクセス
        for i in range(15):
            sequence_item.get_frame_pixmap(i)

        # キャッシュサイズが制限内
        assert len(sequence_item._frame_cache) <= 10
        # 現在のフレーム（5）は保持されている
        assert 5 in sequence_item._frame_cache

    def test_pixmap_returns_current_frame(self, qapp, sequence_item_with_frames):
        """pixmap()メソッドが現在のフレームを返すことを確認"""
        sequence_item_with_frames._current_frame = 1
        
        pixmap = sequence_item_with_frames.pixmap()
        expected_pixmap = sequence_item_with_frames.get_frame_pixmap(1)
        
        assert pixmap is expected_pixmap


class TestFpsAndTiming:
    """FPS・タイミング関連テスト"""

    def test_set_fps_basic(self, qapp, sequence_item_with_frames):
        """基本的なFPS設定"""
        sequence_item_with_frames.set_fps(24)
        
        assert sequence_item_with_frames._frame_metadata['fps'] == 24

    def test_set_fps_updates_durations(self, qapp, sequence_item):
        """FPS設定時の既存フレームduration更新"""
        # フレーム追加（duration未設定のものを含む）
        pixmap = create_test_pixmap()
        sequence_item.add_frame(pixmap, 'frame1.png', 0)  # duration=0
        sequence_item.add_frame(pixmap, 'frame2.png', 100)  # duration設定済み
        
        sequence_item.set_fps(30)
        
        expected_duration = int(1000 / 30)  # 約33ms
        assert sequence_item._frame_data[0]['duration'] == expected_duration
        assert sequence_item._frame_data[1]['duration'] == 100  # 設定済みは変更されない

    def test_get_delays(self, qapp, sequence_item_with_frames):
        """フレーム遅延時間取得のテスト"""
        delays = sequence_item_with_frames._get_delays()
        
        assert len(delays) == 3
        assert all(delay == 100 for delay in delays)

    def test_get_delays_with_fps(self, qapp, sequence_item):
        """FPS設定での遅延時間計算"""
        sequence_item._frame_metadata['fps'] = 24
        pixmap = create_test_pixmap()
        sequence_item.add_frame(pixmap, 'frame.png')  # durationはFPSから計算
        
        delays = sequence_item._get_delays()
        expected_delay = int(1000 / 24)
        
        assert delays[0] == expected_delay


class TestSortingAndMetadata:
    """ソート・メタデータテスト"""

    def test_get_sorted_frames(self, qapp, sequence_item):
        """フレームソート機能のテスト"""
        pixmap = create_test_pixmap()
        
        # 自然順序ではない順番で追加
        filenames = ['frame_10.png', 'frame_2.png', 'frame_1.png']
        for filename in filenames:
            sequence_item.add_frame(pixmap, filename, 100)
        
        sorted_frames = sequence_item.get_sorted_frames()
        sorted_filenames = [frame['filename'] for frame in sorted_frames]
        
        # 自然順序でソートされているか確認
        assert sorted_filenames == ['frame_1.png', 'frame_2.png', 'frame_10.png']

    def test_update_from_data(self, qapp, sequence_item):
        """データ更新機能のテスト"""
        update_data = {
            'frame_metadata': {'fps': 30, 'loop': False},
            'frame_data': [
                {'filename': 'test1.png', 'duration': 50, 'data': b'test_data1'},
                {'filename': 'test2.png', 'duration': 60, 'data': b'test_data2'}
            ],
            'fps': 25
        }
        
        sequence_item.update_from_data(**update_data)
        
        assert sequence_item._frame_metadata['fps'] == 25  # fps引数が優先
        assert sequence_item._frame_metadata['loop'] is False
        assert len(sequence_item._frame_data) == 2
        assert sequence_item._frame_count == 2


class TestSerialization:
    """シリアライゼーション（保存・復元）テスト"""

    def test_get_extra_save_data(self, qapp, sequence_item_with_frames):
        """保存データの生成確認"""
        sequence_item_with_frames.filename = 'test_sequence.png'
        sequence_item_with_frames.setOpacity(0.8)
        sequence_item_with_frames.grayscale = True
        sequence_item_with_frames._current_frame = 1
        sequence_item_with_frames.crop = QtCore.QRectF(1, 2, 3, 4)

        data = sequence_item_with_frames.get_extra_save_data()

        # 基本データの確認
        assert data['filename'] == 'test_sequence.png'
        assert data['opacity'] == 0.8
        assert data['grayscale'] is True
        assert data['current_frame'] == 1
        assert data['crop'] == [1.0, 2.0, 3.0, 4.0]
        
        # シーケンス固有データの確認
        assert 'frame_files' in data
        assert 'frame_metadata' in data
        assert data['frame_count'] == 3
        assert len(data['frame_files']) == 3

    def test_create_from_data_minimal(self, qapp, sequence_item):
        """最小限のデータからの復元"""
        data = {'filename': 'new_sequence.png'}

        result = BeeSequenceItem.create_from_data(item=sequence_item, data=data)

        assert result is sequence_item
        assert sequence_item.filename == 'new_sequence.png'
        assert sequence_item.opacity() == 1.0
        assert sequence_item.grayscale is False
        assert sequence_item._current_frame == 0

    def test_create_from_data_full(self, qapp, sequence_item):
        """完全なデータからの復元"""
        frame_data = [
            {'filename': 'frame1.png', 'duration': 100, 'data': b'data1'},
            {'filename': 'frame2.png', 'duration': 120, 'data': b'data2'}
        ]
        
        data = {
            'filename': 'restored_sequence.png',
            'opacity': 0.7,
            'grayscale': True,
            'current_frame': 1,
            'crop': [10, 20, 30, 40],
            'frame_data': frame_data,
            'frame_metadata': {'fps': 24, 'loop': False}
        }

        result = BeeSequenceItem.create_from_data(item=sequence_item, data=data)

        assert result is sequence_item
        assert sequence_item.filename == 'restored_sequence.png'
        assert sequence_item.opacity() == 0.7
        assert sequence_item.grayscale is True
        assert sequence_item._current_frame == 1
        assert sequence_item.crop == QtCore.QRectF(10, 20, 30, 40)
        assert len(sequence_item._frame_data) == 2
        assert sequence_item._frame_metadata['fps'] == 24

    def test_pixmap_to_bytes(self, qapp, sequence_item_with_frames):
        """pixmap_to_bytes()のテスト"""
        data, format_type = sequence_item_with_frames.pixmap_to_bytes()

        assert isinstance(data, bytes)
        assert format_type == 'png'
        assert len(data) > 0


class TestCopy:
    """コピー機能テスト"""

    def test_create_copy_basic(self, qapp, sequence_item_with_frames):
        """基本的なコピー作成"""
        # 元のアイテムを設定
        sequence_item_with_frames.filename = 'original.png'
        sequence_item_with_frames.setPos(10, 20)
        sequence_item_with_frames.setZValue(0.5)
        sequence_item_with_frames.setScale(1.5)
        sequence_item_with_frames.setRotation(45)
        sequence_item_with_frames.setOpacity(0.8)
        sequence_item_with_frames.grayscale = True
        sequence_item_with_frames.crop = QtCore.QRectF(1, 1, 2, 2)
        sequence_item_with_frames._current_frame = 1

        copy = sequence_item_with_frames.create_copy()

        # 基本属性の確認
        assert copy is not sequence_item_with_frames
        assert isinstance(copy, BeeSequenceItem)
        assert copy.filename == 'original.png'
        assert copy.pos() == QtCore.QPointF(10, 20)
        assert copy.zValue() == 0.5
        assert copy.scale() == 1.5
        assert copy.rotation() == 45
        assert copy.opacity() == 0.8
        assert copy.grayscale is True
        assert copy.crop == QtCore.QRectF(1, 1, 2, 2)
        assert copy._current_frame == 1

        # フレームデータがコピーされていることを確認
        assert len(copy._frame_data) == len(sequence_item_with_frames._frame_data)
        assert copy._frame_metadata == sequence_item_with_frames._frame_metadata


class TestExport:
    """エクスポート機能テスト"""

    def test_get_filename_for_export_with_filename(self, qapp, sequence_item_with_frames):
        """ファイル名ありでのエクスポートファイル名生成"""
        sequence_item_with_frames.filename = 'test_sequence.png'
        sequence_item_with_frames.save_id = 5
        
        filename = sequence_item_with_frames.get_filename_for_export('png')
        
        assert filename == '0005-test_sequence_sequence.png'

    def test_get_filename_for_export_without_filename(self, qapp, sequence_item_with_frames):
        """ファイル名なしでのエクスポートファイル名生成"""
        sequence_item_with_frames.filename = None
        sequence_item_with_frames.save_id = 3
        
        filename = sequence_item_with_frames.get_filename_for_export('jpg')
        
        assert filename == '0003_sequence.jpg'

    def test_get_imgformat(self, qapp, sequence_item):
        """画像保存形式の決定"""
        format_type = sequence_item.get_imgformat()
        assert format_type == 'png'


class TestCompatibilityInterface:
    """既存インターフェースとの互換性テスト"""

    def test_delays_property_compatibility(self, qapp, sequence_item_with_frames):
        """delaysプロパティの互換性確認"""
        delays = sequence_item_with_frames._get_delays()
        assert isinstance(delays, list)
        assert len(delays) == 3
        assert all(delay == 100 for delay in delays)

    def test_frames_property_compatibility(self, qapp, sequence_item_with_frames):
        """フレームアクセス機能の確認"""
        # フレーム数の確認
        assert sequence_item_with_frames.get_frame_count() == 3
        
        # インデックスアクセスが可能
        frame_0 = sequence_item_with_frames.get_frame_pixmap(0)
        assert isinstance(frame_0, QtGui.QPixmap)

    def test_current_frame_property_compatibility(self, qapp, sequence_item_with_frames):
        """current_frameプロパティの互換性確認（継承元）"""
        # getter
        assert sequence_item_with_frames.current_frame == 0
        
        # setter
        sequence_item_with_frames.current_frame = 1
        assert sequence_item_with_frames.current_frame == 1


class TestGrayscaleHandling:
    """グレースケール処理テスト"""

    def test_grayscale_property_setter(self, qapp, sequence_item_with_frames):
        """グレースケールプロパティの設定"""
        # 初期キャッシュ
        sequence_item_with_frames.get_frame_pixmap(0)
        assert len(sequence_item_with_frames._frame_cache) > 0

        # グレースケール設定でキャッシュがクリアされる
        sequence_item_with_frames.grayscale = True

        assert sequence_item_with_frames.grayscale is True
        assert len(sequence_item_with_frames._frame_cache) == 0


class TestErrorHandling:
    """エラーハンドリングテスト"""

    def test_get_frame_pixmap_corrupted_data(self, qapp, sequence_item):
        """破損データでのフレーム取得"""
        # 破損データを持つフレームを追加
        sequence_item._frame_data.append({
            'filename': 'corrupted.png',
            'duration': 100,
            'data': b'invalid_image_data'
        })
        sequence_item._frame_count = 1

        pixmap = sequence_item.get_frame_pixmap(0)
        
        # エラー時はデフォルトサイズのPixmapが返される
        assert isinstance(pixmap, QtGui.QPixmap)

    def test_get_frame_pixmap_missing_data(self, qapp, sequence_item):
        """データなしフレームでの取得"""
        # dataキーがないフレームを追加
        sequence_item._frame_data.append({
            'filename': 'missing_data.png',
            'duration': 100
        })
        sequence_item._frame_count = 1

        pixmap = sequence_item.get_frame_pixmap(0)
        
        # エラー時はデフォルトサイズのPixmapが返される
        assert isinstance(pixmap, QtGui.QPixmap)
        assert pixmap.size() == QtCore.QSize(100, 100)