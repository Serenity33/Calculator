from dataclasses import dataclass
from typing import Optional


@dataclass
class Business:
    id: int
    name: str
    created: str


@dataclass
class Category:
    id: int
    business_id: int
    name: str
    type: str  # 'income' | 'expense'


@dataclass
class Transaction:
    id: int
    business_id: int
    category_id: Optional[int]
    type: str  # 'income' | 'expense'
    amount: float
    description: Optional[str]
    date: str
    created_at: str
    category_name: Optional[str] = None
