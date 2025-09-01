"""
Breeding & Mount Profit Calculator Service
Calculates optimal breeding routes for oxen and horses in Albion Online
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass
import math

@dataclass
class BreedingData:
    """Data for animal breeding by tier"""
    tier: int
    base_grow_hours: float
    premium_grow_hours: float
    total_food: int
    base_offspring_chance: float
    nurtured_offspring_chance: float
    
# Verified breeding data from Tools4Albion and wiki
BREEDING_DATA = {
    3: BreedingData(3, 44, 22, 10, 0.75, 1.00),
    4: BreedingData(4, 92, 46, 30, 0.79, 1.05),
    5: BreedingData(5, 140, 70, 90, 0.81, 1.05),
    6: BreedingData(6, 188, 94, 272, 0.82, 1.04),
    7: BreedingData(7, 236, 118, 805, 0.84, 1.04),
    8: BreedingData(8, 284, 142, 2367, 0.85, 1.03),
}

# Mount crafting recipes (Saddler)
MOUNT_RECIPES = {
    "T4_MOUNT_HORSE": {
        "animal": "T4_FARM_HORSE_GROWN",
        "materials": [("T4_LEATHER", 20)],
        "name": "Adept's Riding Horse"
    },
    "T5_MOUNT_HORSE": {
        "animal": "T5_FARM_HORSE_GROWN",
        "materials": [("T5_LEATHER", 25)],
        "name": "Expert's Riding Horse"
    },
    "T6_MOUNT_HORSE": {
        "animal": "T6_FARM_HORSE_GROWN",
        "materials": [("T6_LEATHER", 30)],
        "name": "Master's Riding Horse"
    },
    "T7_MOUNT_HORSE": {
        "animal": "T7_FARM_HORSE_GROWN",
        "materials": [("T7_LEATHER", 35)],
        "name": "Grandmaster's Riding Horse"
    },
    "T8_MOUNT_HORSE": {
        "animal": "T8_FARM_HORSE_GROWN",
        "materials": [("T8_LEATHER", 40)],
        "name": "Elder's Riding Horse"
    },
    "T4_MOUNT_OX": {
        "animal": "T4_FARM_OX_GROWN",
        "materials": [("T4_PLANKS", 20)],
        "name": "Adept's Transport Ox"
    },
    "T5_MOUNT_OX": {
        "animal": "T5_FARM_OX_GROWN",
        "materials": [("T5_PLANKS", 25)],
        "name": "Expert's Transport Ox"
    },
    "T6_MOUNT_OX": {
        "animal": "T6_FARM_OX_GROWN",
        "materials": [("T6_PLANKS", 30)],
        "name": "Master's Transport Ox"
    },
    "T7_MOUNT_OX": {
        "animal": "T7_FARM_OX_GROWN",
        "materials": [("T7_PLANKS", 30)],  # Verified: 30 T7 Planks
        "name": "Grandmaster's Transport Ox"
    },
    "T8_MOUNT_OX": {
        "animal": "T8_FARM_OX_GROWN",
        "materials": [("T8_PLANKS", 35)],
        "name": "Elder's Transport Ox"
    },
}

# Food items (all provide 48 nutrition)
FOOD_ITEMS = {
    "T1_CARROT": {"name": "Carrot", "nutrition": 48},
    "T2_BEAN": {"name": "Bean", "nutrition": 48},
    "T3_WHEAT": {"name": "Wheat", "nutrition": 48},
    "T4_TURNIP": {"name": "Turnip", "nutrition": 48},
    "T5_CABBAGE": {"name": "Cabbage", "nutrition": 48},
    "T6_POTATO": {"name": "Potato", "nutrition": 48},
    "T7_CORN": {"name": "Corn", "nutrition": 48},
    "T8_PUMPKIN": {"name": "Pumpkin", "nutrition": 48},
}

class BreedingCalculator:
    """Calculator for breeding and mount crafting profitability"""
    
    def __init__(self, aodp_client, pricing_calculator):
        self.aodp_client = aodp_client
        self.pricing = pricing_calculator
        
    async def calculate_breeding_profit(
        self,
        region: str,
        cities: List[str],
        max_age_hours: int,
        premium: bool,
        setup_fee: float,
        tx_tax: float,
        transport_cost: float,
        saddler_fees: Dict[str, float],
        use_focus_breeding: bool,
        use_focus_saddler: bool,
        feed_mode: str,  # "buy" or "farm"
        feed_item: str,
        island_layout: Dict[str, int],
        plan: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Calculate breeding profitability for given plan
        
        Args:
            region: Server region
            cities: List of cities to consider
            max_age_hours: Maximum data age
            premium: Premium account status
            setup_fee: Market order setup fee
            tx_tax: Transaction tax rate
            transport_cost: Transport cost per unit
            saddler_fees: Saddler usage fees by city
            use_focus_breeding: Whether to use focus for breeding
            use_focus_saddler: Whether to use focus at saddler
            feed_mode: "buy" or "farm" food
            feed_item: Food item ID
            island_layout: Pastures per island/city
            plan: List of breeding plans
            
        Returns:
            List of profitability calculations
        """
        results = []
        
        for item in plan:
            mount_type = item["type"]  # "OX" or "HORSE"
            tier = item["tier"]
            quantity = item["quantity"]
            
            # Get mount ID
            mount_id = f"T{tier}_MOUNT_{mount_type}"
            if mount_id not in MOUNT_RECIPES:
                continue
                
            recipe = MOUNT_RECIPES[mount_id]
            breeding_data = BREEDING_DATA.get(tier)
            if not breeding_data:
                continue
            
            # Calculate animal cost
            animal_cost = await self._calculate_animal_cost(
                region, cities, recipe["animal"], breeding_data,
                feed_mode, feed_item, use_focus_breeding, 
                premium, setup_fee, max_age_hours
            )
            
            # Calculate materials cost
            materials_cost, materials_city, materials_breakdown = await self._calculate_materials_cost(
                region, cities, recipe["materials"], 
                setup_fee, max_age_hours
            )
            
            # Find best saddler city (lowest fee)
            saddler_city, saddler_fee_amount = self._find_best_saddler(
                cities, saddler_fees, materials_cost
            )
            
            # Get mount selling prices
            mount_prices = await self._get_mount_prices(
                region, cities, mount_id, max_age_hours
            )
            
            # Find best selling city
            best_sell = self._find_best_sell_city(
                mount_prices, tx_tax, setup_fee
            )
            
            if not best_sell:
                continue
                
            sell_city, sell_price, revenue_net = best_sell
            
            # Calculate totals
            cost_total = (
                animal_cost["total_cost"] + 
                materials_cost + 
                saddler_fee_amount + 
                transport_cost
            )
            
            profit_abs = revenue_net - cost_total
            profit_pct = (profit_abs / cost_total * 100) if cost_total > 0 else 0
            
            # Build result
            result = {
                "mount_id": mount_id,
                "mount_name": recipe["name"],
                "quantity": quantity,
                "tier": tier,
                "type": mount_type,
                
                # Costs breakdown
                "animal_cost": animal_cost,
                "materials_cost": materials_cost,
                "materials_city": materials_city,
                "materials_breakdown": materials_breakdown,
                "saddler_city": saddler_city,
                "saddler_fee": saddler_fee_amount,
                
                # Selling
                "sell_city": sell_city,
                "sell_price": sell_price,
                "revenue_net": revenue_net,
                
                # Profit
                "cost_total": cost_total,
                "profit_absolute": profit_abs,
                "profit_percentage": profit_pct,
                
                # Route
                "route": f"Buy materials in {materials_city} → Saddler in {saddler_city} → Sell in {sell_city}",
                
                # Breeding info
                "grow_hours": breeding_data.premium_grow_hours if premium else breeding_data.base_grow_hours,
                "total_food": breeding_data.total_food,
                "offspring_chance": breeding_data.nurtured_offspring_chance if use_focus_breeding else breeding_data.base_offspring_chance,
                
                # Data freshness
                "data_age_hours": self._calculate_data_age(mount_prices),
            }
            
            # Calculate for total quantity
            result["total_profit"] = profit_abs * quantity
            result["total_profit_percentage"] = profit_pct
            
            results.append(result)
            
        # Sort by profit percentage
        results.sort(key=lambda x: x["profit_percentage"], reverse=True)
        
        return results
    
    async def _calculate_animal_cost(
        self, region: str, cities: List[str], animal_id: str,
        breeding_data: BreedingData, feed_mode: str, feed_item: str,
        use_focus: bool, premium: bool, setup_fee: float, max_age_hours: int
    ) -> Dict[str, Any]:
        """Calculate cost of obtaining the animal (breeding or buying)"""
        
        if feed_mode == "buy":
            # Get food prices
            food_prices = await self.aodp_client.get_prices(
                region, [feed_item], cities, [0]
            )
            
            # Filter by age
            fresh_prices = self.pricing.filter_by_age(food_prices, max_age_hours)
            
            # Find cheapest food
            min_food_price = float('inf')
            food_city = None
            
            for price in fresh_prices:
                if price.get("sell_price_min") and price["sell_price_min"] < min_food_price:
                    min_food_price = price["sell_price_min"]
                    food_city = price["city"]
            
            if food_city:
                # Calculate food cost with setup fee
                food_unit_cost = min_food_price * (1 + setup_fee)
                total_food_cost = food_unit_cost * breeding_data.total_food
            else:
                food_unit_cost = 0
                total_food_cost = 0
                food_city = "Unknown"
        else:
            # Farm mode - simplified calculation
            # Assumes player produces food at marginal cost
            food_unit_cost = 50  # Base estimate, should be calculated from seed prices
            total_food_cost = food_unit_cost * breeding_data.total_food
            food_city = "Own Farm"
        
        # Calculate breeding time value
        grow_hours = breeding_data.premium_grow_hours if premium else breeding_data.base_grow_hours
        
        return {
            "mode": "breed",
            "total_cost": total_food_cost,
            "food_cost_per_unit": food_unit_cost,
            "food_city": food_city,
            "total_food_needed": breeding_data.total_food,
            "grow_hours": grow_hours,
            "offspring_chance": breeding_data.nurtured_offspring_chance if use_focus else breeding_data.base_offspring_chance,
        }
    
    async def _calculate_materials_cost(
        self, region: str, cities: List[str], 
        materials: List[Tuple[str, int]], setup_fee: float, max_age_hours: int
    ) -> Tuple[float, str, List[Dict]]:
        """Calculate total materials cost and find best city"""
        
        total_cost = 0
        best_city = None
        breakdown = []
        
        for material_id, quantity in materials:
            # Get prices for this material
            prices = await self.aodp_client.get_prices(
                region, [material_id], cities, [0]
            )
            
            # Filter by age
            fresh_prices = self.pricing.filter_by_age(prices, max_age_hours)
            
            # Find cheapest
            min_price = float('inf')
            material_city = None
            
            for price in fresh_prices:
                if price.get("sell_price_min") and price["sell_price_min"] < min_price:
                    min_price = price["sell_price_min"]
                    material_city = price["city"]
            
            if material_city:
                # Add setup fee
                unit_cost = min_price * (1 + setup_fee)
                material_total = unit_cost * quantity
                total_cost += material_total
                
                breakdown.append({
                    "item_id": material_id,
                    "quantity": quantity,
                    "unit_price": min_price,
                    "total": material_total,
                    "city": material_city
                })
                
                if not best_city:
                    best_city = material_city
        
        return total_cost, best_city or "Unknown", breakdown
    
    def _find_best_saddler(
        self, cities: List[str], saddler_fees: Dict[str, float], 
        materials_cost: float
    ) -> Tuple[str, float]:
        """Find city with lowest saddler fee"""
        
        best_city = None
        min_fee = float('inf')
        
        for city in cities:
            if city in saddler_fees:
                fee_rate = saddler_fees[city]
                # Calculate fee (percentage of materials cost)
                fee_amount = materials_cost * fee_rate
                
                if fee_amount < min_fee:
                    min_fee = fee_amount
                    best_city = city
        
        # Default to first city if no fees specified
        if not best_city and cities:
            best_city = cities[0]
            min_fee = 0
        
        return best_city, min_fee
    
    async def _get_mount_prices(
        self, region: str, cities: List[str], mount_id: str, max_age_hours: int
    ) -> List[Dict]:
        """Get mount prices across cities"""
        
        prices = await self.aodp_client.get_prices(
            region, [mount_id], cities, [0]
        )
        
        return self.pricing.filter_by_age(prices, max_age_hours)
    
    def _find_best_sell_city(
        self, mount_prices: List[Dict], tx_tax: float, setup_fee: float
    ) -> Optional[Tuple[str, float, float]]:
        """Find best city to sell mount"""
        
        best_city = None
        best_price = 0
        best_revenue = 0
        
        for price in mount_prices:
            # Use buy_price_max as selling price (what buyers are willing to pay)
            if price.get("buy_price_max"):
                sell_price = price["buy_price_max"]
                # Calculate net revenue after taxes and fees
                revenue_net = sell_price * (1 - tx_tax) - sell_price * setup_fee
                
                if revenue_net > best_revenue:
                    best_revenue = revenue_net
                    best_price = sell_price
                    best_city = price["city"]
        
        if best_city:
            return best_city, best_price, best_revenue
        
        return None
    
    def _calculate_data_age(self, prices: List[Dict]) -> float:
        """Calculate average data age in hours"""
        
        if not prices:
            return 999
        
        ages = [p.get("age_hours", 999) for p in prices]
        return sum(ages) / len(ages) if ages else 999