import os
import pytest
from unittest.mock import patch, MagicMock

from PyQt6 import QtCore, QtGui

from beeref.items import BeeSequenceItem, BeePixmapItem
from beeref.fileio.export import ImagesToDirectoryExporter


def create_test_pixmap(width=10, height=10, color=QtCore.Qt.GlobalColor.red):
    """テスト用のQPixmapを作成"""
    pixmap = QtGui.QPixmap(width, height)
    pixmap.fill(color)
    return pixmap


@pytest.fixture
def sequence_item_with_frames():
    """テスト用のSequenceItemフィクスチャ（複数フレーム付き）"""
    item = BeeSequenceItem()
    item.filename = 'test_sequence.png'
    item.save_id = 1

    # 3つのフレームを追加（異なる色）
    colors = [
        QtCore.Qt.GlobalColor.red,
        QtCore.Qt.GlobalColor.green,
        QtCore.Qt.GlobalColor.blue]
    for i, color in enumerate(colors):
        pixmap = create_test_pixmap(20, 20, color)
        item.add_frame(pixmap, f'frame_{i:03d}.png', 100)

    return item


class TestSequenceItemExportMethods:
    """SequenceItem固有のエクスポートメソッドテスト"""

    def test_export_frame_to_bytes_valid_frame(
            self, qapp, sequence_item_with_frames):
        """有効なフレームインデックスでのバイト変換テスト"""
        data, format_type = sequence_item_with_frames.export_frame_to_bytes(0)

        assert isinstance(data, bytes)
        assert len(data) > 0
        assert format_type == 'png'
        assert data.startswith(b'\x89PNG')

    def test_export_frame_to_bytes_all_frames(
            self, qapp, sequence_item_with_frames):
        """全フレームのバイト変換テスト"""
        frame_count = sequence_item_with_frames.get_frame_count()

        for frame_idx in range(frame_count):
            data, format_type = (
                sequence_item_with_frames.export_frame_to_bytes(frame_idx))

            assert isinstance(data, bytes)
            assert len(data) > 0
            assert format_type == 'png'
            assert data.startswith(b'\x89PNG')

    def test_export_frame_to_bytes_with_target_format(
            self, qapp, sequence_item_with_frames):
        """指定形式でのバイト変換テスト"""
        data, format_type = sequence_item_with_frames.export_frame_to_bytes(
            0, 'jpg')

        assert isinstance(data, bytes)
        assert len(data) > 0
        assert format_type == 'jpg'
        # JPEGの場合はFFD8で始まる
        assert data.startswith(b'\xff\xd8')

    def test_export_frame_to_bytes_invalid_index(
            self, qapp, sequence_item_with_frames):
        """無効なフレームインデックスでのエラーテスト"""
        frame_count = sequence_item_with_frames.get_frame_count()

        # 範囲外のインデックス
        with pytest.raises(IndexError) as excinfo:
            sequence_item_with_frames.export_frame_to_bytes(frame_count)
        assert "out of range" in str(excinfo.value)

        # 負のインデックス
        with pytest.raises(IndexError) as excinfo:
            sequence_item_with_frames.export_frame_to_bytes(-1)
        assert "out of range" in str(excinfo.value)

    def test_export_frame_to_bytes_with_grayscale(
            self, qapp, sequence_item_with_frames):
        """グレースケール適用でのバイト変換テスト"""
        sequence_item_with_frames.grayscale = True

        data, format_type = sequence_item_with_frames.export_frame_to_bytes(0)

        assert isinstance(data, bytes)
        assert len(data) > 0
        assert format_type == 'png'
        assert data.startswith(b'\x89PNG')

    def test_get_frame_export_filename_with_filename(
            self, qapp, sequence_item_with_frames):
        """ファイル名ありでのエクスポートファイル名生成テスト"""
        filename = sequence_item_with_frames.get_frame_export_filename(0)

        assert filename == 'frame_000.png'

    def test_get_frame_export_filename_without_filename(self, qapp):
        """ファイル名なしでのエクスポートファイル名生成テスト"""
        item = BeeSequenceItem()
        item.save_id = 2

        # フレーム追加
        pixmap = create_test_pixmap()
        item.add_frame(pixmap, 'test_frame.png', 100)

        filename = item.get_frame_export_filename(0)

        assert filename == 'test_frame.png'

    def test_get_frame_export_filename_with_save_id_default(self, qapp):
        """デフォルトsave_idでのファイル名生成テスト"""
        item = BeeSequenceItem()
        item.filename = 'test.png'
        # save_idは設定しない

        # フレーム追加
        pixmap = create_test_pixmap()
        item.add_frame(pixmap, 'frame.png', 100)

        filename = item.get_frame_export_filename(0, save_id_default=5)

        assert filename == 'frame.png'

    def test_get_frame_export_folder_and_filename_with_filename(
            self, qapp, sequence_item_with_frames):
        """フォルダ名とファイル名の生成テスト（ファイル名あり）"""
        folder_name, filename = (
            sequence_item_with_frames.get_frame_export_folder_and_filename(0))

        assert folder_name == '0001-Sequence'
        assert filename == 'frame_000.png'

    def test_get_frame_export_folder_and_filename_without_filename(self, qapp):
        """フォルダ名とファイル名の生成テスト（ファイル名なし）"""
        item = BeeSequenceItem()
        item.save_id = 2

        # フレーム追加
        pixmap = create_test_pixmap()
        item.add_frame(pixmap, 'test_frame.png', 100)

        folder_name, filename = item.get_frame_export_folder_and_filename(0)

        assert folder_name == '0002-Sequence'
        assert filename == 'test_frame.png'

    def test_get_frame_export_folder_and_filename_with_save_id_default(
            self,
            qapp):
        """デフォルトsave_idでのフォルダ名とファイル名生成テスト"""
        item = BeeSequenceItem()
        item.filename = 'test.png'
        # save_idは設定しない

        # フレーム追加
        pixmap = create_test_pixmap()
        item.add_frame(pixmap, 'frame.png', 100)

        folder_name, filename = item.get_frame_export_folder_and_filename(
            0, save_id_default=5)

        assert folder_name == '0005-Sequence'
        assert filename == 'frame.png'

    def test_get_frame_export_filename_invalid_index(
            self, qapp, sequence_item_with_frames):
        """無効なインデックスでのエラーテスト"""
        frame_count = sequence_item_with_frames.get_frame_count()

        with pytest.raises(IndexError) as excinfo:
            sequence_item_with_frames.get_frame_export_filename(frame_count)
        assert "out of range" in str(excinfo.value)

    def test_get_frame_export_filename_no_save_id(self, qapp):
        """save_idなしでのエラーテスト"""
        item = BeeSequenceItem()
        pixmap = create_test_pixmap()
        item.add_frame(pixmap, 'frame.png', 100)

        with pytest.raises(AssertionError) as excinfo:
            item.get_frame_export_filename(0)
        assert "save_id must be provided" in str(excinfo.value)

    def test_get_frame_export_filename_no_original_filename(self, qapp):
        """元のファイル名がない場合のテスト"""
        item = BeeSequenceItem()
        item.save_id = 1

        # 元のファイル名なしでフレーム追加
        pixmap = create_test_pixmap()
        item.add_frame(pixmap, '', 100)  # 空文字列

        filename = item.get_frame_export_filename(0)
        folder_name, filename_new = item.get_frame_export_folder_and_filename(
            0)

        # 元のファイル名がない場合はframe_001.pngのような形式
        assert filename == 'frame_001.png'
        assert folder_name == '0001-Sequence'
        assert filename_new == 'frame_001.png'

    def test_different_format_detection(self, qapp):
        """異なる形式のファイル名からの形式判定テスト"""
        item = BeeSequenceItem()
        item.save_id = 1

        test_cases = [
            ('frame.jpg', 'jpg'),
            ('frame.jpeg', 'jpg'),
            ('frame.webp', 'webp'),
            ('frame.bmp', 'bmp'),
            ('frame.tiff', 'tiff'),
            ('frame.gif', 'png'),  # GIFはPNGとして扱う
            ('frame.unknown', 'png'),  # 不明な形式はPNG
        ]

        for original_filename, expected_format in test_cases:
            pixmap = create_test_pixmap()
            item._frame_data.clear()  # フレームデータをクリア
            item.add_frame(pixmap, original_filename, 100)

            data, format_type = item.export_frame_to_bytes(0)
            assert format_type == expected_format


