from PyQt6 import QtGui

from beeref.items import sort_by_filename, BeePixmapItem, BeeTextItem, BeeAnimatedPixmapItem, item_registry


def test_sort_by_filename(view):
    item1 = BeePixmapItem(QtGui.QImage())

    item2 = BeePixmapItem(QtGui.QImage())
    item2.filename = 'foo.png'
    item2.save_id = 66

    item3 = BeePixmapItem(QtGui.QImage())
    item3.save_id = 33

    item4 = BeePixmapItem(QtGui.QImage())
    item4.filename = 'bar.png'
    item4.save_id = 77

    item5 = BeePixmapItem(QtGui.QImage())
    item5.save_id = 22

    result = sort_by_filename([item1, item2, item3, item4, item5])
    assert result == [item4, item2, item5, item3, item1]


def test_sort_by_filename_when_only_by_filename(view):
    item1 = BeePixmapItem(QtGui.QImage())
    item1.filename = 'foo.png'
    item2 = BeePixmapItem(QtGui.QImage())
    item2.filename = 'bar.png'
    assert sort_by_filename([item1, item2]) == [item2, item1]


def test_sort_by_filename_when_only_by_save_id(view):
    item1 = BeePixmapItem(QtGui.QImage())
    item1.save_id = 66
    item2 = BeePixmapItem(QtGui.QImage())
    item2.save_id = 33
    assert sort_by_filename([item1, item2]) == [item2, item1]


def test_sort_by_filename_deals_with_text_items(view):
    item1 = BeeTextItem('Foo')
    item2 = BeeTextItem('Bar')
    assert len(sort_by_filename([item1, item2])) == 2


def test_item_registry_contains_animated_pixmap():
    """アイテムレジストリにBeeAnimatedPixmapItemが登録されていることを確認"""
    assert 'animated_pixmap' in item_registry
    assert item_registry['animated_pixmap'] == BeeAnimatedPixmapItem


def test_item_registry_animated_pixmap_type():
    """BeeAnimatedPixmapItemのTYPE属性が正しいことを確認"""
    assert BeeAnimatedPixmapItem.TYPE == 'animated_pixmap'


def test_sort_by_filename_deals_with_animated_pixmap_items(view):
    """sort_by_filenameがアニメーションアイテムを適切に処理することを確認"""
    # アニメーションデータを作成
    animation_data = {
        'frames': [QtGui.QImage(2, 2, QtGui.QImage.Format.Format_ARGB32)],
        'delays': [100]
    }
    
    item1 = BeeAnimatedPixmapItem(animation_data, filename='animation1.gif')
    item1.save_id = 10
    
    item2 = BeeAnimatedPixmapItem(animation_data, filename='animation2.gif')
    item2.save_id = 5
    
    item3 = BeeAnimatedPixmapItem(animation_data)
    item3.save_id = 15
    
    # ファイル名でソートされることを確認
    result = sort_by_filename([item1, item2, item3])
    assert result == [item1, item2, item3]  # filename順: animation1, animation2, そして save_id順
