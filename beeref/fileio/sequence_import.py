# This file is part of BeeRef.
#
# BeeRef is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BeeRef is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BeeRef.  If not, see <https://www.gnu.org/licenses/>.

"""連番画像のインポート機能"""

import logging
import os.path
from typing import List, Optional, Dict, Tuple

from PyQt6 import QtGui

from beeref.items import BeeSequenceItem
from .sequence_detection import (
    SequenceGroup, detect_image_sequences, get_sequence_info
)

logger = logging.getLogger(__name__)


def create_sequence_item_from_files(
        file_paths: List[str],
        fps: float = 12.0,
        detect_fps: bool = True) -> Optional[BeeSequenceItem]:
    """
    ファイルパスリストからBeeSequenceItemを作成

    Args:
        file_paths: 連番画像ファイルのパスリスト
        fps: フレームレート（detect_fps=Falseの場合使用）
        detect_fps: ファイル名からフレームレートを自動検出するか

    Returns:
        作成されたBeeSequenceItem、失敗時はNone
    """
    if not file_paths:
        logger.warning("No files provided for sequence creation")
        return None

    # ファイルの存在確認
    valid_files = []
    for file_path in file_paths:
        if os.path.exists(file_path) and os.path.isfile(file_path):
            valid_files.append(file_path)
        else:
            logger.warning(f"File not found or not a file: {file_path}")

    if not valid_files:
        logger.error("No valid files found for sequence creation")
        return None

    # ファイル名でソート（自然順序）
    valid_files.sort(key=_natural_sort_key)

    try:
        item = BeeSequenceItem()

        # 最初のファイルからベース情報を取得
        first_file = valid_files[0]
        item.filename = f"Sequence from {os.path.basename(first_file)}"

        # 各ファイルをフレームとして追加
        frame_duration = int(1000 / fps)  # ミリ秒
        for file_path in valid_files:
            try:
                # 画像を読み込み
                pixmap = QtGui.QPixmap(file_path)
                if pixmap.isNull():
                    logger.warning(f"Failed to load image: {file_path}")
                    continue

                # フレームとして追加
                frame_filename = os.path.basename(file_path)
                item.add_frame(pixmap, frame_filename, frame_duration)

                logger.debug(f"Added frame: {frame_filename}")

            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                continue

        if item.get_frame_count() == 0:
            logger.error("No frames were successfully added to the sequence")
            return None

        # メタデータを設定
        item._frame_metadata.update({
            'fps': fps,
            'loop': True,
            'source_directory': os.path.dirname(first_file),
            'sequence_pattern': _detect_sequence_pattern(valid_files)
        })

        logger.info(
            f"Created sequence item with {item.get_frame_count()} frames "
            f"at {fps} fps from {len(valid_files)} files")

        return item

    except Exception as e:
        logger.error(f"Failed to create sequence item: {e}")
        return None


def create_sequence_item_from_group(
        sequence_group: SequenceGroup,
        fps: float = 12.0) -> Optional[BeeSequenceItem]:
    """
    SequenceGroupからBeeSequenceItemを作成

    Args:
        sequence_group: 連番グループ
        fps: フレームレート

    Returns:
        作成されたBeeSequenceItem、失敗時はNone
    """
    if not sequence_group or not sequence_group.files:
        logger.warning("Empty or invalid sequence group")
        return None

    file_paths = sequence_group.get_sorted_files()
    item = create_sequence_item_from_files(file_paths, fps)

    if item:
        # SequenceGroupの情報を追加
        info = get_sequence_info(sequence_group)
        item.filename = f"Sequence: {info['prefix']}*{info['suffix']}"
        item._frame_metadata.update({
            'sequence_pattern': info['pattern'],
            'prefix': info['prefix'],
            'suffix': info['suffix']
        })

    return item


def import_sequences_from_directory(
        directory_path: str,
        fps: float = 12.0,
        min_sequence_length: int = 3) -> List[BeeSequenceItem]:
    """
    ディレクトリから連番画像を検出してBeeSequenceItemを作成

    Args:
        directory_path: 検索対象ディレクトリ
        fps: フレームレート
        min_sequence_length: 連番として認識する最小ファイル数

    Returns:
        作成されたBeeSequenceItemのリスト
    """
    try:
        # 連番を検出
        sequence_groups = detect_image_sequences(
            directory_path,
            min_sequence_length=min_sequence_length
        )

        if not sequence_groups:
            logger.info(f"No image sequences found in {directory_path}")
            return []

        sequence_items = []
        for group in sequence_groups:
            item = create_sequence_item_from_group(group, fps)
            if item:
                sequence_items.append(item)
                logger.info(f"Created sequence: {item.filename}")

        logger.info(
            f"Imported {len(sequence_items)} sequences from {directory_path}")

        return sequence_items

    except Exception as e:
        logger.error(f"Error importing sequences from {directory_path}: {e}")
        return []


