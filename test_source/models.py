"""ユーザー登録フォームのデータモデル"""

from dataclasses import dataclass
from datetime import date
import re


@dataclass
class UserRegistration:
    """ユーザー登録データ"""
    shimei: str          # 指名
    shimei_kana: str     # 指名（カタカナ）
    birthdate: date      # 生年月日
    address: str         # 住所


def validate_shimei(value: str) -> bool:
    """指名のバリデーション: 最大50文字、空白のみは不可"""
    if not value or not value.strip():
        return False
    return len(value) <= 50


def validate_shimei_kana(value: str) -> bool:
    """指名（カタカナ）のバリデーション: 全角カタカナのみ、最大50文字"""
    if not value:
        return False
    pattern = r'^[ァ-ヶー　\s]+$'
    return bool(re.match(pattern, value)) and len(value) <= 50


def validate_birthdate(value: date) -> bool:
    """生年月日のバリデーション: 過去の日付のみ許可"""
    return value < date.today()


def validate_address(value: str) -> bool:
    """住所のバリデーション: 最大200文字"""
    return bool(value) and len(value) <= 200
