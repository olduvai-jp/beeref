from unittest.mock import patch

from PyQt6 import QtWidgets

from beeref.widgets.settings import (
    AnimationCacheSizeWidget,
    AnimationFormatWidget,
    ArrangeGapWidget,
    ConfirmCloseUnsavedWidget,
    ImageStorageFormatWidget,
    SettingsDialog,
)


def test_image_storage_format_sets_title_when_not_edited(settings, view):
    widget = ImageStorageFormatWidget()
    assert widget.title() == 'Image Storage Format:'


def test_image_storage_format_sets_title_when_edited(settings, view):
    settings.setValue('Items/image_storage_format', 'jpg')
    widget = ImageStorageFormatWidget()
    assert widget.title() == 'Image Storage Format: ✎'


def test_image_storage_format_selects_radiobox(settings, view):
    settings.setValue('Items/image_storage_format', 'jpg')
    widget = ImageStorageFormatWidget()
    assert widget.buttons['best'].isChecked() is False
    assert widget.buttons['png'].isChecked() is False
    assert widget.buttons['jpg'].isChecked() is True


def test_image_storage_format_saves_change(settings, view):
    settings.setValue('Items/image_storage_format', 'best')
    widget = ImageStorageFormatWidget()
    widget.set_value('jpg')
    assert widget.buttons['best'].isChecked() is False
    assert widget.buttons['png'].isChecked() is False
    assert widget.buttons['jpg'].isChecked() is True
    assert settings.valueOrDefault('Items/image_storage_format') == 'jpg'
    assert widget.title() == 'Image Storage Format: ✎'


def test_image_storage_format_on_restore_defaults(settings, view):
    widget = ImageStorageFormatWidget()
    widget.set_value('jpg')
    settings.setValue('Items/image_storage_format', 'best')
    widget.on_restore_defaults()
    assert widget.buttons['best'].isChecked() is True
    assert widget.buttons['png'].isChecked() is False
    assert widget.buttons['jpg'].isChecked() is False
    assert widget.title() == 'Image Storage Format:'


def test_arrange_gap_initialises_input_from_settings(settings, view):
    settings.setValue('Items/arrange_gap', 6)
    widget = ArrangeGapWidget()
    assert widget.input.value() == 6


def test_arrange_gap_sets_title_when_not_edited(settings, view):
    widget = ArrangeGapWidget()
    assert widget.title() == 'Arrange Gap:'


def test_arrange_gap_sets_title_when_edited(settings, view):
    settings.setValue('Items/arrange_gap', 6)
    widget = ArrangeGapWidget()
    assert widget.title() == 'Arrange Gap: ✎'


def test_arrange_gap_saves_change(settings, view):
    settings.setValue('Items/arrange_gap', 6)
    widget = ArrangeGapWidget()
    widget.set_value(8)
    assert settings.valueOrDefault('Items/arrange_gap') == 8
    assert widget.title() == 'Arrange Gap: ✎'


def test_arrange_gap_on_restore_defaults(settings, view):
    widget = ArrangeGapWidget()
    widget.set_value(7)
    settings.setValue('Items/arrange_gap', 0)
    widget.on_restore_defaults()
    assert widget.input.value() == 0
    assert widget.title() == 'Arrange Gap:'


def test_confirm_closed_initialises_input_from_settings(settings, view):
    settings.setValue('Save/confirm_close_unsaved', False)
    widget = ConfirmCloseUnsavedWidget()
    assert widget.input.isChecked() is False


def test_confirm_closed_sets_title_when_not_edited(settings, view):
    widget = ConfirmCloseUnsavedWidget()
    assert widget.title() == 'Confirm when closing an unsaved file:'


def test_confirm_closed_sets_title_when_edited(settings, view):
    settings.setValue('Save/confirm_close_unsaved', False)
    widget = ConfirmCloseUnsavedWidget()
    assert widget.title() == 'Confirm when closing an unsaved file: ✎'


def test_confirm_closed_saves_change(settings, view):
    settings.setValue('Save/confirm_close_unsaved', True)
    widget = ConfirmCloseUnsavedWidget()
    widget.set_value(False)
    assert settings.valueOrDefault('Save/confirm_close_unsaved') is False
    assert widget.title() == 'Confirm when closing an unsaved file: ✎'


