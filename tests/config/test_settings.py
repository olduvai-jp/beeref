import os
import os.path
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from PyQt6 import QtGui

from beeref.config.settings import CommandlineArgs


def test_command_line_args_singleton():
    assert CommandlineArgs() is CommandlineArgs()
    assert CommandlineArgs()._args is CommandlineArgs()._args
    CommandlineArgs._instance = None


@patch('beeref.config.settings.parser.parse_args')
def test_command_line_args_with_check_forces_new_parsing(parse_mock):
    args1 = CommandlineArgs()
    args2 = CommandlineArgs(with_check=True)
    parse_mock.assert_called_once()
    assert args1 is not args2
    CommandlineArgs._instance = None


def test_command_line_args_get():
    args = CommandlineArgs()
    assert args.loglevel == 'INFO'
    CommandlineArgs._instance = None


def test_command_line_args_get_unknown():
    args = CommandlineArgs()
    with pytest.raises(AttributeError):
        args.foo
    CommandlineArgs._instance = None


def test_settings_on_startup_sets_alloc_from_settings(settings):
    settings.setValue('Items/image_allocation_limit', 66)
    QtGui.QImageReader.setAllocationLimit(100)
    settings.on_startup()
    assert QtGui.QImageReader.allocationLimit() == 66


def test_settings_on_startup_sets_alloc_from_environment(settings):
    settings.setValue('Items/image_allocation_limit', 66)
    os.environ['QT_IMAGEIO_MAXALLOC'] = '42'
    QtGui.QImageReader.setAllocationLimit(100)
    settings.on_startup()
    assert QtGui.QImageReader.allocationLimit() == 42


def test_settings_set_value_without_callback(settings):
    settings.FIELDS = {'foo/bar': {}}
    settings.setValue('foo/bar', 100)
    assert settings.value('foo/bar') == 100


def test_settings_set_value_with_callback(settings):
    foo_callback = MagicMock()
    settings.FIELDS = {'foo/bar': {'post_save_callback': foo_callback}}
    settings.setValue('foo/bar', 100)
    foo_callback.assert_called_once_with(100)
    assert settings.value('foo/bar') == 100


def test_settings_remove_without_callback(settings):
    settings.FIELDS = {'foo/bar': {}}
    settings.remove('foo/bar')
    assert settings.value('foo/bar') is None


def test_settings_remove_with_callback(settings):
    foo_callback = MagicMock()
    settings.FIELDS = {
        'foo/bar': {'default': 66,
                    'post_save_callback': foo_callback}
    }
    settings.remove('foo/bar')
    foo_callback.assert_called_once_with(66)
    assert settings.value('foo/bar') is None


def test_settings_value_or_default_gets_default(settings):
    assert settings.valueOrDefault('Items/image_storage_format') == 'best'


def test_settings_value_or_default_gets_overriden_value(settings):
    settings.setValue('Items/image_storage_format', 'png')
    assert settings.valueOrDefault('Items/image_storage_format') == 'png'


def test_settings_value_or_default_gets_default_when_invalid(settings):
    settings.setValue('Items/image_storage_format', 'foo')
    assert settings.valueOrDefault('Items/image_storage_format') == 'best'


def test_settings_value_or_default_casts_value(settings):
    settings.setValue('Items/arrange_gap', '5')
    assert settings.valueOrDefault('Items/arrange_gap') == 5


def test_settings_value_or_default_gets_default_when_cast_error(settings):
    settings.setValue('Items/arrange_gap', 'foo')
    assert settings.valueOrDefault('Items/arrange_gap') == 0


def test_settings_value_changed_when_default(settings):
    assert settings.value_changed('Items/image_storage_format') is False


def test_settings_value_changed_when_chagned(settings):
    settings.setValue('Items/image_storage_format', 'jpg')
    assert settings.value_changed('Items/image_storage_format') is True


def test_settings_restore_defaults_restores(settings):
    settings.setValue('Items/image_storage_format', 'png')
    settings.restore_defaults()
    assert settings.contains('Items/image_storage_format') is False


def test_settings_restore_defaults_leaves_other_settings(settings):
    settings.setValue('foo/bar', 'baz')
    settings.restore_defaults()
    assert settings.contains('foo/bar') is True
    assert settings.value('foo/bar') == 'baz'


def test_settings_recent_files_get_empty(settings):
    settings.get_recent_files() == []


def test_settings_recent_files_get_existing_only(settings):
    with tempfile.NamedTemporaryFile() as f:
        settings.update_recent_files('foo.bee')
        settings.update_recent_files(f.name)
    settings.get_recent_files(existing_only=True) == [f.name]


def test_settings_recent_files_update(settings):
    settings.update_recent_files('foo.bee')
    settings.update_recent_files('bar.bee')
    assert settings.get_recent_files() == [
        os.path.abspath('bar.bee'),
        os.path.abspath('foo.bee')]


def test_settings_recent_files_update_existing(settings):
    settings.update_recent_files('foo.bee')
    settings.update_recent_files('bar.bee')
    settings.update_recent_files('foo.bee')
    assert settings.get_recent_files() == [
        os.path.abspath('foo.bee'),
        os.path.abspath('bar.bee')]


