"""
Albion Market Helper - Backend API
FastAPI application for analyzing market opportunities in Albion Online
"""
from items_database import ALBION_ITEMS, get_all_items_flat
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv
from database import init_db, get_db, MarketTick
from services.ingest import IngestService
from sqlalchemy.orm import Session
from fastapi import Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from models import Region, Quality
from schemas import (
    PricesRequest, PricesResponse,
    OpportunitiesRequest, OpportunitiesResponse,
    HistoryRequest, HistoryResponse,
    MetaResponse
)
from services.aodp_client import AODPClient
from services.pricing import PricingCalculator
from services.cache import CacheManager
from schemas_breeding import BreedingRequest, BreedingResponse
from services.breeding import BreedingCalculator

load_dotenv()

# Configuration
AODP_BASE = os.getenv("AODP_BASE", "https://west.albion-online-data.com")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "600"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "120"))

# Initialize services
cache_manager = CacheManager(ttl_seconds=CACHE_TTL_SECONDS)
aodp_client = AODPClient(
    base_url=AODP_BASE,
    cache_manager=cache_manager,
    rate_limit_per_min=RATE_LIMIT_PER_MIN
)
pricing_calculator = PricingCalculator()
init_db()
ingest_service = IngestService()
breeding_calculator = BreedingCalculator(aodp_client, pricing_calculator)

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



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await aodp_client.initialize()
    yield
    # Shutdown
    await aodp_client.close()

app = FastAPI(
    title="Albion Market Helper API",
    version="1.0.0",
    description="API for analyzing market opportunities in Albion Online",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite cualquier origen (incluido file://)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Supported cities and items
SUPPORTED_CITIES = [
    "Martlock", "Lymhurst", "Bridgewatch", 
    "Thetford", "Fort Sterling", "Caerleon"
]

# Popular items 
DEFAULT_ITEMS = get_all_items_flat()

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

@app.get("/")
async def root():
    return {
        "name": "Albion Market Helper API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/api/meta/cities", response_model=MetaResponse)
async def get_cities():
    """Get list of supported cities and items organized by categories"""
    return MetaResponse(
        cities=SUPPORTED_CITIES,
        items=DEFAULT_ITEMS,  # Esto ahora tiene TODOS los items
        items_by_category=ALBION_ITEMS,  # Nuevo: items organizados por categorías
        regions=["west", "europe", "east"]
    )

@app.post("/api/market/prices", response_model=PricesResponse)
async def get_market_prices(request: PricesRequest):
    """Get current market prices for specified items and cities"""
    try:
        # Get prices from AODP
        prices_data = await aodp_client.get_prices(
            region=request.region,
            items=request.items,
            cities=request.cities,
            qualities=request.qualities
        )
        
        # Filter by max age
        filtered_prices = pricing_calculator.filter_by_age(
            prices_data, 
            max_age_hours=request.max_age_hours
        )
        
        return PricesResponse(
            region=request.region,
            prices=filtered_prices,
            timestamp=pricing_calculator.get_current_timestamp()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/market/opportunities", response_model=OpportunitiesResponse)
async def calculate_opportunities(request: OpportunitiesRequest):
    """Calculate profit opportunities between cities"""
    try:
        # Get current prices
        prices_data = await aodp_client.get_prices(
            region=request.region,
            items=request.items,
            cities=request.cities,
            qualities=request.qualities
        )
        
        # Filter by age
        filtered_prices = pricing_calculator.filter_by_age(
            prices_data,
            max_age_hours=request.max_age_hours
        )
        
        # Calculate opportunities
        opportunities = pricing_calculator.calculate_opportunities(
            prices=filtered_prices,
            premium=request.premium,
            setup_fee=request.setup_fee,
            transport_cost=request.transport_cost,
            prefer_caerleon=request.prefer_caerleon
        )
        
        # Sort by profit percentage (descending) then by absolute profit
        sorted_opportunities = sorted(
            opportunities,
            key=lambda x: (-x["profit_percentage"], -x["profit_absolute"])
        )
        
        return OpportunitiesResponse(
            region=request.region,
            opportunities=sorted_opportunities[:100],  # Limit to top 100
            timestamp=pricing_calculator.get_current_timestamp(),
            parameters={
                "premium": request.premium,
                "setup_fee": request.setup_fee,
                "transport_cost": request.transport_cost,
                "max_age_hours": request.max_age_hours
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/history", response_model=HistoryResponse)
async def get_market_history(
    region: str,
    item: str,
    city: str,
    timescale: int = 24
):
    """Get historical price data for an item in a specific city"""
    try:
        history_data = await aodp_client.get_history(
            region=region,
            item=item,
            city=city,
            timescale=timescale
        )
        
        return HistoryResponse(
            region=region,
            item=item,
            city=city,
            timescale=timescale,
            data=history_data
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cache/clear")
async def clear_cache():
    """Clear the cache (admin endpoint)"""
    cache_manager.clear()
    return {"message": "Cache cleared successfully"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "cache_size": cache_manager.size(),
        "rate_limit": f"{RATE_LIMIT_PER_MIN} requests/min"
    }

@app.post("/api/breeding/calc", response_model=BreedingResponse)
async def calculate_breeding(request: BreedingRequest):
    """Calculate breeding and mount crafting profitability"""
    try:
        # Agregar este print para debug
        print(f"Request received: {request.dict()}")
        
        # Calculate breeding profitability
        results = await breeding_calculator.calculate_breeding_profit(
            region=request.region,
            cities=request.cities,
            max_age_hours=request.max_age_hours,
            premium=request.premium,
            setup_fee=request.setup_fee,
            tx_tax=request.tx_tax,
            transport_cost=request.transport_cost,
            saddler_fees=request.saddler_fees,
            use_focus_breeding=request.use_focus_breeding,
            use_focus_saddler=request.use_focus_saddler,
            feed_mode=request.feed_mode,
            feed_item=request.feed_item,
            island_layout=request.island_layout,
            plan=[item.dict() for item in request.plan]  # Convertir a dict
        )
        
        return BreedingResponse(
            region=request.region,
            results=results,
            timestamp=pricing_calculator.get_current_timestamp(),
            parameters={
                "premium": request.premium,
                "setup_fee": request.setup_fee,
                "tx_tax": request.tx_tax,
                "max_age_hours": request.max_age_hours,
                "feed_mode": request.feed_mode,
                "use_focus_breeding": request.use_focus_breeding,
                "use_focus_saddler": request.use_focus_saddler,
            }
        )
    except Exception as e:
        print(f"Error in breeding calculation: {str(e)}")  # Print del error
        import traceback
        traceback.print_exc()  # Stack trace completo
        raise HTTPException(status_code=500, detail=str(e))
        
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)