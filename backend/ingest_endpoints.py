"""
Add these imports and endpoints to your existing app.py
"""

# Add to imports:
from database import init_db, get_db, MarketTick
from services.ingest import IngestService
from sqlalchemy.orm import Session
from fastapi import Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Initialize database on startup
init_db()

# Initialize ingest service
ingest_service = IngestService()

# Schemas for ingest endpoints
class ADCRecord(BaseModel):
    type: str = "marketorder"
    region: str = "west"
    city: str
    item_id: str
    quality: int = 0
    sell_price_min: Optional[float] = None
    sell_price_max: Optional[float] = None
    buy_price_min: Optional[float] = None
    buy_price_max: Optional[float] = None
    timestamp: str

class ADCIngestRequest(BaseModel):
    records: List[ADCRecord]

class IngestStatsResponse(BaseModel):
    source_counts: Dict[str, int]
    latest_ingests: List[Dict[str, Any]]
    fresh_data_coverage: Dict[str, Any]
    stale_items: List[Dict[str, Any]]

# Add these endpoints:

@app.post("/api/ingest/adc")
async def ingest_adc_data(
    request: ADCIngestRequest,
    db: Session = Depends(get_db)
):
    """
    Ingest market data from Albion Data Client
    
    This endpoint receives data from ADC when configured with:
    -i "http://localhost:8000/api/ingest/adc"
    
    The data is stored with source='PRIVATE' and deduplicated.
    """
    try:
        # Convert Pydantic models to dicts
        records = [record.dict() for record in request.records]
        
        # Ingest data
        stats = ingest_service.ingest_adc_data(db, records)
        
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/private/stats", response_model=IngestStatsResponse)
async def get_private_stats(db: Session = Depends(get_db)):
    """
    Get statistics about private data ingestion
    
    Returns:
    - Counts by source (PRIVATE vs AODP)
    - Last ingestion timestamps
    - Fresh data coverage
    - Stale items that need updating
    """
    try:
        stats = ingest_service.get_stats(db)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Modified market prices endpoint with private data integration
@app.post("/api/market/prices/v2", response_model=PricesResponse)
async def get_market_prices_v2(
    request: PricesRequest,
    db: Session = Depends(get_db)
):
    """
    Get market prices with private data priority
    
    This version:
    1. Checks local database for PRIVATE data first
    2. Falls back to AODP API for missing data
    3. Returns merged results with source indicators
    """
    try:
        # First, try to get data from local database
        local_prices = ingest_service.get_best_snapshot(
            db=db,
            region=request.region,
            cities=request.cities,
            items=request.items,
            max_age_hours=request.max_age_hours
        )
        
        # If we have all the data locally and it's fresh, use it
        if len(local_prices) == len(request.cities) * len(request.items):
            return PricesResponse(
                region=request.region,
                prices=local_prices,
                timestamp=pricing_calculator.get_current_timestamp()
            )
        
        # Otherwise, also fetch from AODP
        aodp_prices = await aodp_client.get_prices(
            region=request.region,
            items=request.items,
            cities=request.cities,
            qualities=request.qualities
        )
        
        # Merge with preference for private data
        merged_prices = ingest_service.merge_with_aodp(
            db=db,
            aodp_data=aodp_prices,
            region=request.region,
            max_age_hours=request.max_age_hours
        )
        
        return PricesResponse(
            region=request.region,
            prices=merged_prices,
            timestamp=pricing_calculator.get_current_timestamp()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Modified opportunities endpoint to include all profits (including negative)
@app.post("/api/market/opportunities/v2")
async def calculate_opportunities_v2(
    request: OpportunitiesRequest,
    db: Session = Depends(get_db)
):
    """
    Calculate ALL market opportunities (including negative profit)
    
    Changes from v1:
    - Returns ALL routes, not just profitable ones
    - Includes source information (PRIVATE/AODP)
    - Shows data age for transparency
    """
    try:
        # Get prices with private data priority
        local_prices = ingest_service.get_best_snapshot(
            db=db,
            region=request.region,
            cities=request.cities,
            items=request.items,
            max_age_hours=request.max_age_hours
        )
        
        # If local data is incomplete, fetch from AODP
        if len(local_prices) < len(request.cities) * len(request.items):
            aodp_prices = await aodp_client.get_prices(
                region=request.region,
                items=request.items,
                cities=request.cities,
                qualities=request.qualities
            )
            
            merged_prices = ingest_service.merge_with_aodp(
                db=db,
                aodp_data=aodp_prices,
                region=request.region,
                max_age_hours=request.max_age_hours
            )
        else:
            merged_prices = local_prices
        
        # Calculate opportunities WITHOUT filtering by profit
        opportunities = []
        for price in merged_prices:
            if price.get('sell_price_min') and price.get('buy_price_max'):
                # Calculate for each city pair
                for other_price in merged_prices:
                    if (price['city'] != other_price['city'] and 
                        price['item_id'] == other_price['item_id']):
                        
                        # Buy in first city, sell in second
                        buy_price = price['sell_price_min']
                        sell_price = other_price['buy_price_max']
                        
                        # Calculate profit (can be negative)
                        buy_cost = buy_price * (1 + request.setup_fee)
                        sell_revenue = sell_price * (1 - request.setup_fee)
                        if request.premium:
                            sell_revenue *= (1 - 0.04)  # 4% tax
                        else:
                            sell_revenue *= (1 - 0.08)  # 8% tax
                        
                        profit = sell_revenue - buy_cost - request.transport_cost
                        profit_pct = (profit / buy_cost * 100) if buy_cost > 0 else 0
                        
                        opportunities.append({
                            'item_id': price['item_id'],
                            'item_name': DEFAULT_ITEMS.get(price['item_id'], price['item_id']),
                            'quality': price.get('quality', 0),
                            'buy_city': price['city'],
                            'sell_city': other_price['city'],
                            'buy_price': buy_price,
                            'sell_price': sell_price,
                            'buy_timestamp': price.get('sell_price_min_date', ''),
                            'sell_timestamp': other_price.get('buy_price_max_date', ''),
                            'profit_absolute': round(profit, 2),
                            'profit_percentage': round(profit_pct, 2),
                            'source_buy': price.get('source', 'AODP'),
                            'source_sell': other_price.get('source', 'AODP'),
                            'age_buy_hours': price.get('age_hours', 999),
                            'age_sell_hours': other_price.get('age_hours', 999),
                            'is_caerleon_route': 'Caerleon' in [price['city'], other_price['city']],
                            'is_profitable': profit > 0  # Flag for frontend filtering
                        })
        
        # Sort by profit percentage DESC, then absolute profit DESC
        sorted_opportunities = sorted(
            opportunities,
            key=lambda x: (-x['profit_percentage'], -x['profit_absolute'])
        )
        
        return {
            'region': request.region,
            'opportunities': sorted_opportunities,
            'timestamp': pricing_calculator.get_current_timestamp(),
            'parameters': request.dict(),
            'stats': {
                'total_routes': len(sorted_opportunities),
                'profitable_routes': sum(1 for o in sorted_opportunities if o['is_profitable']),
                'negative_routes': sum(1 for o in sorted_opportunities if not o['is_profitable']),
                'private_data_used': sum(1 for o in sorted_opportunities if o['source_buy'] == 'PRIVATE' or o['source_sell'] == 'PRIVATE')
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))