class TestImagesToDirectoryExporterSequenceIntegration:
    """ImagesToDirectoryExporterでのSequenceItem統合テスト"""

    def test_export_sequence_frames_individually(self, view, tmpdir):
        """SequenceItemフレームの個別エクスポートテスト"""
        # テスト用SequenceItemを作成
        item = BeeSequenceItem()
        item.filename = 'test_sequence.png'
        item.save_id = 10

        # 3つのフレームを追加
        for i in range(3):
            pixmap = create_test_pixmap(15, 15)
            item.add_frame(pixmap, f'frame_{i:03d}.png', 100)

        view.scene.addItem(item)

        # animation_format設定をモック
        with patch('beeref.fileio.export.BeeSettings') as mock_settings:
            mock_settings.return_value.valueOrDefault.return_value = (
                'same_as_source')

            exporter = ImagesToDirectoryExporter(view.scene, tmpdir)
            exporter.export()

        # エクスポートされたフォルダの確認
        exported_items = os.listdir(tmpdir)
        assert len(exported_items) == 1
        assert '0010-Sequence' in exported_items

        # フォルダ内のファイル確認
        sequence_dir = os.path.join(tmpdir, '0010-Sequence')
        frame_files = os.listdir(sequence_dir)
        assert len(frame_files) == 3

        # ファイル名の形式確認
        expected_files = [
            'frame_000.png',
            'frame_001.png',
            'frame_002.png'
        ]

        for expected_file in expected_files:
            assert expected_file in frame_files

            # ファイルがPNGとして有効か確認
            file_path = os.path.join(sequence_dir, expected_file)
            with open(file_path, 'rb') as f:
                assert f.read().startswith(b'\x89PNG')

    def test_export_sequence_with_worker(self, view, tmpdir):
        """ワーカー付きSequenceItemエクスポートテスト"""
        # テスト用SequenceItemを作成
        item = BeeSequenceItem()
        item.filename = 'worker_test.png'
        item.save_id = 20

        # 2つのフレームを追加
        for i in range(2):
            pixmap = create_test_pixmap(10, 10)
            item.add_frame(pixmap, f'frame_{i}.png', 100)

        view.scene.addItem(item)

        # ワーカーモック
        worker = MagicMock(canceled=False)

        with patch('beeref.fileio.export.BeeSettings') as mock_settings:
            mock_settings.return_value.valueOrDefault.return_value = (
                'same_as_source')

            exporter = ImagesToDirectoryExporter(view.scene, tmpdir)
            exporter.export(worker)

        # ワーカーメソッドの呼び出し確認
        worker.begin_processing.emit.assert_called_once_with(1)
        worker.finished.emit.assert_called_once()

        # エクスポートされたフォルダの確認
        exported_items = os.listdir(tmpdir)
        assert len(exported_items) == 1
        assert '0020-Sequence' in exported_items

        # フォルダ内のファイル確認
        sequence_dir = os.path.join(tmpdir, '0020-Sequence')
        frame_files = os.listdir(sequence_dir)
        assert len(frame_files) == 2

    def test_export_sequence_canceled(self, view, tmpdir):
        """キャンセルされたSequenceItemエクスポートテスト"""
        # テスト用SequenceItemを作成
        item = BeeSequenceItem()
        item.filename = 'cancel_test.png'
        item.save_id = 30

        pixmap = create_test_pixmap()
        item.add_frame(pixmap, 'frame.png', 100)

        view.scene.addItem(item)

        # キャンセルされたワーカー
        worker = MagicMock(canceled=True)

        with patch('beeref.fileio.export.BeeSettings') as mock_settings:
            mock_settings.return_value.valueOrDefault.return_value = (
                'same_as_source')

            exporter = ImagesToDirectoryExporter(view.scene, tmpdir)
            exporter.export(worker)

        # ファイルがエクスポートされていないことを確認
        exported_files = os.listdir(tmpdir)
        assert len(exported_files) == 0

        worker.finished.emit.assert_called_once_with(tmpdir, [])

    def test_export_mixed_items_with_sequence(
            self, view, tmpdir, imgfilename3x3):
        """SequenceItemと他のアイテムの混在エクスポートテスト"""
        # 通常のBeePixmapItem
        pixmap_item = BeePixmapItem(QtGui.QImage(imgfilename3x3))
        pixmap_item.save_id = 1
        view.scene.addItem(pixmap_item)

        # SequenceItem
        sequence_item = BeeSequenceItem()
        sequence_item.filename = 'mixed_test.png'
        sequence_item.save_id = 2

        pixmap = create_test_pixmap()
        sequence_item.add_frame(pixmap, 'frame.png', 100)

        view.scene.addItem(sequence_item)

        with patch('beeref.fileio.export.BeeSettings') as mock_settings:
            mock_settings.return_value.valueOrDefault.return_value = (
                'same_as_source')

            exporter = ImagesToDirectoryExporter(view.scene, tmpdir)
            exporter.export()

        # 両方のタイプがエクスポートされていることを確認
        exported_items = os.listdir(tmpdir)
        assert len(exported_items) == 2

        # BeePixmapItemのファイル
        pixmap_files = [f for f in exported_items if f.startswith(
            '0001') and os.path.isfile(os.path.join(tmpdir, f))]
        assert len(pixmap_files) == 1

        # SequenceItemのフォルダ
        sequence_folders = [f for f in exported_items if f.startswith(
            '0002') and os.path.isdir(os.path.join(tmpdir, f))]
        assert len(sequence_folders) == 1
        assert sequence_folders[0] == '0002-Sequence'

        # SequenceItemフォルダ内のファイル確認
        sequence_dir = os.path.join(tmpdir, sequence_folders[0])
        frame_files = os.listdir(sequence_dir)
        assert len(frame_files) == 1
        assert 'frame.png' in frame_files

    def test_export_sequence_with_grayscale(self, view, tmpdir):
        """グレースケール設定でのSequenceItemエクスポートテスト"""
        # テスト用SequenceItemを作成
        item = BeeSequenceItem()
        item.filename = 'grayscale_test.png'
        item.save_id = 40
        item.grayscale = True

        # カラーPixmapを追加
        pixmap = create_test_pixmap(12, 12, QtCore.Qt.GlobalColor.red)
        item.add_frame(pixmap, 'red_frame.png', 100)

        view.scene.addItem(item)

        with patch('beeref.fileio.export.BeeSettings') as mock_settings:
            mock_settings.return_value.valueOrDefault.return_value = (
                'same_as_source')

            exporter = ImagesToDirectoryExporter(view.scene, tmpdir)
            exporter.export()

        # エクスポートされたフォルダの確認
        exported_items = os.listdir(tmpdir)
        assert len(exported_items) == 1
        assert '0040-Sequence' in exported_items

        # フォルダ内のファイル確認
        sequence_dir = os.path.join(tmpdir, '0040-Sequence')
        frame_files = os.listdir(sequence_dir)
        assert len(frame_files) == 1
        assert 'red_frame.png' in frame_files

        # グレースケール処理されてもPNGとして有効
        file_path = os.path.join(sequence_dir, 'red_frame.png')
        with open(file_path, 'rb') as f:
            assert f.read().startswith(b'\x89PNG')

    def test_export_sequence_empty_frames(self, view, tmpdir):
        """空のSequenceItemのエクスポートテスト"""
        # フレームなしのSequenceItem
        item = BeeSequenceItem()
        item.filename = 'empty_test.png'
        item.save_id = 50

        view.scene.addItem(item)

        with patch('beeref.fileio.export.BeeSettings') as mock_settings:
            mock_settings.return_value.valueOrDefault.return_value = (
                'same_as_source')

            exporter = ImagesToDirectoryExporter(view.scene, tmpdir)
            exporter.export()

        # フレームがないのでファイルはエクスポートされない
        exported_files = os.listdir(tmpdir)
        assert len(exported_files) == 0


