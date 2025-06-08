import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

from PyQt6 import QtCore, QtGui

from beeref.fileio.sequence_import import (
    create_sequence_item_from_files,
    create_sequence_item_from_group,
    import_sequences_from_directory,
    detect_fps_from_filenames,
    validate_sequence_files,
    get_sequence_import_info,
    _natural_sort_key,
    _detect_sequence_pattern
)
from beeref.fileio.sequence_detection import SequenceGroup
from beeref.items import BeeSequenceItem


def create_test_image_file(filepath, width=10, height=10,
                           color=QtCore.Qt.GlobalColor.red):
    """テスト用の画像ファイルを作成"""
    pixmap = QtGui.QPixmap(width, height)
    pixmap.fill(color)
    pixmap.save(filepath, 'PNG')


@pytest.fixture
def temp_dir():
    """一時ディレクトリのフィクスチャ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_sequence_files(temp_dir):
    """テスト用の連番ファイルを作成"""
    files = []
    for i in range(5):
        filepath = os.path.join(temp_dir, f'frame_{i:03d}.png')
        create_test_image_file(filepath, color=[
            QtCore.Qt.GlobalColor.red,
            QtCore.Qt.GlobalColor.green,
            QtCore.Qt.GlobalColor.blue,
            QtCore.Qt.GlobalColor.yellow,
            QtCore.Qt.GlobalColor.cyan
        ][i])
        files.append(filepath)
    return files


@pytest.fixture
def test_assets_dir():
    """テストアセットディレクトリのパス"""
    return os.path.join(os.path.dirname(__file__), '..', 'assets')


class TestCreateSequenceItemFromFiles:
    """create_sequence_item_from_files関数のテスト"""

    def test_create_from_valid_files(self, qapp, test_sequence_files):
        """有効なファイルからのシーケンス作成"""
        item = create_sequence_item_from_files(test_sequence_files, fps=24.0)

        assert item is not None
        assert isinstance(item, BeeSequenceItem)
        assert item.get_frame_count() == 5
        assert item._frame_metadata['fps'] == 24.0
        assert 'frame_000.png' in item.filename

    def test_create_empty_file_list(self, qapp):
        """空のファイルリストでの作成"""
        item = create_sequence_item_from_files([], fps=12.0)

        assert item is None

    def test_create_nonexistent_files(self, qapp, temp_dir):
        """存在しないファイルでの作成"""
        fake_files = [
            os.path.join(temp_dir, 'nonexistent1.png'),
            os.path.join(temp_dir, 'nonexistent2.png')
        ]

        item = create_sequence_item_from_files(fake_files, fps=12.0)

        assert item is None

    def test_create_mixed_valid_invalid_files(self, qapp, test_sequence_files,
                                              temp_dir):
        """有効・無効ファイル混在での作成"""
        mixed_files = test_sequence_files[:2] + [
            os.path.join(temp_dir, 'nonexistent.png')
        ]

        item = create_sequence_item_from_files(mixed_files, fps=12.0)

        # 有効なファイルのみでシーケンスが作成される
        assert item is not None
        assert item.get_frame_count() == 2

    def test_natural_sorting(self, qapp, temp_dir):
        """自然順序ソートのテスト"""
        # 順不同でファイルを作成
        filenames = [
            'frame_10.png',
            'frame_2.png',
            'frame_1.png',
            'frame_20.png']
        files = []
        for filename in filenames:
            filepath = os.path.join(temp_dir, filename)
            create_test_image_file(filepath)
            files.append(filepath)

        item = create_sequence_item_from_files(files, fps=12.0)

        assert item is not None
        # フレーム順序が自然順序になっているか確認
        frame_filenames = [frame['filename'] for frame in item._frame_data]
        expected_order = [
            'frame_1.png',
            'frame_2.png',
            'frame_10.png',
            'frame_20.png']
        assert frame_filenames == expected_order

    def test_corrupted_image_handling(self, qapp, temp_dir):
        """破損画像ファイルの処理"""
        # 正常なファイルと破損ファイルを作成
        valid_file = os.path.join(temp_dir, 'valid.png')
        corrupted_file = os.path.join(temp_dir, 'corrupted.png')

        create_test_image_file(valid_file)
        # 破損ファイル（無効なPNGデータ）
        with open(corrupted_file, 'wb') as f:
            f.write(b'invalid_png_data')

        files = [valid_file, corrupted_file]
        item = create_sequence_item_from_files(files, fps=12.0)

        # 有効なファイルのみでシーケンスが作成される
        assert item is not None
        assert item.get_frame_count() == 1

    def test_fps_and_duration_calculation(self, qapp, test_sequence_files):
        """FPSとduration計算のテスト"""
        fps = 30.0
        item = create_sequence_item_from_files(test_sequence_files, fps=fps)

        expected_duration = int(1000 / fps)  # 約33ms
        for frame in item._frame_data:
            assert frame['duration'] == expected_duration

    def test_metadata_setting(self, qapp, test_sequence_files):
        """メタデータ設定のテスト"""
        item = create_sequence_item_from_files(test_sequence_files, fps=60.0)

        assert item._frame_metadata['fps'] == 60.0
        assert item._frame_metadata['loop'] is True
        assert 'source_directory' in item._frame_metadata
        assert 'sequence_pattern' in item._frame_metadata


class TestCreateSequenceItemFromGroup:
    """create_sequence_item_from_group関数のテスト"""

    def test_create_from_valid_group(self, qapp, test_sequence_files):
        """有効なSequenceGroupからの作成"""
        from beeref.fileio.sequence_detection import SequencePattern

        # ダミーのSequencePatternを作成
        pattern = SequencePattern(
            r'^(.+?)(\d{3,})(\.\w+)$',
            prefix_group=1, number_group=2, suffix_group=3,
            description="test pattern"
        )

        # SequenceGroupを作成
        group = SequenceGroup('frame_', '.png', pattern)
        for i, file_path in enumerate(test_sequence_files):
            group.add_file(i, file_path)

        item = create_sequence_item_from_group(group, fps=24.0)

        assert item is not None
        assert isinstance(item, BeeSequenceItem)
        assert item.get_frame_count() == 5

    def test_create_from_empty_group(self, qapp):
        """空のSequenceGroupからの作成"""
        from beeref.fileio.sequence_detection import SequencePattern

        pattern = SequencePattern(
            r'^(.+?)(\d{3,})(\.\w+)$',
            prefix_group=1, number_group=2, suffix_group=3,
            description="test pattern"
        )

        group = SequenceGroup('', '.png', pattern)

        item = create_sequence_item_from_group(group, fps=12.0)

        assert item is None

    def test_create_from_none_group(self, qapp):
        """Noneでの作成"""
        item = create_sequence_item_from_group(None, fps=12.0)

        assert item is None

    @patch('beeref.fileio.sequence_import.get_sequence_info')
    def test_sequence_info_integration(
            self, mock_get_info, qapp, test_sequence_files):
        """get_sequence_info関数との連携テスト"""
        from beeref.fileio.sequence_detection import SequencePattern

        mock_get_info.return_value = {
            'pattern': 'frame_###.png',
            'prefix': 'frame_',
            'suffix': '.png'
        }

        pattern = SequencePattern(
            r'^(.+?)(\d{3,})(\.\w+)$',
            prefix_group=1, number_group=2, suffix_group=3,
            description="test pattern"
        )

        group = SequenceGroup('frame_', '.png', pattern)
        for i, file_path in enumerate(test_sequence_files):
            group.add_file(i, file_path)

        item = create_sequence_item_from_group(group, fps=12.0)

        assert item is not None
        assert 'frame_' in item.filename
        assert item._frame_metadata['prefix'] == 'frame_'
        mock_get_info.assert_called_once_with(group)


class TestImportSequencesFromDirectory:
    """import_sequences_from_directory関数のテスト"""

    @patch('beeref.fileio.sequence_import.detect_image_sequences')
    def test_import_with_sequences_found(
            self, mock_detect, qapp, test_sequence_files):
        """シーケンスが見つかった場合のインポート"""
        from beeref.fileio.sequence_detection import SequencePattern

        # モックのSequenceGroupを作成
        pattern = SequencePattern(
            r'^(.+?)(\d{3,})(\.\w+)$',
            prefix_group=1, number_group=2, suffix_group=3,
            description="test pattern"
        )

        group = SequenceGroup('frame_', '.png', pattern)
        for i, file_path in enumerate(test_sequence_files):
            group.add_file(i, file_path)

        mock_detect.return_value = [group]

        with patch(
                'beeref.fileio.sequence_import.create_sequence_item_from_group'
        ) as mock_create:
            mock_item = MagicMock(spec=BeeSequenceItem)
            mock_item.filename = 'Test Sequence'
            mock_create.return_value = mock_item

            items = import_sequences_from_directory(
                '/fake/path', fps=24.0, min_sequence_length=3)

            assert len(items) == 1
            assert items[0] is mock_item
            mock_detect.assert_called_once_with(
                '/fake/path', min_sequence_length=3)
            mock_create.assert_called_once_with(group, 24.0)

    @patch('beeref.fileio.sequence_import.detect_image_sequences')
    def test_import_no_sequences_found(self, mock_detect, qapp):
        """シーケンスが見つからない場合"""
        mock_detect.return_value = []

        items = import_sequences_from_directory('/fake/path', fps=12.0)

        assert items == []
        mock_detect.assert_called_once()

    @patch('beeref.fileio.sequence_import.detect_image_sequences')
    def test_import_error_handling(self, mock_detect, qapp):
        """エラー発生時の処理"""
        mock_detect.side_effect = Exception('Test error')

        items = import_sequences_from_directory('/fake/path')

        assert items == []

    @patch('beeref.fileio.sequence_import.detect_image_sequences')
    def test_import_failed_item_creation(
            self, mock_detect, qapp, test_sequence_files):
        """アイテム作成失敗時の処理"""
        from beeref.fileio.sequence_detection import SequencePattern

        pattern = SequencePattern(
            r'^(.+?)(\d{3,})(\.\w+)$',
            prefix_group=1, number_group=2, suffix_group=3,
            description="test pattern"
        )

        group = SequenceGroup('frame_', '.png', pattern)
        for i, file_path in enumerate(test_sequence_files):
            group.add_file(i, file_path)

        mock_detect.return_value = [group]

        with patch(
                'beeref.fileio.sequence_import.create_sequence_item_from_group'
        ) as mock_create:
            mock_create.return_value = None  # 作成失敗

            items = import_sequences_from_directory('/fake/path')

            assert items == []


class TestDetectFpsFromFilenames:
    """detect_fps_from_filenames関数のテスト"""

    def test_detect_fps_pattern_basic(self, qapp):
        """基本的なFPSパターン検出"""
        filenames = [
            'animation_24fps_001.png',
            'animation_24fps_002.png'
        ]

        fps = detect_fps_from_filenames(filenames)

        assert fps == 24.0

    def test_detect_fps_various_patterns(self, qapp):
        """様々なFPSパターンの検出"""
        test_cases = [
            (['test_30fps.png'], 30.0),
            (['fps60_frame.png'], 60.0),
            (['render_12_fps_001.png'], 12.0),
            (['fps_24_sequence.png'], 24.0),
            (['movie_15f_001.png'], 15.0),
        ]

        for filenames, expected_fps in test_cases:
            fps = detect_fps_from_filenames(filenames)
            assert fps == expected_fps

    def test_detect_fps_out_of_range(self, qapp):
        """範囲外のFPS値は検出されない"""
        filenames = ['test_150fps.png', 'test_0fps.png']

        fps = detect_fps_from_filenames(filenames)

        assert fps is None

    def test_detect_fps_no_pattern(self, qapp):
        """FPSパターンがない場合"""
        filenames = ['frame_001.png', 'frame_002.png']

        fps = detect_fps_from_filenames(filenames)

        assert fps is None

    def test_detect_fps_common_fps_guess(self, qapp):
        """ファイル数からの一般的なFPS推測"""
        # 24ファイル = 24fps の可能性
        filenames = [f'frame_{i:03d}.png' for i in range(24)]

        fps = detect_fps_from_filenames(filenames)

        # 実装では12が最初に見つかるため
        assert fps == 12.0

    def test_detect_fps_multiple_common_fps(self, qapp):
        """複数の一般的なFPSに該当する場合（最初のものが選ばれる）"""
        # 12ファイル = 12fps が最初に見つかる
        filenames = [f'frame_{i:03d}.png' for i in range(12)]

        fps = detect_fps_from_filenames(filenames)

        assert fps == 12.0

    def test_detect_fps_no_guess_possible(self, qapp):
        """推測できない場合"""
        filenames = [f'frame_{i:03d}.png' for i in range(7)]  # 一般的なFPSの倍数ではない

        fps = detect_fps_from_filenames(filenames)

        assert fps is None


class TestValidateSequenceFiles:
    """validate_sequence_files関数のテスト"""

    def test_validate_empty_list(self, qapp):
        """空のリストの検証"""
        valid, errors = validate_sequence_files([])

        assert valid is False
        assert 'No files provided' in errors[0]

    def test_validate_valid_files(self, qapp, test_sequence_files):
        """有効なファイルの検証"""
        valid, errors = validate_sequence_files(test_sequence_files)

        assert valid is True
        assert errors == []

    def test_validate_missing_files(self, qapp, temp_dir):
        """存在しないファイルの検証"""
        missing_files = [
            os.path.join(temp_dir, 'missing1.png'),
            os.path.join(temp_dir, 'missing2.png')
        ]

        valid, errors = validate_sequence_files(missing_files)

        assert valid is False
        assert any('Missing files' in error for error in errors)

    def test_validate_unsupported_formats(self, qapp, temp_dir):
        """サポートされていない形式の検証"""
        unsupported_file = os.path.join(temp_dir, 'test.txt')
        with open(unsupported_file, 'w') as f:
            f.write('not an image')

        valid, errors = validate_sequence_files([unsupported_file])

        assert valid is False
        assert any('Unsupported image formats' in error for error in errors)

    def test_validate_corrupted_images(self, qapp, temp_dir):
        """破損画像の検証"""
        corrupted_file = os.path.join(temp_dir, 'corrupted.png')
        with open(corrupted_file, 'wb') as f:
            f.write(b'not_a_png_file')

        valid, errors = validate_sequence_files([corrupted_file])

        assert valid is False
        assert any('Cannot load images' in error for error in errors)

    def test_validate_mixed_conditions(
            self, qapp, test_sequence_files, temp_dir):
        """複数の問題がある場合の検証"""
        missing_file = os.path.join(temp_dir, 'missing.png')
        unsupported_file = os.path.join(temp_dir, 'test.txt')
        with open(unsupported_file, 'w') as f:
            f.write('text file')

        files = test_sequence_files + [missing_file, unsupported_file]

        valid, errors = validate_sequence_files(files)

        assert valid is False
        assert len(errors) >= 2  # 複数のエラーが報告される


class TestGetSequenceImportInfo:
    """get_sequence_import_info関数のテスト"""

    def test_get_info_valid_files(self, qapp, test_sequence_files):
        """有効なファイルの情報取得"""
        info = get_sequence_import_info(test_sequence_files)

        assert info['file_count'] == 5
        assert info['valid'] is True
        assert info['errors'] == []
        assert info['suggested_fps'] == 12.0  # デフォルト
        assert info['total_size_mb'] > 0
        assert info['estimated_memory_mb'] > 0

    def test_get_info_invalid_files(self, qapp):
        """無効なファイルの情報取得"""
        invalid_files = ['/nonexistent/file.png']

        info = get_sequence_import_info(invalid_files)

        assert info['file_count'] == 1
        assert info['valid'] is False
        assert len(info['errors']) > 0

    @patch('beeref.fileio.sequence_import.detect_fps_from_filenames')
    def test_get_info_fps_detection(
            self,
            mock_detect_fps,
            qapp,
            test_sequence_files):
        """FPS検出機能のテスト"""
        mock_detect_fps.return_value = 30.0

        info = get_sequence_import_info(test_sequence_files)

        assert info['suggested_fps'] == 30.0
        mock_detect_fps.assert_called_once_with(test_sequence_files)

    def test_get_info_size_calculation(self, qapp, test_sequence_files):
        """ファイルサイズ計算のテスト"""
        info = get_sequence_import_info(test_sequence_files)

        # ファイルサイズが計算されている
        assert info['total_size_mb'] > 0
        # メモリ使用量推定値がファイルサイズの2倍程度
        assert info['estimated_memory_mb'] >= info['total_size_mb'] * 1.5


class TestUtilityFunctions:
    """ユーティリティ関数のテスト"""

    def test_natural_sort_key(self, qapp):
        """自然順序ソートキーのテスト"""
        filenames = ['file10.png', 'file2.png', 'file1.png', 'file20.png']
        sorted_filenames = sorted(filenames, key=_natural_sort_key)

        expected = ['file1.png', 'file2.png', 'file10.png', 'file20.png']
        assert sorted_filenames == expected

    def test_natural_sort_key_complex(self, qapp):
        """複雑な自然順序ソートのテスト"""
        filenames = [
            'seq_001_a.png',
            'seq_10_b.png',
            'seq_2_c.png',
            'seq_001_b.png'
        ]
        sorted_filenames = sorted(filenames, key=_natural_sort_key)

        expected = [
            'seq_001_a.png',
            'seq_001_b.png',
            'seq_2_c.png',
            'seq_10_b.png'
        ]
        assert sorted_filenames == expected

    def test_detect_sequence_pattern(self, qapp):
        """シーケンスパターン検出のテスト"""
        test_cases = [
            (['frame_0001.png'], '4桁以上の数字'),
            (['seq_001.png'], '3桁の数字'),
            (['img_1.png'], '数字'),
            (['nopattern.png'], 'パターン不明')
        ]

        for filenames, expected_pattern in test_cases:
            pattern = _detect_sequence_pattern(filenames)
            assert pattern == expected_pattern

    def test_detect_sequence_pattern_empty(self, qapp):
        """空のファイルリストでのパターン検出"""
        pattern = _detect_sequence_pattern([])
        assert pattern == 'unknown'


class TestIntegration:
    """統合テスト"""

    def test_full_workflow_integration(self, qapp, temp_dir):
        """完全なワークフロー統合テスト"""
        # 連番ファイルを作成
        sequence_files = []
        for i in range(3):
            filepath = os.path.join(temp_dir, f'animation_{i:04d}.png')
            create_test_image_file(filepath)
            sequence_files.append(filepath)

        # 1. 検証
        valid, errors = validate_sequence_files(sequence_files)
        assert valid is True

        # 2. 情報取得
        info = get_sequence_import_info(sequence_files)
        assert info['valid'] is True
        assert info['file_count'] == 3

        # 3. シーケンス作成
        item = create_sequence_item_from_files(
            sequence_files, fps=info['suggested_fps'])
        assert item is not None
        assert item.get_frame_count() == 3

        # 4. フレームアクセス
        pixmap = item.get_frame_pixmap(0)
        assert not pixmap.isNull()

    def test_error_recovery_integration(self, qapp, temp_dir):
        """エラー回復統合テスト"""
        # 有効ファイルと無効ファイルの混在
        valid_file = os.path.join(temp_dir, 'valid_001.png')
        invalid_file = os.path.join(temp_dir, 'invalid.txt')

        create_test_image_file(valid_file)
        with open(invalid_file, 'w') as f:
            f.write('not an image')

        files = [valid_file, invalid_file]

        # 検証で問題が検出される
        valid, errors = validate_sequence_files(files)
        assert valid is False

        # しかし、有効なファイルのみでシーケンス作成は可能
        item = create_sequence_item_from_files([valid_file], fps=12.0)
        assert item is not None
        assert item.get_frame_count() == 1