def test_confirm_closed_on_restore_defaults(settings, view):
    widget = ConfirmCloseUnsavedWidget()
    widget.set_value(False)
    settings.setValue('Save/confirm_close_unsaved', True)
    widget.on_restore_defaults()
    assert widget.input.isChecked() is True
    assert widget.title() == 'Confirm when closing an unsaved file:'


@patch('PyQt6.QtWidgets.QMessageBox.question',
       return_value=QtWidgets.QMessageBox.StandardButton.Yes)
def test_settings_dialog_on_restore_defaults(msg_mock, settings, view):
    dialog = SettingsDialog(view)
    settings.setValue('Items/image_storage_format', 'jpg')
    settings.setValue('Items/arrange_gap', 10)
    settings.setValue('Save/confirm_close_unsaved', False)
    settings.setValue('Items/animation_frame_cache_size', 25)
    dialog.on_restore_defaults()
    msg_mock.assert_called_once()
    assert settings.valueOrDefault('Items/image_storage_format') == 'best'
    assert settings.valueOrDefault('Items/arrange_gap') == 0
    assert settings.valueOrDefault('Save/confirm_close_unsaved') is True
    assert settings.valueOrDefault('Items/animation_frame_cache_size') == 10


def test_animation_format_sets_title_when_not_edited(settings, view):
    """AnimationFormatWidget: 未編集時のタイトル設定"""
    from beeref.widgets.settings import AnimationFormatWidget
    widget = AnimationFormatWidget()
    assert widget.title() == 'Animation Export Format:'


def test_animation_format_sets_title_when_edited(settings, view):
    """AnimationFormatWidget: 編集時のタイトル設定"""
    from beeref.widgets.settings import AnimationFormatWidget
    settings.setValue('Items/animation_export_format', 'webp')
    widget = AnimationFormatWidget()
    assert widget.title() == 'Animation Export Format: ✎'


def test_animation_format_selects_radiobox(settings, view):
    """AnimationFormatWidget: ラジオボタンの選択状態確認"""
    from beeref.widgets.settings import AnimationFormatWidget
    settings.setValue('Items/animation_export_format', 'webp')
    widget = AnimationFormatWidget()
    assert widget.buttons['gif'].isChecked() is False
    assert widget.buttons['webp'].isChecked() is True


def test_animation_format_saves_change(settings, view):
    """AnimationFormatWidget: 値変更の保存確認"""
    from beeref.widgets.settings import AnimationFormatWidget
    settings.setValue('Items/animation_export_format', 'gif')
    widget = AnimationFormatWidget()
    widget.set_value('webp')
    assert widget.buttons['gif'].isChecked() is False
    assert widget.buttons['webp'].isChecked() is True
    assert settings.valueOrDefault('Items/animation_export_format') == 'webp'
    assert widget.title() == 'Animation Export Format: ✎'


def test_animation_format_on_restore_defaults(settings, view):
    """AnimationFormatWidget: デフォルト復元テスト"""
    from beeref.widgets.settings import AnimationFormatWidget
    widget = AnimationFormatWidget()
    widget.set_value('webp')
    settings.setValue('Items/animation_export_format', 'same_as_source')
    widget.on_restore_defaults()
    assert widget.buttons['same_as_source'].isChecked() is True
    assert widget.buttons['webp'].isChecked() is False
    # デフォルト復元後は編集マークが消える
    assert widget.title() == 'Animation Export Format:'


def test_animation_format_initial_state(settings, view):
    """AnimationFormatWidget: 初期状態の確認"""
    from beeref.widgets.settings import AnimationFormatWidget
    widget = AnimationFormatWidget()

    # デフォルト値の確認（同じソース形式がデフォルト）
    assert widget.buttons['same_as_source'].isChecked() is True
    assert widget.buttons['gif'].isChecked() is False
    assert widget.buttons['webp'].isChecked() is False

    # オプションの確認
    assert 'same_as_source' in widget.buttons
    assert 'gif' in widget.buttons
    assert 'webp' in widget.buttons
    assert len(widget.buttons) == 3  # same_as_source, gif, webp の3つ


def test_animation_cache_size_sets_title_when_not_edited(settings, view):
    """AnimationCacheSizeWidget: 未編集時のタイトル設定"""
    widget = AnimationCacheSizeWidget()
    assert widget.title() == 'Animation Frame Cache:'


