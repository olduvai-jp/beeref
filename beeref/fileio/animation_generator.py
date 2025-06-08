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
import io
from typing import List, Optional, Dict, Any

from PyQt6 import QtGui

from beeref.config.settings import BeeSettings

logger = logging.getLogger(__name__)


class AnimationGenerator:
    """連番画像からアニメーションを生成するクラス"""

    def __init__(self):
        self.settings = BeeSettings()

    def create_animation_data(self,
                              image_paths: List[str],
                              fps: Optional[int] = None,
                              output_format: str = 'gif') -> Optional[
                                  Dict[str, Any]]:
        """
        連番画像リストからBeeAnimatedDataItem用のアニメーションデータを生成

        Args:
            image_paths: 連番画像ファイルパスのリスト（ソート済み）
            fps: フレームレート（Noneの場合は設定値を使用）
            output_format: 出力フォーマット（'gif' または 'webp'）

        Returns:
            アニメーションデータ辞書、失敗時はNone
        """
        if not image_paths:
            logger.warning("No image paths provided for animation generation")
            return None

        if fps is None:
            fps = self.settings.valueOrDefault('Items/animation_default_fps')

        try:
            # 最初の画像でサイズを確認
            first_image = QtGui.QImage(image_paths[0])
            if first_image.isNull():
                logger.error(f"Failed to load first image: {image_paths[0]}")
                return None

            # フレーム間隔を計算（ミリ秒）
            frame_delay = int(1000 / fps)

            logger.debug(
                f"Creating animation from {len(image_paths)} images "
                f"at {fps} FPS")

            # アニメーションファイルを生成
            animation_data = self._create_animated_file(
                image_paths, frame_delay, output_format)

            if animation_data:
                # メタデータを追加
                animation_data.update({
                    'source_files': image_paths,
                    'fps': fps,
                    'frame_count': len(image_paths),
                    'generated': True,
                })

                logger.info(
                    f"Successfully created animation from "
                    f"{len(image_paths)} images")
                return animation_data
            else:
                logger.error("Failed to create animation file")
                return None

        except Exception as e:
            logger.error(f"Error creating animation data: {e}")
            return None

    def _create_animated_file(self,
                              image_paths: List[str],
                              frame_delay: int,
                              output_format: str) -> Optional[Dict[str, Any]]:
        """
        実際のアニメーションファイルを生成

        Args:
            image_paths: 画像ファイルパスのリスト
            frame_delay: フレーム間隔（ミリ秒）
            output_format: 出力フォーマット

        Returns:
            アニメーションデータ辞書
        """
        if output_format.lower() == 'gif':
            return self._create_gif_animation(image_paths, frame_delay)
        elif output_format.lower() == 'webp':
            return self._create_webp_animation(image_paths, frame_delay)
        else:
            logger.error(f"Unsupported animation format: {output_format}")
            return None

    def _create_gif_animation(self,
                              image_paths: List[str],
                              frame_delay: int) -> Optional[Dict[str, Any]]:
        """
        PILを使用してGIFアニメーションを生成

        Args:
            image_paths: 画像ファイルパスのリスト
            frame_delay: フレーム間隔（ミリ秒）

        Returns:
            アニメーションデータ辞書
        """
        try:
            # PILで画像を読み込み
            pil_images = []
            for image_path in image_paths:
                try:
                    # QtImageからPIL Imageに変換
                    qimage = QtGui.QImage(image_path)
                    if qimage.isNull():
                        logger.warning(f"Failed to load image: {image_path}")
                        continue

                    # QImageをPIL Imageに変換
                    pil_image = self._qimage_to_pil(qimage)
                    if pil_image:
                        pil_images.append(pil_image)
                    else:
                        logger.warning(
                            f"Failed to convert image to PIL: {image_path}")
                        continue

                except Exception as e:
                    logger.warning(f"Error processing image {image_path}: {e}")
                    continue

            if len(pil_images) < 2:
                logger.error("Not enough valid images for animation")
                return None

            # メモリ上でGIFアニメーションを生成
            buffer = io.BytesIO()
            pil_images[0].save(
                buffer,
                format='GIF',
                append_images=pil_images[1:],
                duration=frame_delay,
                loop=0,
                optimize=True
            )

            # バイトデータを取得
            file_data = buffer.getvalue()

            logger.debug(
                f"Successfully created GIF animation: {len(file_data)} bytes")

            return {
                'type': 'animated_data',
                'file_data': file_data,
                'path': f"generated_animation_{len(image_paths)}_frames.gif",
                'format': 'gif'
            }

        except ImportError:
            logger.error(
                "PIL/Pillow not available for GIF animation generation")
            return None
        except Exception as e:
            logger.error(f"Error creating GIF animation: {e}")
            return None

    def _qimage_to_pil(self, qimage: QtGui.QImage) -> Optional:
        """QImageをPIL Imageに変換"""
        try:
            from PIL import Image

            # QImageをRGBA32形式に変換
            qimage = qimage.convertToFormat(
                QtGui.QImage.Format.Format_RGBA8888)

            width = qimage.width()
            height = qimage.height()

            # QImageからバイトデータを取得
            ptr = qimage.constBits()
            ptr.setsize(height * width * 4)
            data = ptr.asstring()

            # PIL Imageを作成
            pil_image = Image.frombytes('RGBA', (width, height), data)
            return pil_image

        except Exception as e:
            logger.error(f"Error converting QImage to PIL: {e}")
            return None

    def _create_webp_animation(self,
                               image_paths: List[str],
                               frame_delay: int) -> Optional[Dict[str, Any]]:
        """
        WebPアニメーションを生成（実装は後で追加可能）

        Args:
            image_paths: 画像ファイルパスのリスト
            frame_delay: フレーム間隔（ミリ秒）

        Returns:
            アニメーションデータ辞書
        """
        # 現在はWebPアニメーションはサポートしていない
        logger.warning("WebP animation generation is not implemented yet")
        return None

    def validate_image_sequence(self, image_paths: List[str]) -> bool:
        """
        画像シーケンスの妥当性を検証

        Args:
            image_paths: 画像ファイルパスのリスト

        Returns:
            妥当な場合True
        """
        if not image_paths:
            return False

        # 最低2フレーム必要
        if len(image_paths) < 2:
            logger.warning("At least 2 images required for animation")
            return False

        # 全ての画像が存在し、読み込み可能かチェック
        base_size = None
        for i, image_path in enumerate(image_paths):
            if not os.path.exists(image_path):
                logger.warning(f"Image file does not exist: {image_path}")
                return False

            # 画像が読み込み可能かチェック
            image = QtGui.QImage(image_path)
            if image.isNull():
                logger.warning(f"Cannot load image: {image_path}")
                return False

            # サイズの一貫性をチェック（最初の数フレームのみ）
            if i < 5:  # 最初の5フレームで確認
                current_size = (image.width(), image.height())
                if base_size is None:
                    base_size = current_size
                elif base_size != current_size:
                    logger.debug(f"Image size mismatch: {image_path} "
                                 f"({current_size} vs {base_size})")
                    # サイズが違っても警告のみで処理続行

        return True

    def estimate_animation_size(self, image_paths: List[str]) -> int:
        """
        生成されるアニメーションのおおよそのサイズを推定

        Args:
            image_paths: 画像ファイルパスのリスト

        Returns:
            推定サイズ（バイト）
        """
        if not image_paths:
            return 0

        try:
            # 最初の画像のサイズを基準に推定
            first_image = QtGui.QImage(image_paths[0])
            if first_image.isNull():
                return 0

            # 簡単な推定式：画像サイズ × フレーム数 × 圧縮率
            pixel_count = first_image.width() * first_image.height()
            frame_count = len(image_paths)

            # GIF圧縮を想定（実際の値は大きく異なる可能性がある）
            estimated_size = pixel_count * frame_count * 0.3

            return int(estimated_size)

        except Exception as e:
            logger.debug(f"Error estimating animation size: {e}")
            return 0


def create_animation_from_sequence(
        image_paths: List[str],
        fps: Optional[int] = None,
        output_format: str = 'gif') -> Optional[Dict[str, Any]]:
    """
    連番画像からアニメーションデータを生成する便利関数

    Args:
        image_paths: 連番画像ファイルパスのリスト（ソート済み）
        fps: フレームレート（Noneの場合は設定値を使用）
        output_format: 出力フォーマット（'gif' または 'webp'）

    Returns:
        BeeAnimatedDataItem用のアニメーションデータ辞書、失敗時はNone
    """
    generator = AnimationGenerator()

    # 画像シーケンスを検証
    if not generator.validate_image_sequence(image_paths):
        return None

    # アニメーションデータを生成
    return generator.create_animation_data(image_paths, fps, output_format)
