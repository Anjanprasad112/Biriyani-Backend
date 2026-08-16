from datetime import date

from pydantic import BaseModel


class SalesPoint(BaseModel):

    date: date

    label: str

    revenue: int

    orders: int


class TopItem(BaseModel):

    name: str

    quantity: int

    revenue: int


class DashboardSummary(BaseModel):

    period_start: date

    period_end: date

    total_revenue: int

    total_orders: int

    active_orders: int

    completed_orders: int

    cancelled_orders: int

    rejected_orders: int

    average_order_value: int

    average_preparation_minutes: int

    sales: list[SalesPoint]

    top_items: list[TopItem]