def test_animation_cache_size_sets_title_when_edited(settings, view):
    """AnimationCacheSizeWidget: 編集時のタイトル設定"""
    settings.setValue('Items/animation_frame_cache_size', 20)
    widget = AnimationCacheSizeWidget()
    assert widget.title() == 'Animation Frame Cache: ✎'


def test_animation_cache_size_saves_change(settings, view):
    """AnimationCacheSizeWidget: 値変更の保存確認"""
    settings.setValue('Items/animation_frame_cache_size', 10)
    widget = AnimationCacheSizeWidget()
    widget.set_value(25)
    assert widget.input.value() == 25
    assert settings.valueOrDefault('Items/animation_frame_cache_size') == 25
    assert widget.title() == 'Animation Frame Cache: ✎'


def test_animation_cache_size_on_restore_defaults(settings, view):
    """AnimationCacheSizeWidget: デフォルト復元テスト"""
    widget = AnimationCacheSizeWidget()
    widget.set_value(30)
    settings.setValue('Items/animation_frame_cache_size', 10)
    widget.on_restore_defaults()
    assert widget.input.value() == 10
    assert widget.title() == 'Animation Frame Cache:'


def test_animation_cache_size_initial_state(settings, view):
    """AnimationCacheSizeWidget: 初期状態の確認"""
    widget = AnimationCacheSizeWidget()
    
    # デフォルト値の確認（10がデフォルト）
    assert widget.input.value() == 10
    
    # 範囲の確認
    assert widget.input.minimum() == 1
    assert widget.input.maximum() == 50


def test_settings_dialog_has_animation_tab(settings, view):
    """SettingsDialog: Animationタブが存在することを確認"""
    dialog = SettingsDialog(view)
    tabs = dialog.findChild(QtWidgets.QTabWidget)
    
    # タブの数を確認（Miscellaneous, Images & Items, Animation）
    assert tabs.count() == 3
    
    # Animationタブの存在確認
    animation_tab_index = None
    for i in range(tabs.count()):
        if tabs.tabText(i) == '&Animation':
            animation_tab_index = i
            break
    
    assert animation_tab_index is not None, "Animationタブが見つかりません"


def test_settings_dialog_animation_tab_contains_widgets(settings, view):
    """SettingsDialog: AnimationタブにAnimationFormatWidgetとAnimationCacheSizeWidgetが含まれることを確認"""
    dialog = SettingsDialog(view)
    tabs = dialog.findChild(QtWidgets.QTabWidget)
    
    # Animationタブを取得
    animation_tab = None
    for i in range(tabs.count()):
        if tabs.tabText(i) == '&Animation':
            animation_tab = tabs.widget(i)
            break
    
    assert animation_tab is not None, "Animationタブが見つかりません"
    
    # AnimationFormatWidgetとAnimationCacheSizeWidgetが含まれることを確認
    animation_format_widget = animation_tab.findChild(AnimationFormatWidget)
    animation_cache_widget = animation_tab.findChild(AnimationCacheSizeWidget)
    
    assert animation_format_widget is not None, "AnimationFormatWidgetが見つかりません"
    assert animation_cache_widget is not None, "AnimationCacheSizeWidgetが見つかりません"


def test_animation_default_fps_sets_title_when_not_edited(settings, view):
    """AnimationDefaultFpsWidget: 未編集時のタイトル設定"""
    from beeref.widgets.settings import AnimationDefaultFpsWidget
    widget = AnimationDefaultFpsWidget()
    assert widget.title() == 'Default Animation FPS:'


def test_animation_default_fps_sets_title_when_edited(settings, view):
    """AnimationDefaultFpsWidget: 編集時のタイトル設定"""
    from beeref.widgets.settings import AnimationDefaultFpsWidget
    settings.setValue('Items/animation_default_fps', 25)
    widget = AnimationDefaultFpsWidget()
    assert widget.title() == 'Default Animation FPS: ✎'


def test_animation_default_fps_initialises_input_from_settings(settings, view):
    """AnimationDefaultFpsWidget: 設定からの初期化"""
    from beeref.widgets.settings import AnimationDefaultFpsWidget
    settings.setValue('Items/animation_default_fps', 24)
    widget = AnimationDefaultFpsWidget()
    assert widget.input.value() == 24