def test_settings_recent_files_update_respects_max_num(settings):
    for i in range(15):
        settings.update_recent_files(f'{i}.bee')

    recent = settings.get_recent_files()
    assert len(recent) == 10
    assert recent[0] == os.path.abspath('14.bee')
    assert recent[-1] == os.path.abspath('5.bee')


def test_animation_export_format_default(settings):
    """アニメーションエクスポート形式設定のデフォルト値テスト"""
    assert (settings.valueOrDefault('Items/animation_export_format') ==
            'same_as_source')


def test_animation_export_format_valid_values(settings):
    """アニメーションエクスポート形式設定の有効値テスト"""
    # Same as Source形式
    settings.setValue('Items/animation_export_format', 'same_as_source')
    assert (settings.valueOrDefault('Items/animation_export_format') ==
            'same_as_source')

    # GIF形式
    settings.setValue('Items/animation_export_format', 'gif')
    assert settings.valueOrDefault('Items/animation_export_format') == 'gif'

    # WebP形式
    settings.setValue('Items/animation_export_format', 'webp')
    assert settings.valueOrDefault('Items/animation_export_format') == 'webp'


def test_animation_export_format_invalid_value_returns_default(settings):
    """アニメーションエクスポート形式設定の無効値でデフォルト値が返されることをテスト"""
    settings.setValue('Items/animation_export_format', 'invalid_format')
    assert (settings.valueOrDefault('Items/animation_export_format') ==
            'same_as_source')


def test_animation_export_format_value_changed(settings):
    """アニメーションエクスポート形式設定の変更検出テスト"""
    # デフォルト値では変更なし
    assert settings.value_changed('Items/animation_export_format') is False

    # 値を変更
    settings.setValue('Items/animation_export_format', 'webp')
    assert settings.value_changed('Items/animation_export_format') is True

    # デフォルト値に戻すと変更なしになる
    settings.setValue('Items/animation_export_format', 'same_as_source')
    assert settings.value_changed('Items/animation_export_format') is False


def test_animation_frame_cache_size_default(settings):
    """アニメーションフレームキャッシュサイズ設定のデフォルト値テスト"""
    assert settings.valueOrDefault('Items/animation_frame_cache_size') == 10


def test_animation_frame_cache_size_valid_range(settings):
    """アニメーションフレームキャッシュサイズ設定の有効範囲テスト"""
    # 最小値
    settings.setValue('Items/animation_frame_cache_size', 1)
    assert settings.valueOrDefault('Items/animation_frame_cache_size') == 1

    # 中間値
    settings.setValue('Items/animation_frame_cache_size', 25)
    assert settings.valueOrDefault('Items/animation_frame_cache_size') == 25

    # 最大値
    settings.setValue('Items/animation_frame_cache_size', 50)
    assert settings.valueOrDefault('Items/animation_frame_cache_size') == 50


def test_animation_frame_cache_size_invalid_range_returns_default(settings):
    """アニメーションフレームキャッシュサイズ設定の無効範囲でデフォルト値が返されることをテスト"""
    # 範囲外の値（小さすぎる）
    settings.setValue('Items/animation_frame_cache_size', 0)
    assert settings.valueOrDefault('Items/animation_frame_cache_size') == 10

    # 範囲外の値（大きすぎる）
    settings.setValue('Items/animation_frame_cache_size', 51)
    assert settings.valueOrDefault('Items/animation_frame_cache_size') == 10


def test_animation_frame_cache_size_type_casting(settings):
    """アニメーションフレームキャッシュサイズ設定の型変換テスト"""
    # 文字列から整数へ変換
    settings.setValue('Items/animation_frame_cache_size', '15')
    assert settings.valueOrDefault('Items/animation_frame_cache_size') == 15

    # 無効な文字列の場合はデフォルト値
    settings.setValue('Items/animation_frame_cache_size', 'invalid')
    assert settings.valueOrDefault('Items/animation_frame_cache_size') == 10


def test_animation_settings_value_changed(settings):
    """アニメーション設定項目の変更検出テスト"""
    # animation_frame_cache_size
    assert settings.value_changed('Items/animation_frame_cache_size') is False
    settings.setValue('Items/animation_frame_cache_size', 20)
    assert settings.value_changed('Items/animation_frame_cache_size') is True


def test_same_as_source_export_format_setting(settings):
    """Same as Source エクスポート形式設定の詳細テスト"""
    # デフォルト値がsame_as_sourceであることを確認
    assert (settings.valueOrDefault('Items/animation_export_format') ==
            'same_as_source')

    # same_as_sourceが有効な値として認識されることを確認
    settings.setValue('Items/animation_export_format', 'same_as_source')
    assert (settings.valueOrDefault('Items/animation_export_format') ==
            'same_as_source')

    # 無効な値の場合はsame_as_sourceにフォールバックすることを確認
    settings.setValue('Items/animation_export_format', 'invalid')
    assert (settings.valueOrDefault('Items/animation_export_format') ==
            'same_as_source')

    # 他の有効な値も設定できることを確認
    settings.setValue('Items/animation_export_format', 'gif')
    assert settings.valueOrDefault('Items/animation_export_format') == 'gif'

    settings.setValue('Items/animation_export_format', 'webp')
    assert settings.valueOrDefault('Items/animation_export_format') == 'webp'