def detect_fps_from_filenames(file_paths: List[str]) -> Optional[float]:
    """
    ファイル名からフレームレートを推測

    Args:
        file_paths: ファイルパスリスト

    Returns:
        推測されたFPS、検出できない場合はNone
    """
    import re

    # 一般的なFPS値のパターンを検索
    fps_patterns = [
        r'(\d+)fps',
        r'fps(\d+)',
        r'(\d+)_fps',
        r'fps_(\d+)',
        r'_(\d+)f(?:ps)?_',
    ]

    for file_path in file_paths:
        filename = os.path.basename(file_path).lower()
        for pattern in fps_patterns:
            match = re.search(pattern, filename)
            if match:
                try:
                    fps = float(match.group(1))
                    if 1 <= fps <= 120:  # 妥当な範囲
                        logger.debug(f"Detected FPS {fps} from {filename}")
                        return fps
                except ValueError:
                    continue

    # ファイル数からFPSを推測（秒数を仮定）
    if len(file_paths) > 1:
        # 12fps、24fps、30fps等の一般的な値を返す
        common_fps = [12, 24, 30, 60]
        for fps in common_fps:
            if len(file_paths) % fps == 0:
                logger.debug(f"Guessed FPS {fps} based on file count")
                return fps

    return None


def _natural_sort_key(file_path: str) -> List:
    """自然順序ソート用のキー生成"""
    import re
    filename = os.path.basename(file_path)
    parts = re.split('([0-9]+)', filename)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def _detect_sequence_pattern(file_paths: List[str]) -> str:
    """ファイルパスリストから連番パターンを検出"""
    if not file_paths:
        return "unknown"

    # 最初のファイルでパターンを判定
    filename = os.path.basename(file_paths[0])

    # 数字部分を検出
    import re
    if re.search(r'\d{4,}', filename):
        return "4桁以上の数字"
    elif re.search(r'\d{3}', filename):
        return "3桁の数字"
    elif re.search(r'\d+', filename):
        return "数字"
    else:
        return "パターン不明"


def validate_sequence_files(file_paths: List[str]) -> Tuple[bool, List[str]]:
    """
    連番ファイルの検証

    Args:
        file_paths: 検証するファイルパスリスト

    Returns:
        (検証結果, エラーメッセージリスト)
    """
    errors = []

    if not file_paths:
        errors.append("No files provided")
        return False, errors

    # ファイル存在確認
    missing_files = []
    for file_path in file_paths:
        if not os.path.exists(file_path):
            missing_files.append(file_path)

    if missing_files:
        errors.append(f"Missing files: {', '.join(missing_files)}")

    # 画像形式確認
    supported_extensions = {
        '.png',
        '.jpg',
        '.jpeg',
        '.gif',
        '.bmp',
        '.tiff',
        '.webp'}
    invalid_files = []
    for file_path in file_paths:
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in supported_extensions:
            invalid_files.append(file_path)

    if invalid_files:
        errors.append(f"Unsupported image formats: {', '.join(invalid_files)}")

    # 画像読み込み確認（最初の数ファイルのみ）
    load_test_files = file_paths[:min(3, len(file_paths))]
    unloadable_files = []
    for file_path in load_test_files:
        try:
            pixmap = QtGui.QPixmap(file_path)
            if pixmap.isNull():
                unloadable_files.append(file_path)
        except Exception:
            unloadable_files.append(file_path)

    if unloadable_files:
        errors.append(f"Cannot load images: {', '.join(unloadable_files)}")

    return len(errors) == 0, errors


def get_sequence_import_info(file_paths: List[str]) -> Dict:
    """
    連番インポートの情報を取得

    Args:
        file_paths: ファイルパスリスト

    Returns:
        インポート情報の辞書
    """
    info = {
        'file_count': len(file_paths),
        'valid': False,
        'errors': [],
        'suggested_fps': 12.0,
        'total_size_mb': 0.0,
        'estimated_memory_mb': 0.0,
    }

    # 検証
    valid, errors = validate_sequence_files(file_paths)
    info['valid'] = valid
    info['errors'] = errors

    if not valid:
        return info

    # FPS推測
    detected_fps = detect_fps_from_filenames(file_paths)
    if detected_fps:
        info['suggested_fps'] = detected_fps

    # ファイルサイズ計算
    total_size = 0
    for file_path in file_paths:
        try:
            total_size += os.path.getsize(file_path)
        except OSError:
            pass

    info['total_size_mb'] = total_size / (1024 * 1024)
    # メモリ使用量の推定（展開時のおおよその目安）
    info['estimated_memory_mb'] = info['total_size_mb'] * 2

    return info
