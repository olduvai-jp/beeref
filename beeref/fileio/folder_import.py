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
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from beeref.fileio.image import load_image
from beeref.fileio.sequence_detection import detect_image_sequences, get_sequence_info
from beeref.fileio.animation_generator import create_animation_from_sequence
from beeref.items import BeePixmapItem, BeeAnimatedDataItem

logger = logging.getLogger(__name__)


class FolderImportOptions:
    """フォルダインポートのオプション設定"""

    def __init__(self):
        # 対応画像形式
        self.image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp',
                                 '.tiff', '.webp', '.svg']

        # 連番検出設定
        self.min_sequence_length = 3
        self.detect_sequences = True

        # アニメーション生成設定
        self.create_animations = True
        self.animation_fps = None  # Noneの場合は設定値を使用
        self.animation_format = 'gif'

        # 処理設定
        self.include_subdirectories = False
        self.max_animation_frames = 100  # アニメーション最大フレーム数


class FolderImportResult:
    """フォルダインポートの結果"""

    def __init__(self):
        self.items: List[Dict[str, Any]] = []  # 作成されたアイテムデータのリスト
        self.errors: List[str] = []  # エラーファイルのリスト
        self.sequences_found: int = 0  # 検出された連番数
        self.animations_created: int = 0  # 作成されたアニメーション数
        self.static_images: int = 0  # 静止画数
        self.total_files_processed: int = 0  # 処理されたファイル総数


