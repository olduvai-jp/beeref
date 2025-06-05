import os
import stat
from unittest.mock import MagicMock
import pytest

from PyQt6 import QtGui

from beeref.items import BeePixmapItem, BeeAnimatedPixmapItem
from beeref.fileio.errors import BeeFileIOError
from beeref.fileio.export import SelectedImagesToDirectoryExporter


def test_selected_images_to_directory_exporter_export_selected_only(
        view, tmpdir, imgdata3x3, imgfilename3x3):
    """選択された画像アイテムのみがエクスポートされることを確認"""
    # 3つの画像アイテムを作成
    item1 = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    item1.save_id = 1
    view.scene.addItem(item1)
    
    item2 = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    item2.save_id = 2
    view.scene.addItem(item2)
    
    item3 = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    item3.save_id = 3
    view.scene.addItem(item3)
    
    # item1とitem3のみを選択
    item1.setSelected(True)
    item3.setSelected(True)
    
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    exporter.export()
    
    # 選択されたアイテムのファイルのみが作成されることを確認
    assert os.path.exists(os.path.join(tmpdir, '0001.png'))
    assert not os.path.exists(os.path.join(tmpdir, '0002.png'))  # 選択されていない
    assert os.path.exists(os.path.join(tmpdir, '0003.png'))
    
    # ファイル内容が画像であることを確認
    with open(os.path.join(tmpdir, '0001.png'), 'rb') as f:
        assert f.read().startswith(b'\x89PNG')
    with open(os.path.join(tmpdir, '0003.png'), 'rb') as f:
        assert f.read().startswith(b'\x89PNG')


def test_selected_images_to_directory_exporter_pixmap_and_animated(
        view, tmpdir, imgfilename3x3):
    """静止画とアニメーション画像の両方が対象となることを確認"""
    # 静止画アイテム
    pixmap_item = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    pixmap_item.save_id = 1
    view.scene.addItem(pixmap_item)
    
    # アニメーション画像アイテム（正しい形式で作成）
    animation_data = {
        'frames': [QtGui.QImage(imgfilename3x3), QtGui.QImage(imgfilename3x3)],
        'fps': 10
    }
    animated_item = BeeAnimatedPixmapItem(animation_data)
    animated_item.save_id = 2
    view.scene.addItem(animated_item)
    
    # 両方を選択
    pixmap_item.setSelected(True)
    animated_item.setSelected(True)
    
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    
    # アイテムが正しくフィルタリングされていることを確認
    assert len(exporter.items) == 2
    assert pixmap_item in exporter.items
    assert animated_item in exporter.items


def test_selected_images_to_directory_exporter_no_image_items_selected(
        view, tmpdir, imgfilename3x3):
    """画像アイテムが選択されていない場合の処理"""
    # 画像アイテムを作成するが選択しない
    item1 = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    view.scene.addItem(item1)
    
    item2 = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    view.scene.addItem(item2)
    
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    
    # 選択されたアイテムがないことを確認
    assert len(exporter.items) == 0
    assert exporter.num_total == 0
    
    # エクスポートが正常に完了することを確認
    exporter.export()
    
    # ファイルが作成されないことを確認
    assert len(os.listdir(tmpdir)) == 0


def test_selected_images_to_directory_exporter_text_item_only_selected(
        view, tmpdir):
    """画像以外のアイテム（テキストなど）のみが選択されている場合の処理"""
    from beeref.items import BeeTextItem
    
    # テキストアイテムを作成して選択
    text_item = BeeTextItem('Test text')
    text_item.setSelected(True)
    view.scene.addItem(text_item)
    
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    
    # 画像アイテムが選択されていないことを確認
    assert len(exporter.items) == 0
    assert exporter.num_total == 0
    
    # エクスポートが正常に完了することを確認
    exporter.export()
    
    # ファイルが作成されないことを確認
    assert len(os.listdir(tmpdir)) == 0


def test_selected_images_to_directory_exporter_mixed_selection(
        view, tmpdir, imgfilename3x3):
    """画像アイテムとテキストアイテムが混在した選択の場合"""
    from beeref.items import BeeTextItem
    
    # 画像アイテム
    image_item = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    image_item.save_id = 1
    view.scene.addItem(image_item)
    
    # テキストアイテム
    text_item = BeeTextItem('Test text')
    view.scene.addItem(text_item)
    
    # 両方を選択
    image_item.setSelected(True)
    text_item.setSelected(True)
    
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    
    # 画像アイテムのみがフィルタリングされることを確認
    assert len(exporter.items) == 1
    assert image_item in exporter.items
    assert exporter.num_total == 1
    
    exporter.export()
    
    # 画像ファイルのみが作成されることを確認
    assert os.path.exists(os.path.join(tmpdir, '0001.png'))
    with open(os.path.join(tmpdir, '0001.png'), 'rb') as f:
        assert f.read().startswith(b'\x89PNG')


def test_selected_images_to_directory_exporter_empty_selection(
        view, tmpdir, imgfilename3x3):
    """空の選択の場合の処理"""
    # アイテムを作成するが選択しない
    item = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    view.scene.addItem(item)
    
    # 何も選択しない
    view.scene.clearSelection()
    
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    
    # 空のアイテムリストであることを確認
    assert len(exporter.items) == 0
    assert exporter.num_total == 0
    
    exporter.export()
    
    # ファイルが作成されないことを確認
    assert len(os.listdir(tmpdir)) == 0


