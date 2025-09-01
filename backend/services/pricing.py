"""
Pricing calculator for market opportunities
Handles all profit calculations and filtering logic
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

class PricingCalculator:
    """Calculate profit opportunities and apply filters"""
    
    def __init__(self):
        # Item name mapping (can be expanded)
        self.item_names = {
            "T4_BAG": "Adept's Bag",
            "T5_BAG": "Expert's Bag",
            "T6_BAG": "Master's Bag",
            "T7_BAG": "Grandmaster's Bag",
            "T8_BAG": "Elder's Bag",
            "T4_CAPE": "Adept's Cape",
            "T5_CAPE": "Expert's Cape",
            "T6_CAPE": "Master's Cape",
            "T4_ORE": "Iron Ore",
            "T5_ORE": "Titanium Ore",
            "T6_ORE": "Runite Ore",
            "T4_PLANKS": "Chestnut Planks",
            "T5_PLANKS": "Bloodoak Planks",
            "T6_PLANKS": "Ashenbark Planks",
            "T4_LEATHER": "Worked Leather",
            "T5_LEATHER": "Cured Leather",
            "T6_LEATHER": "Hardened Leather",
        }
    
    def get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string"""
        return datetime.utcnow().isoformat() + "Z"
    
    def calculate_age_hours(self, timestamp_str: Optional[str]) -> float:
        """Calculate age in hours from timestamp string"""
        if not timestamp_str:
            return 999999  # Very old if no timestamp
        
        try:
            # Parse different timestamp formats
            timestamp_str = timestamp_str.replace("Z", "+00:00")
            if "T" in timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace("+00:00", ""))
            else:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            
            age = datetime.utcnow() - timestamp
            return age.total_seconds() / 3600
        except Exception:
            return 999999
    
    def filter_by_age(self, prices: List[Dict[str, Any]], max_age_hours: int) -> List[Dict[str, Any]]:
        """Filter prices by maximum age"""
        filtered = []
        for price in prices:
            # Calculate age for buy and sell prices
            sell_age = self.calculate_age_hours(price.get("sell_price_min_date"))
            buy_age = self.calculate_age_hours(price.get("buy_price_max_date"))
            
            # Use the most recent timestamp for age calculation
            min_age = min(sell_age, buy_age)
            
            # Add age to price data
            price["age_hours"] = min_age
            
            # Only include if data is fresh enough
            if min_age <= max_age_hours:
                filtered.append(price)
        
        return filtered
    
    def calculate_transaction_tax(self, amount: float, is_premium: bool) -> float:
        """
        Calculate transaction tax
        Premium: 4%, Non-premium: 8%
        """
        tax_rate = 0.04 if is_premium else 0.08
        return amount * tax_rate
    
    def calculate_setup_fee(self, amount: float, setup_fee_rate: float) -> float:
        """Calculate order setup fee"""
        return amount * setup_fee_rate
    
    def calculate_profit(
        self,
        buy_price: float,
        sell_price: float,
        is_premium: bool,
        setup_fee_rate: float = 0.025,
        transport_cost: float = 0
    ) -> Tuple[float, float]:
        """
        Calculate profit for a trade
        
        Returns:
            Tuple of (absolute_profit, profit_percentage)
        """
        # Calculate costs
        buy_setup_fee = self.calculate_setup_fee(buy_price, setup_fee_rate)
        effective_buy_cost = buy_price + buy_setup_fee
        
        # Calculate revenue
        sell_tax = self.calculate_transaction_tax(sell_price, is_premium)
        sell_setup_fee = self.calculate_setup_fee(sell_price, setup_fee_rate)
        net_revenue = sell_price - sell_tax - sell_setup_fee
        
        # Calculate profit
        absolute_profit = net_revenue - effective_buy_cost - transport_cost
        
        # Calculate profit percentage
        if effective_buy_cost > 0:
            profit_percentage = (absolute_profit / effective_buy_cost) * 100
        else:
            profit_percentage = 0
        
        return absolute_profit, profit_percentage
    
    def calculate_opportunities(
        self,
        prices: List[Dict[str, Any]],
        premium: bool,
        setup_fee: float,
        transport_cost: float = 0,
        prefer_caerleon: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Calculate all profitable opportunities from price data
        """
        opportunities = []
        
        # Group prices by item and quality
        price_map = defaultdict(lambda: defaultdict(dict))
        for price in prices:
            item_id = price.get("item_id", "")
            city = price.get("city", "")
            quality = price.get("quality", 0)
            price_map[item_id][quality][city] = price
        
        # Calculate opportunities for each item and quality
        for item_id, quality_data in price_map.items():
            for quality, city_prices in quality_data.items():
                cities = list(city_prices.keys())
                
                # Check all city pairs
                for buy_city in cities:
                    for sell_city in cities:
                        if buy_city == sell_city:
                            continue
                        
                        buy_data = city_prices[buy_city]
                        sell_data = city_prices[sell_city]
                        
                        # Get prices (use sell_price_min for buying, buy_price_max for selling)
                        buy_price = buy_data.get("sell_price_min")
                        sell_price = sell_data.get("buy_price_max")
                        
                        # Skip if prices are not available
                        if not buy_price or not sell_price or buy_price <= 0 or sell_price <= 0:
                            continue
                        
                        # Skip if sell price is not higher than buy price
                        if sell_price <= buy_price:
                            continue
                        
                        # Calculate profit
                        absolute_profit, profit_percentage = self.calculate_profit(
                            buy_price=buy_price,
                            sell_price=sell_price,
                            is_premium=premium,
                            setup_fee_rate=setup_fee,
                            transport_cost=transport_cost
                        )
                        
                        # Only include profitable opportunities
                        if absolute_profit > 0:
                            is_caerleon_route = "Caerleon" in buy_city or "Caerleon" in sell_city
                            
                            opportunity = {
                                "item_id": item_id,
                                "item_name": self.item_names.get(item_id, item_id),
                                "quality": quality,
                                "buy_city": buy_city,
                                "sell_city": sell_city,
                                "buy_price": buy_price,
                                "sell_price": sell_price,
                                "buy_timestamp": buy_data.get("sell_price_min_date", ""),
                                "sell_timestamp": sell_data.get("buy_price_max_date", ""),
                                "fees_percentage": (0.04 if premium else 0.08) + setup_fee,
                                "setup_fee_percentage": setup_fee,
                                "transport_cost": transport_cost,
                                "profit_absolute": round(absolute_profit, 2),
                                "profit_percentage": round(profit_percentage, 2),
                                "is_caerleon_route": is_caerleon_route,
                                "data_age_hours": max(
                                    buy_data.get("age_hours", 0),
                                    sell_data.get("age_hours", 0)
                                )
                            }
                            
                            # Apply Caerleon preference
                            if prefer_caerleon and is_caerleon_route:
                                opportunity["profit_percentage"] *= 1.1  # 10% boost for sorting
                            
                            opportunities.append(opportunity)
        
        return opportunities