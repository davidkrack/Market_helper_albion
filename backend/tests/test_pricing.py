"""
Tests for pricing calculator
Run with: pytest tests/test_pricing.py -v
"""

import pytest
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.pricing import PricingCalculator

class TestPricingCalculator:
    
    @pytest.fixture
    def calculator(self):
        return PricingCalculator()
    
    def test_transaction_tax_premium(self, calculator):
        """Test transaction tax calculation for premium account"""
        tax = calculator.calculate_transaction_tax(1000, is_premium=True)
        assert tax == 40  # 4% of 1000
    
    def test_transaction_tax_non_premium(self, calculator):
        """Test transaction tax calculation for non-premium account"""
        tax = calculator.calculate_transaction_tax(1000, is_premium=False)
        assert tax == 80  # 8% of 1000
    
    def test_setup_fee_calculation(self, calculator):
        """Test setup fee calculation"""
        fee = calculator.calculate_setup_fee(1000, setup_fee_rate=0.025)
        assert fee == 25  # 2.5% of 1000
    
    def test_profit_calculation_premium(self, calculator):
        """Test profit calculation for premium account"""
        buy_price = 1000
        sell_price = 1500
        
        absolute_profit, profit_percentage = calculator.calculate_profit(
            buy_price=buy_price,
            sell_price=sell_price,
            is_premium=True,
            setup_fee_rate=0.025,
            transport_cost=0
        )
        
        # Expected calculation:
        # Buy cost: 1000 + (1000 * 0.025) = 1025
        # Sell revenue: 1500 - (1500 * 0.04) - (1500 * 0.025) = 1500 - 60 - 37.5 = 1402.5
        # Profit: 1402.5 - 1025 = 377.5
        # Profit %: (377.5 / 1025) * 100 = 36.83%
        
        assert abs(absolute_profit - 377.5) < 0.01
        assert abs(profit_percentage - 36.83) < 0.01
    
    def test_profit_calculation_non_premium(self, calculator):
        """Test profit calculation for non-premium account"""
        buy_price = 1000
        sell_price = 1500
        
        absolute_profit, profit_percentage = calculator.calculate_profit(
            buy_price=buy_price,
            sell_price=sell_price,
            is_premium=False,
            setup_fee_rate=0.025,
            transport_cost=0
        )
        
        # Expected calculation:
        # Buy cost: 1000 + (1000 * 0.025) = 1025
        # Sell revenue: 1500 - (1500 * 0.08) - (1500 * 0.025) = 1500 - 120 - 37.5 = 1342.5
        # Profit: 1342.5 - 1025 = 317.5
        # Profit %: (317.5 / 1025) * 100 = 30.98%
        
        assert abs(absolute_profit - 317.5) < 0.01
        assert abs(profit_percentage - 30.98) < 0.01
    
    def test_profit_with_transport_cost(self, calculator):
        """Test profit calculation with transport cost"""
        buy_price = 1000
        sell_price = 1500
        transport_cost = 50
        
        absolute_profit, profit_percentage = calculator.calculate_profit(
            buy_price=buy_price,
            sell_price=sell_price,
            is_premium=True,
            setup_fee_rate=0.025,
            transport_cost=transport_cost
        )
        
        # Profit should be reduced by transport cost
        assert abs(absolute_profit - 327.5) < 0.01
    
    def test_age_calculation(self, calculator):
        """Test age calculation from timestamp"""
        # Create a timestamp 5 hours ago
        old_time = datetime.utcnow() - timedelta(hours=5)
        timestamp_str = old_time.isoformat() + "Z"
        
        age_hours = calculator.calculate_age_hours(timestamp_str)
        assert abs(age_hours - 5) < 0.1  # Allow small time difference
    
    def test_filter_by_age(self, calculator):
        """Test filtering prices by age"""
        now = datetime.utcnow()
        old_time = now - timedelta(hours=20)
        recent_time = now - timedelta(hours=2)
        
        prices = [
            {
                "item_id": "T4_BAG",
                "city": "Martlock",
                "sell_price_min": 1000,
                "sell_price_min_date": old_time.isoformat() + "Z",
                "buy_price_max_date": old_time.isoformat() + "Z"
            },
            {
                "item_id": "T5_BAG",
                "city": "Martlock",
                "sell_price_min": 2000,
                "sell_price_min_date": recent_time.isoformat() + "Z",
                "buy_price_max_date": recent_time.isoformat() + "Z"
            }
        ]
        
        filtered = calculator.filter_by_age(prices, max_age_hours=12)
        
        # Should only include the recent price
        assert len(filtered) == 1
        assert filtered[0]["item_id"] == "T5_BAG"
    
    def test_calculate_opportunities(self, calculator):
        """Test opportunity calculation from price data"""
        prices = [
            {
                "item_id": "T4_BAG",
                "city": "Martlock",
                "quality": 0,
                "sell_price_min": 1000,  # Buy price in Martlock
                "buy_price_max": 900,
                "sell_price_min_date": datetime.utcnow().isoformat() + "Z",
                "buy_price_max_date": datetime.utcnow().isoformat() + "Z",
                "age_hours": 1
            },
            {
                "item_id": "T4_BAG",
                "city": "Caerleon",
                "quality": 0,
                "sell_price_min": 1200,
                "buy_price_max": 1400,  # Sell price in Caerleon
                "sell_price_min_date": datetime.utcnow().isoformat() + "Z",
                "buy_price_max_date": datetime.utcnow().isoformat() + "Z",
                "age_hours": 1
            }
        ]
        
        opportunities = calculator.calculate_opportunities(
            prices=prices,
            premium=True,
            setup_fee=0.025,
            transport_cost=0,
            prefer_caerleon=False
        )
        
        # Should find one profitable route: Martlock -> Caerleon
        assert len(opportunities) == 1
        opp = opportunities[0]
        assert opp["buy_city"] == "Martlock"
        assert opp["sell_city"] == "Caerleon"
        assert opp["profit_absolute"] > 0
        assert opp["is_caerleon_route"] == True
    
    def test_no_opportunities_when_not_profitable(self, calculator):
        """Test that unprofitable routes are not included"""
        prices = [
            {
                "item_id": "T4_BAG",
                "city": "Martlock",
                "quality": 0,
                "sell_price_min": 1000,
                "buy_price_max": 900,
                "sell_price_min_date": datetime.utcnow().isoformat() + "Z",
                "buy_price_max_date": datetime.utcnow().isoformat() + "Z",
                "age_hours": 1
            },
            {
                "item_id": "T4_BAG",
                "city": "Lymhurst",
                "quality": 0,
                "sell_price_min": 1050,  # Not enough margin
                "buy_price_max": 1000,
                "sell_price_min_date": datetime.utcnow().isoformat() + "Z",
                "buy_price_max_date": datetime.utcnow().isoformat() + "Z",
                "age_hours": 1
            }
        ]
        
        opportunities = calculator.calculate_opportunities(
            prices=prices,
            premium=False,  # Higher tax makes it unprofitable
            setup_fee=0.025,
            transport_cost=0,
            prefer_caerleon=False
        )
        
        # Should find no profitable opportunities
        assert len(opportunities) == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])