class TestSequenceExportEdgeCases:
    """SequenceItemエクスポートのエッジケーステスト"""

    def test_export_frame_with_crop(self, qapp):
        """クロップ設定でのフレームエクスポートテスト"""
        item = BeeSequenceItem()
        item.save_id = 1
        item.crop = QtCore.QRectF(2, 2, 6, 6)  # 10x10から6x6を切り出し

        pixmap = create_test_pixmap(10, 10)
        item.add_frame(pixmap, 'crop_test.png', 100)

        data, format_type = item.export_frame_to_bytes(0)

        assert isinstance(data, bytes)
        assert len(data) > 0
        assert format_type == 'png'

    def test_export_filename_special_characters(self, qapp):
        """特殊文字を含むファイル名でのエクスポートテスト"""
        item = BeeSequenceItem()
        item.filename = 'test_特殊文字_テスト.png'
        item.save_id = 1

        pixmap = create_test_pixmap()
        item.add_frame(pixmap, 'frame_特殊.png', 100)

        filename = item.get_frame_export_filename(0)
        folder_name, filename_new = item.get_frame_export_folder_and_filename(
            0)

        # 特殊文字が含まれていても正常にファイル名が生成される
        assert filename == 'frame_特殊.png'
        assert folder_name == '0001-Sequence'
        assert filename_new == 'frame_特殊.png'

    def test_export_large_frame_count(self, qapp):
        """大量のフレームでのファイル名生成テスト"""
        item = BeeSequenceItem()
        item.filename = 'large_test.png'
        item.save_id = 1

        # 100フレーム追加
        for i in range(100):
            pixmap = create_test_pixmap()
            item.add_frame(pixmap, f'frame_{i:03d}.png', 100)

        # 最後のフレームのファイル名をテスト
        filename = item.get_frame_export_filename(99)
        folder_name, filename_new = item.get_frame_export_folder_and_filename(
            99)

        # 元のファイル名をそのまま使用
        assert filename == 'frame_099.png'
        assert folder_name == '0001-Sequence'
        assert filename_new == 'frame_099.png'

    def test_export_different_format_per_frame(self, qapp):
        """フレームごとに異なる形式でのエクスポートテスト"""
        item = BeeSequenceItem()
        item.save_id = 1

        formats = ['png', 'jpg', 'webp']
        for i, fmt in enumerate(formats):
            pixmap = create_test_pixmap()
            item.add_frame(pixmap, f'frame_{i}.{fmt}', 100)

        # 各フレームが元の形式でエクスポートされる
        for i, expected_fmt in enumerate(['png', 'jpg', 'webp']):
            data, format_type = item.export_frame_to_bytes(i)
            assert format_type == expected_fmt
