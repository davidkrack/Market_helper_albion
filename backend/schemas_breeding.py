"""
Pydantic schemas for breeding calculator API
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, validator

class BreedingPlanItem(BaseModel):
    type: str = Field(..., description="OX or HORSE")
    tier: int = Field(..., ge=3, le=8, description="Tier 3-8")
    quantity: int = Field(..., ge=1, description="Number to breed/craft")
    
    @validator('type')
    def validate_type(cls, v):
        if v.upper() not in ['OX', 'HORSE']:
            raise ValueError('Type must be OX or HORSE')
        return v.upper()

class BreedingRequest(BaseModel):
    region: str = Field(default="west")
    cities: List[str] = Field(..., min_items=1)
    max_age_hours: int = Field(default=12, ge=1, le=48)
    premium: bool = Field(default=True)
    setup_fee: float = Field(default=0.025, ge=0, le=0.1)
    tx_tax: float = Field(default=0.04, ge=0, le=0.2)
    transport_cost: float = Field(default=0, ge=0)
    saddler_fees: Dict[str, float] = Field(default_factory=dict)
    use_focus_breeding: bool = Field(default=False)
    use_focus_saddler: bool = Field(default=False)
    feed_mode: str = Field(default="buy")
    feed_item: str = Field(default="T6_POTATO")
    island_layout: Dict[str, int] = Field(default_factory=dict)
    plan: List[BreedingPlanItem] = Field(..., min_items=1)
    
    @validator('region')
    def validate_region(cls, v):
        if v not in ['west', 'europe', 'east']:
            raise ValueError('Region must be west, europe, or east')
        return v
    
    @validator('feed_mode')
    def validate_feed_mode(cls, v):
        if v not in ['buy', 'farm']:
            raise ValueError('Feed mode must be buy or farm')
        return v
    
    @validator('saddler_fees')
    def validate_saddler_fees(cls, v):
        for city, fee in v.items():
            if fee < 0 or fee > 1:
                raise ValueError(f'Saddler fee for {city} must be between 0 and 1')
        return v

class AnimalCostInfo(BaseModel):
    mode: str
    total_cost: float
    food_cost_per_unit: float
    food_city: str
    total_food_needed: int
    grow_hours: float
    offspring_chance: float

class MaterialBreakdown(BaseModel):
    item_id: str
    quantity: int
    unit_price: float
    total: float
    city: str

class BreedingResult(BaseModel):
    mount_id: str
    mount_name: str
    quantity: int
    tier: int
    type: str
    
    # Costs
    animal_cost: Dict[str, Any]
    materials_cost: float
    materials_city: str
    materials_breakdown: List[Dict[str, Any]]
    saddler_city: str
    saddler_fee: float
    
    # Revenue
    sell_city: str
    sell_price: float
    revenue_net: float
    
    # Profit
    cost_total: float
    profit_absolute: float
    profit_percentage: float
    total_profit: float
    total_profit_percentage: float
    
    # Route
    route: str
    
    # Breeding info
    grow_hours: float
    total_food: int
    offspring_chance: float
    
    # Data freshness
    data_age_hours: float

class BreedingResponse(BaseModel):
    region: str
    results: List[BreedingResult]
    timestamp: str
    parameters: Dict[str, Any]