class FolderImporter:
    """フォルダインポート処理を行うクラス"""

    def __init__(self, options: Optional[FolderImportOptions] = None):
        self.options = options or FolderImportOptions()

    def import_folder(self, folder_path: str,
                      pos: Tuple[float, float] = (0, 0)) -> FolderImportResult:
        """
        フォルダから画像をインポート

        Args:
            folder_path: インポート対象フォルダパス
            pos: アイテムの配置位置

        Returns:
            インポート結果
        """
        result = FolderImportResult()

        try:
            if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
                logger.error(
                    f"Folder does not exist or is not a directory: {folder_path}")
                result.errors.append(folder_path)
                return result

            logger.info(f"Starting folder import from: {folder_path}")

            # フォルダ内の画像ファイルを取得
            image_files = self._scan_image_files(folder_path)
            if not image_files:
                logger.warning(f"No image files found in folder: {folder_path}")
                return result

            logger.debug(f"Found {len(image_files)} image files")
            result.total_files_processed = len(image_files)

            # 連番検出
            used_files = set()
            if self.options.detect_sequences:
                sequences = detect_image_sequences(
                    folder_path,
                    self.options.image_extensions,
                    self.options.min_sequence_length
                )

                result.sequences_found = len(sequences)
                logger.info(f"Detected {len(sequences)} image sequences")

                # 各連番シーケンスを処理
                for sequence in sequences:
                    sequence_result = self._process_sequence(sequence, pos)
                    if sequence_result:
                        result.items.append(sequence_result)
                        result.animations_created += 1
                        # 使用されたファイルをマーク
                        used_files.update(sequence.get_sorted_files())
                    else:
                        # アニメーション作成に失敗した場合は個別画像として処理
                        for file_path in sequence.get_sorted_files():
                            if file_path not in used_files:
                                static_result = self._process_static_image(
                                    file_path, pos)
                                if static_result:
                                    result.items.append(static_result)
                                    result.static_images += 1
                                else:
                                    result.errors.append(file_path)
                                used_files.add(file_path)

            # 連番に含まれなかった画像を個別処理
            for file_path in image_files:
                if file_path not in used_files:
                    static_result = self._process_static_image(file_path, pos)
                    if static_result:
                        result.items.append(static_result)
                        result.static_images += 1
                    else:
                        result.errors.append(file_path)

            logger.info(
                f"Folder import completed: {result.animations_created} animations, "
                f"{result.static_images} static images, {len(result.errors)} errors"
            )

            return result

        except Exception as e:
            logger.error(f"Error during folder import: {e}")
            result.errors.append(str(e))
            return result

    def _scan_image_files(self, folder_path: str) -> List[str]:
        """
        フォルダ内の画像ファイルをスキャン

        Args:
            folder_path: スキャン対象フォルダ

        Returns:
            画像ファイルパスのリスト
        """
        image_files = []

        try:
            folder = Path(folder_path)

            if self.options.include_subdirectories:
                # 再帰的にスキャン
                for file_path in folder.rglob('*'):
                    if file_path.is_file() and self._is_image_file(file_path):
                        image_files.append(str(file_path))
            else:
                # 直下のファイルのみ
                for file_path in folder.iterdir():
                    if file_path.is_file() and self._is_image_file(file_path):
                        image_files.append(str(file_path))

            return sorted(image_files)

        except Exception as e:
            logger.error(f"Error scanning image files in {folder_path}: {e}")
            return []

    def _is_image_file(self, file_path: Path) -> bool:
        """
        ファイルが画像ファイルかどうか判定

        Args:
            file_path: ファイルパス

        Returns:
            画像ファイルの場合True
        """
        return file_path.suffix.lower() in self.options.image_extensions

    def _process_sequence(self, sequence,
                          pos: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """
        連番シーケンスを処理してアニメーションアイテムデータを作成

        Args:
            sequence: SequenceGroup オブジェクト
            pos: 配置位置

        Returns:
            アニメーションアイテムデータ、失敗時はNone
        """
        if not self.options.create_animations:
            return None

        try:
            sequence_info = get_sequence_info(sequence)
            image_paths = sequence_info['files']

            # フレーム数制限チェック
            if len(image_paths) > self.options.max_animation_frames:
                logger.warning(
                    f"Sequence has too many frames ({len(image_paths)}), "
                    f"maximum is {self.options.max_animation_frames}"
                )
                return None

            logger.debug(
                f"Processing sequence: {sequence_info['prefix']}*"
                f"{sequence_info['suffix']}")

            # アニメーションデータを生成
            animation_data = create_animation_from_sequence(
                image_paths,
                self.options.animation_fps,
                self.options.animation_format
            )

            if not animation_data:
                logger.warning("Failed to create animation from sequence")
                return None

            # BeeAnimatedDataItem用のデータを準備
            item_data = {
                'type': 'animated_data',
                'data': animation_data,
                'filename': (f"sequence_{sequence_info['prefix']}_"
                             f"{len(image_paths)}_frames"),
                'pos': pos,
                'sequence_info': sequence_info
            }

            logger.debug("Created animation item data for sequence")
            return item_data

        except Exception as e:
            logger.error(f"Error processing sequence: {e}")
            return None

    def _process_static_image(self, file_path: str,
                              pos: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """
        静止画を処理してPixmapアイテムデータを作成

        Args:
            file_path: 画像ファイルパス
            pos: 配置位置

        Returns:
            Pixmapアイテムデータ、失敗時はNone
        """
        try:
            logger.debug(f"Processing static image: {file_path}")

            # 画像を読み込み
            data, filename = load_image(file_path)

            # アニメーション画像の場合
            if isinstance(data, dict) and data.get('type') == 'animated_data':
                item_data = {
                    'type': 'animated_data',
                    'data': data,
                    'filename': filename,
                    'pos': pos
                }
            else:
                # 静止画の場合
                if data.isNull():
                    logger.warning(f"Could not load image: {file_path}")
                    return None

                item_data = {
                    'type': 'pixmap',
                    'data': data,
                    'filename': filename,
                    'pos': pos
                }

            return item_data

        except Exception as e:
            logger.error(f"Error processing static image {file_path}: {e}")
            return None


def import_folder_images(
        folder_path: str,
        pos: Tuple[float, float] = (0, 0),
        options: Optional[FolderImportOptions] = None) -> FolderImportResult:
    """
    フォルダから画像をインポートする便利関数

    Args:
        folder_path: インポート対象フォルダパス
        pos: アイテムの配置位置
        options: インポートオプション

    Returns:
        インポート結果
    """
    importer = FolderImporter(options)
    return importer.import_folder(folder_path, pos)


def create_items_from_import_result(
        result: FolderImportResult,
        scene_pos: Tuple[float, float] = (0, 0)) -> Tuple[List[Any], List[str]]:
    """
    インポート結果からBeeRefアイテムを作成

    Args:
        result: フォルダインポート結果
        scene_pos: シーンでの配置位置

    Returns:
        (作成されたアイテムのリスト, エラーファイルのリスト)
    """
    items = []
    errors = result.errors.copy()

    try:
        for item_data in result.items:
            try:
                if item_data['type'] == 'animated_data':
                    # BeeAnimatedDataItemを作成
                    animation_data = item_data['data']
                    if animation_data and animation_data.get('file_data'):
                        item = BeeAnimatedDataItem(
                            animation_data['file_data'],
                            item_data['filename']
                        )
                        item.set_pos_center(scene_pos)
                        items.append(item)
                    else:
                        logger.warning(
                            f"Invalid animation data: {item_data['filename']}")
                        errors.append(item_data['filename'])

                elif item_data['type'] == 'pixmap':
                    # BeePixmapItemを作成
                    item = BeePixmapItem(item_data['data'], item_data['filename'])
                    item.set_pos_center(scene_pos)
                    items.append(item)

                else:
                    logger.warning(f"Unknown item type: {item_data['type']}")
                    errors.append(item_data.get('filename', 'unknown'))

            except Exception as e:
                logger.error(f"Error creating item from data: {e}")
                errors.append(item_data.get('filename', 'unknown'))

        logger.info(f"Created {len(items)} items from import result")
        return items, errors

    except Exception as e:
        logger.error(f"Error creating items from import result: {e}")
        return [], result.errors