def test_same_as_source_value_changed_detection(settings):
    """Same as Source設定の変更検出テスト"""
    # デフォルト値では変更なし
    assert settings.value_changed('Items/animation_export_format') is False

    # 他の値に変更すると変更有り
    settings.setValue('Items/animation_export_format', 'gif')
    assert settings.value_changed('Items/animation_export_format') is True

    settings.setValue('Items/animation_export_format', 'webp')
    assert settings.value_changed('Items/animation_export_format') is True

    # デフォルト値（same_as_source）に戻すと変更なし
    settings.setValue('Items/animation_export_format', 'same_as_source')
    assert settings.value_changed('Items/animation_export_format') is False


def test_animation_default_fps_default_value(settings):
    """アニメーションデフォルトFPS設定のデフォルト値テスト"""
    assert settings.valueOrDefault('Items/animation_default_fps') == 8


def test_animation_default_fps_valid_range(settings):
    """アニメーションデフォルトFPS設定の有効範囲テスト"""
    # 最小値
    settings.setValue('Items/animation_default_fps', 1)
    assert settings.valueOrDefault('Items/animation_default_fps') == 1

    # 中間値
    settings.setValue('Items/animation_default_fps', 30)
    assert settings.valueOrDefault('Items/animation_default_fps') == 30

    # 最大値
    settings.setValue('Items/animation_default_fps', 60)
    assert settings.valueOrDefault('Items/animation_default_fps') == 60


def test_animation_default_fps_invalid_range_returns_default(settings):
    """アニメーションデフォルトFPS設定の無効範囲でデフォルト値が返されることをテスト"""
    # 範囲外の値（小さすぎる）
    settings.setValue('Items/animation_default_fps', 0)
    assert settings.valueOrDefault('Items/animation_default_fps') == 8

    # 範囲外の値（大きすぎる）
    settings.setValue('Items/animation_default_fps', 61)
    assert settings.valueOrDefault('Items/animation_default_fps') == 8

    # 負の値
    settings.setValue('Items/animation_default_fps', -5)
    assert settings.valueOrDefault('Items/animation_default_fps') == 8


def test_animation_default_fps_type_casting(settings):
    """アニメーションデフォルトFPS設定の型変換テスト"""
    # 文字列から整数へ変換
    settings.setValue('Items/animation_default_fps', '25')
    assert settings.valueOrDefault('Items/animation_default_fps') == 25

    # 浮動小数点数から整数へ変換
    settings.setValue('Items/animation_default_fps', 15.7)
    assert settings.valueOrDefault('Items/animation_default_fps') == 15

    # 無効な文字列の場合はデフォルト値
    settings.setValue('Items/animation_default_fps', 'invalid')
    assert settings.valueOrDefault('Items/animation_default_fps') == 8

    # Noneの場合はデフォルト値
    settings.setValue('Items/animation_default_fps', None)
    assert settings.valueOrDefault('Items/animation_default_fps') == 8


def test_animation_default_fps_edge_cases(settings):
    """アニメーションデフォルトFPS設定のエッジケーステスト"""
    # 境界値テスト
    # 1 FPS（最小値）
    settings.setValue('Items/animation_default_fps', 1)
    assert settings.valueOrDefault('Items/animation_default_fps') == 1

    # 60 FPS（最大値）
    settings.setValue('Items/animation_default_fps', 60)
    assert settings.valueOrDefault('Items/animation_default_fps') == 60

    # 0（最小値の下）
    settings.setValue('Items/animation_default_fps', 0)
    assert settings.valueOrDefault('Items/animation_default_fps') == 8

    # 61（最大値の上）
    settings.setValue('Items/animation_default_fps', 61)
    assert settings.valueOrDefault('Items/animation_default_fps') == 8


def test_animation_default_fps_value_changed(settings):
    """アニメーションデフォルトFPS設定の変更検出テスト"""
    # デフォルト値では変更なし
    assert settings.value_changed('Items/animation_default_fps') is False

    # 値を変更
    settings.setValue('Items/animation_default_fps', 20)
    assert settings.value_changed('Items/animation_default_fps') is True

    # デフォルト値に戻すと変更なし
    settings.setValue('Items/animation_default_fps', 8)
    assert settings.value_changed('Items/animation_default_fps') is False


def test_animation_default_fps_common_values(settings):
    """アニメーションデフォルトFPS設定の一般的な値テスト"""
    # 一般的なFPS値をテスト
    common_fps_values = [1, 5, 8, 10, 12, 15, 24, 25, 30, 50, 60]

    for fps in common_fps_values:
        settings.setValue('Items/animation_default_fps', fps)
        assert settings.valueOrDefault('Items/animation_default_fps') == fps
        assert settings.value_changed('Items/animation_default_fps') == (fps != 8)
