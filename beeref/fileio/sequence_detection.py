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

import logging
import os
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class SequencePattern:
    """連番パターンの定義クラス"""

    def __init__(self, pattern: str, prefix_group: int, number_group: int,
                 suffix_group: int, description: str):
        self.pattern = pattern
        self.prefix_group = prefix_group
        self.number_group = number_group
        self.suffix_group = suffix_group
        self.description = description
        self.regex = re.compile(pattern, re.IGNORECASE)


# 検出する連番パターンの定義
SEQUENCE_PATTERNS = [
    # {prefix}000x.png パターン
    SequencePattern(
        r'^(.+?)(\d{3,})(\.\w+)$',
        prefix_group=1,
        number_group=2,
        suffix_group=3,
        description="prefix + 3桁以上の数字 + 拡張子"
    ),
    # 000x.png パターン
    SequencePattern(
        r'^(\d{3,})(\.\w+)$',
        prefix_group=0,  # プレフィックスなし
        number_group=1,
        suffix_group=2,
        description="3桁以上の数字 + 拡張子"
    ),
    # x.png パターン
    SequencePattern(
        r'^(\d+)(\.\w+)$',
        prefix_group=0,  # プレフィックスなし
        number_group=1,
        suffix_group=2,
        description="数字 + 拡張子"
    ),
]


class SequenceGroup:
    """連番グループを表すクラス"""

    def __init__(self, prefix: str, suffix: str, pattern: SequencePattern):
        self.prefix = prefix
        self.suffix = suffix
        self.pattern = pattern
        self.files: List[Tuple[int, str]] = []  # (番号, ファイルパス)のリスト

    def add_file(self, number: int, filepath: str):
        """ファイルを連番グループに追加"""
        self.files.append((number, filepath))

    def get_sorted_files(self) -> List[str]:
        """番号順にソートされたファイルパスリストを取得"""
        self.files.sort(key=lambda x: x[0])
        return [filepath for _, filepath in self.files]

    def is_valid_sequence(self, min_files: int = 3) -> bool:
        """有効な連番グループかどうか判定"""
        return len(self.files) >= min_files

    def get_group_key(self) -> str:
        """グループの識別キーを取得"""
        return f"{self.prefix}_{self.suffix}_{self.pattern.description}"


class SequenceDetector:
    """連番検出エンジン"""

    def __init__(self, min_sequence_length: int = 3):
        self.min_sequence_length = min_sequence_length

    def detect_sequences(self, file_paths: List[str]) -> List[SequenceGroup]:
        """ファイルパスリストから連番グループを検出"""
        groups = defaultdict(lambda: defaultdict(lambda: None))

        # 各ファイルをパターンにマッチさせてグループ化
        for filepath in file_paths:
            filename = os.path.basename(filepath)

            for pattern in SEQUENCE_PATTERNS:
                match = pattern.regex.match(filename)
                if match:
                    # マッチした場合、グループ情報を抽出
                    if pattern.prefix_group > 0:
                        prefix = match.group(pattern.prefix_group)
                    else:
                        prefix = ""

                    number_str = match.group(pattern.number_group)
                    suffix = match.group(pattern.suffix_group)

                    try:
                        number = int(number_str)
                    except ValueError:
                        continue

                    # グループキーを生成
                    group_key = f"{prefix}_{suffix}_{pattern.description}"

                    # グループが存在しない場合は作成
                    if group_key not in groups:
                        groups[group_key] = SequenceGroup(
                            prefix, suffix, pattern)

                    # ファイルをグループに追加
                    groups[group_key].add_file(number, filepath)

                    # 最初にマッチしたパターンのみ使用
                    break

        # 有効な連番グループのみを返す
        valid_groups = []
        for group in groups.values():
            if group.is_valid_sequence(self.min_sequence_length):
                logger.debug(
                    f"Detected sequence: {group.prefix}*{group.suffix} "
                    f"({len(group.files)} files) using pattern: "
                    f"{group.pattern.description}"
                )
                valid_groups.append(group)

        return valid_groups


def detect_image_sequences(directory_path: str,
                           image_extensions: Optional[List[str]] = None,
                           min_sequence_length: int = 3) -> List[
                               SequenceGroup]:
    """
    ディレクトリ内の画像ファイルから連番を検出

    Args:
        directory_path: 検索対象ディレクトリ
        image_extensions: 対象画像拡張子リスト（None の場合は一般的な画像形式）
        min_sequence_length: 連番として認識する最小ファイル数

    Returns:
        検出された連番グループのリスト
    """
    if image_extensions is None:
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff',
                            '.webp', '.svg']

    try:
        directory = Path(directory_path)
        if not directory.exists() or not directory.is_dir():
            logger.warning(
                f"Directory does not exist or is not a directory: "
                f"{directory_path}")
            return []

        # ディレクトリ内の画像ファイルを取得
        image_files = []
        for file_path in directory.iterdir():
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in image_extensions:
                    image_files.append(str(file_path))

        if not image_files:
            logger.debug(
                f"No image files found in directory: {directory_path}")
            return []

        logger.debug(
            f"Found {len(image_files)} image files in {directory_path}")

        # 連番検出
        detector = SequenceDetector(min_sequence_length)
        sequences = detector.detect_sequences(image_files)

        logger.info(
            f"Detected {len(sequences)} image sequences in {directory_path}")

        return sequences

    except Exception as e:
        logger.error(f"Error detecting sequences in {directory_path}: {e}")
        return []


def get_sequence_info(sequence_group: SequenceGroup) -> Dict:
    """
    連番グループの情報を辞書形式で取得

    Args:
        sequence_group: 連番グループ

    Returns:
        連番情報の辞書
    """
    files = sequence_group.get_sorted_files()
    return {
        'prefix': sequence_group.prefix,
        'suffix': sequence_group.suffix,
        'pattern': sequence_group.pattern.description,
        'file_count': len(files),
        'files': files,
        'first_file': files[0] if files else None,
        'last_file': files[-1] if files else None,
    }
