"""
Pydantic schemas for API requests and responses
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator

# Request schemas
class PricesRequest(BaseModel):
    region: str = Field(default="west", description="Server region")
    items: List[str] = Field(..., description="List of item IDs")
    cities: List[str] = Field(..., description="List of city names")
    qualities: List[int] = Field(default=[0], description="Item qualities (0-5)")
    max_age_hours: int = Field(default=12, description="Maximum data age in hours")
    
    @validator('region')
    def validate_region(cls, v):
        if v not in ['west', 'europe', 'east']:
            raise ValueError('Region must be west, europe, or east')
        return v
    
    @validator('qualities')
    def validate_qualities(cls, v):
        for q in v:
            if q < 0 or q > 5:
                raise ValueError('Quality must be between 0 and 5')
        return v

class OpportunitiesRequest(BaseModel):
    region: str = Field(default="west")
    items: List[str] = Field(...)
    cities: List[str] = Field(...)
    qualities: List[int] = Field(default=[0])
    premium: bool = Field(default=False, description="Premium account status")
    setup_fee: float = Field(default=0.025, description="Order setup fee percentage")
    max_age_hours: int = Field(default=12)
    transport_cost: float = Field(default=0, description="Transport cost per item")
    prefer_caerleon: bool = Field(default=False, description="Prioritize Caerleon routes")
    
    @validator('setup_fee')
    def validate_setup_fee(cls, v):
        if v < 0 or v > 0.1:
            raise ValueError('Setup fee must be between 0 and 10%')
        return v

class HistoryRequest(BaseModel):
    region: str = Field(default="west")
    item: str = Field(..., description="Item ID")
    city: str = Field(..., description="City name")
    timescale: int = Field(default=24, description="Time scale (1=hourly, 24=daily)")

# Response schemas
class PriceInfo(BaseModel):
    item_id: str
    city: str
    quality: int
    sell_price_min: Optional[float]
    sell_price_max: Optional[float]
    buy_price_min: Optional[float]
    buy_price_max: Optional[float]
    sell_price_min_date: Optional[str]
    sell_price_max_date: Optional[str]
    buy_price_min_date: Optional[str]
    buy_price_max_date: Optional[str]
    age_hours: Optional[float]

class PricesResponse(BaseModel):
    region: str
    prices: List[PriceInfo]
    timestamp: str

class OpportunityInfo(BaseModel):
    item_id: str
    item_name: Optional[str]
    quality: int
    buy_city: str
    sell_city: str
    buy_price: float
    sell_price: float
    buy_timestamp: str
    sell_timestamp: str
    fees_percentage: float
    setup_fee_percentage: float
    transport_cost: float
    profit_absolute: float
    profit_percentage: float
    is_caerleon_route: bool
    data_age_hours: float

class OpportunitiesResponse(BaseModel):
    region: str
    opportunities: List[Dict[str, Any]]
    timestamp: str
    parameters: Dict[str, Any]

class HistoryDataPoint(BaseModel):
    timestamp: str
    item_count: int
    avg_price: float
    min_price: float
    max_price: float

class HistoryResponse(BaseModel):
    region: str
    item: str
    city: str
    timescale: int
    data: List[Dict[str, Any]]

class MetaResponse(BaseModel):
    cities: List[str]
    items: Dict[str, str]
    regions: List[str]