def test_animation_default_fps_saves_change(settings, view):
    """AnimationDefaultFpsWidget: 値変更の保存確認"""
    from beeref.widgets.settings import AnimationDefaultFpsWidget
    settings.setValue('Items/animation_default_fps', 10)
    widget = AnimationDefaultFpsWidget()
    widget.set_value(30)
    assert widget.input.value() == 30
    assert settings.valueOrDefault('Items/animation_default_fps') == 30
    assert widget.title() == 'Default Animation FPS: ✎'


def test_animation_default_fps_on_restore_defaults(settings, view):
    """AnimationDefaultFpsWidget: デフォルト復元テスト"""
    from beeref.widgets.settings import AnimationDefaultFpsWidget
    widget = AnimationDefaultFpsWidget()
    widget.set_value(45)
    settings.setValue('Items/animation_default_fps', 10)
    widget.on_restore_defaults()
    assert widget.input.value() == 10
    assert widget.title() == 'Default Animation FPS:'


def test_animation_default_fps_initial_state(settings, view):
    """AnimationDefaultFpsWidget: 初期状態の確認"""
    from beeref.widgets.settings import AnimationDefaultFpsWidget
    widget = AnimationDefaultFpsWidget()
    
    # デフォルト値の確認（10がデフォルト）
    assert widget.input.value() == 10
    
    # 範囲の確認
    assert widget.input.minimum() == 1
    assert widget.input.maximum() == 60


def test_animation_default_fps_range_validation(settings, view):
    """AnimationDefaultFpsWidget: 範囲バリデーションテスト"""
    from beeref.widgets.settings import AnimationDefaultFpsWidget
    widget = AnimationDefaultFpsWidget()
    
    # 最小値
    widget.set_value(1)
    assert widget.input.value() == 1
    assert settings.valueOrDefault('Items/animation_default_fps') == 1
    
    # 最大値
    widget.set_value(60)
    assert widget.input.value() == 60
    assert settings.valueOrDefault('Items/animation_default_fps') == 60
    
    # 中間値
    widget.set_value(24)
    assert widget.input.value() == 24
    assert settings.valueOrDefault('Items/animation_default_fps') == 24


def test_animation_default_fps_edge_case_values(settings, view):
    """AnimationDefaultFpsWidget: エッジケース値のテスト"""
    from beeref.widgets.settings import AnimationDefaultFpsWidget
    widget = AnimationDefaultFpsWidget()
    
    # 境界値の確認
    # UIウィジェット自体が範囲制限を行うため、無効な値は設定できない
    # ただし、プログラマティックに設定することをテスト
    
    # 一般的なアニメーションFPS値
    common_fps_values = [12, 15, 24, 25, 30, 50]
    for fps in common_fps_values:
        widget.set_value(fps)
        assert widget.input.value() == fps
        assert settings.valueOrDefault('Items/animation_default_fps') == fps


def test_settings_dialog_animation_tab_contains_fps_widget(settings, view):
    """SettingsDialog: AnimationタブにAnimationDefaultFpsWidgetが含まれることを確認"""
    from beeref.widgets.settings import AnimationDefaultFpsWidget
    dialog = SettingsDialog(view)
    tabs = dialog.findChild(QtWidgets.QTabWidget)
    
    # Animationタブを取得
    animation_tab = None
    for i in range(tabs.count()):
        if tabs.tabText(i) == '&Animation':
            animation_tab = tabs.widget(i)
            break
    
    assert animation_tab is not None, "Animationタブが見つかりません"
    
    # AnimationDefaultFpsWidgetが含まれることを確認
    animation_fps_widget = animation_tab.findChild(AnimationDefaultFpsWidget)
    assert animation_fps_widget is not None, "AnimationDefaultFpsWidgetが見つかりません"


def test_animation_default_fps_widget_value_change_callback(settings, view):
    """AnimationDefaultFpsWidget: 値変更コールバックテスト"""
    from beeref.widgets.settings import AnimationDefaultFpsWidget
    widget = AnimationDefaultFpsWidget()
    
    # 初期値確認
    initial_value = settings.valueOrDefault('Items/animation_default_fps')
    assert initial_value == 10
    
    # ウィジェットで値を変更
    widget.input.setValue(20)
    widget.on_value_changed(20)
    
    # 設定が更新されることを確認
    assert settings.valueOrDefault('Items/animation_default_fps') == 20
    
    # タイトルが更新されることを確認
    assert widget.title() == 'Default Animation FPS: ✎'
