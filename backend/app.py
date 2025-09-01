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
breeding_calculator = BreedingCalculator(aodp_client, pricing_calculator)

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