def test_selected_images_to_directory_exporter_with_worker(
        view, tmpdir, imgfilename3x3):
    """ワーカーと連携したエクスポート"""
    item = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    item.setSelected(True)
    view.scene.addItem(item)
    
    worker = MagicMock(canceled=False)
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    exporter.export(worker)
    
    # ファイルが作成されることを確認
    assert len(os.listdir(tmpdir)) == 1
    filename = os.listdir(tmpdir)[0]
    with open(os.path.join(tmpdir, filename), 'rb') as f:
        assert f.read().startswith(b'\x89PNG')
    
    # ワーカーのメソッドが呼び出されることを確認
    worker.begin_processing.emit.assert_called_once_with(1)
    worker.progress.emit.assert_called_with(0)
    worker.finished.emit.assert_called_once_with(tmpdir, [])


def test_selected_images_to_directory_exporter_with_worker_when_canceled(
        view, tmpdir, imgfilename3x3):
    """ワーカーがキャンセルされた場合"""
    item = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    item.setSelected(True)
    view.scene.addItem(item)
    
    worker = MagicMock(canceled=True)
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    exporter.export(worker)
    
    # ファイルが作成されないことを確認
    assert len(os.listdir(tmpdir)) == 0
    
    worker.begin_processing.emit.assert_called_once_with(1)
    worker.progress.emit.assert_called_once_with(0)
    worker.finished.emit.assert_called_once_with(tmpdir, [])


def test_selected_images_to_directory_exporter_no_selected_items_with_worker(
        view, tmpdir, imgfilename3x3):
    """選択アイテムがない場合のワーカーとの連携"""
    # アイテムを作成するが選択しない
    item = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    view.scene.addItem(item)
    
    worker = MagicMock(canceled=False)
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    exporter.export(worker)
    
    # ファイルが作成されないことを確認
    assert len(os.listdir(tmpdir)) == 0
    
    # ワーカーに適切な値が送信されることを確認
    worker.begin_processing.emit.assert_called_once_with(0)
    worker.progress.emit.assert_called_once_with(0)
    worker.finished.emit.assert_called_once_with(tmpdir, [])


def test_selected_images_to_directory_exporter_file_exists_handling(
        view, tmpdir, imgfilename3x3):
    """ファイルが既に存在する場合の処理"""
    item = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    item.save_id = 1
    item.setSelected(True)
    view.scene.addItem(item)
    
    # 同名ファイルを先に作成
    existing_file = os.path.join(tmpdir, '0001.png')
    with open(existing_file, 'w') as f:
        f.write('existing content')
    
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    exporter.handle_existing = 'skip'
    exporter.export()
    
    # 既存ファイルが保持されることを確認
    with open(existing_file, 'r') as f:
        assert f.read() == 'existing content'


def test_selected_images_to_directory_exporter_inheritance_from_base(
        view, tmpdir):
    """ImagesToDirectoryExporterからの継承が正しく動作することを確認"""
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    
    # 基底クラスの属性が継承されていることを確認
    assert hasattr(exporter, 'scene')
    assert hasattr(exporter, 'dirname')
    assert hasattr(exporter, 'items')
    assert hasattr(exporter, 'max_save_id')
    assert hasattr(exporter, 'num_total')
    assert hasattr(exporter, 'start_from')
    assert hasattr(exporter, 'handle_existing')
    
    # 基底クラスのメソッドが使用可能であることを確認
    assert hasattr(exporter, 'export')
    assert hasattr(exporter, 'emit_begin_processing')
    assert hasattr(exporter, 'emit_progress')
    assert hasattr(exporter, 'emit_finished')


def test_selected_images_to_directory_exporter_max_save_id_calculation(
        view, tmpdir, imgfilename3x3):
    """選択されたアイテムのmax_save_idが正しく計算されることを確認"""
    # 異なるsave_idを持つアイテムを作成
    item1 = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    item1.save_id = 5
    view.scene.addItem(item1)
    
    item2 = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    item2.save_id = 10
    view.scene.addItem(item2)
    
    item3 = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    item3.save_id = 3
    view.scene.addItem(item3)
    
    # item1とitem2のみを選択（最大save_idは10）
    item1.setSelected(True)
    item2.setSelected(True)
    
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    
    # max_save_idが選択されたアイテムの最大値になることを確認
    assert exporter.max_save_id == 10


def test_selected_images_to_directory_exporter_when_dir_not_writeable(
        view, tmpdir, imgfilename3x3):
    """ディレクトリが書き込み不可の場合のエラーハンドリング"""
    item = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    item.setSelected(True)
    view.scene.addItem(item)
    
    # ディレクトリを読み取り専用にする
    os.chmod(tmpdir, stat.S_IREAD)
    
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    
    with pytest.raises(BeeFileIOError):
        exporter.export()


def test_selected_images_to_directory_exporter_when_dir_not_writeable_w_worker(
        view, tmpdir, imgfilename3x3):
    """ディレクトリが書き込み不可の場合のワーカーとの連携"""
    item = BeePixmapItem(QtGui.QImage(imgfilename3x3))
    item.setSelected(True)
    view.scene.addItem(item)
    
    # ディレクトリを読み取り専用にする
    os.chmod(tmpdir, stat.S_IREAD)
    
    exporter = SelectedImagesToDirectoryExporter(view.scene, tmpdir)
    worker = MagicMock(canceled=False)
    
    exporter.export(worker)
    
    # エラーがワーカーに通知されることを確認
    worker.begin_processing.emit.assert_called_once_with(1)
    worker.finished.emit.assert_called_once()
    args = worker.finished.emit.call_args.args
    assert args[0] == tmpdir
    assert len(args[1]) == 1  # エラーが1つ報告される