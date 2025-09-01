"""
Private data ingestion service for Albion Data Client
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from database import MarketTick, IngestStats
import json

class IngestService:
    """Service for handling private market data ingestion"""
    
    def __init__(self):
        self.source_priority = ['PRIVATE', 'AODP']  # Priority order
    
    def ingest_adc_data(self, db: Session, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Ingest data from Albion Data Client
        
        Args:
            db: Database session
            records: List of market records from ADC
            
        Returns:
            Ingestion statistics
        """
        stats = {
            'received': len(records),
            'inserted': 0,
            'updated': 0,
            'duplicates': 0,
            'errors': []
        }
        
        for record in records:
            try:
                # Parse record
                market_tick = self._parse_adc_record(record)
                
                # Check for existing record
                existing = db.query(MarketTick).filter(
                    and_(
                        MarketTick.city == market_tick.city,
                        MarketTick.item_id == market_tick.item_id,
                        MarketTick.quality == market_tick.quality,
                        MarketTick.timestamp == market_tick.timestamp,
                        MarketTick.source == market_tick.source
                    )
                ).first()
                
                if existing:
                    # Update if prices changed
                    if self._prices_changed(existing, market_tick):
                        existing.sell_price_min = market_tick.sell_price_min
                        existing.sell_price_max = market_tick.sell_price_max
                        existing.buy_price_min = market_tick.buy_price_min
                        existing.buy_price_max = market_tick.buy_price_max
                        existing.ingested_at = datetime.utcnow()
                        stats['updated'] += 1
                    else:
                        stats['duplicates'] += 1
                else:
                    # Insert new record
                    db.add(market_tick)
                    stats['inserted'] += 1
                    
            except Exception as e:
                stats['errors'].append({
                    'record': record,
                    'error': str(e)
                })
        
        # Update stats
        self._update_ingest_stats(db, 'PRIVATE', stats['inserted'] + stats['updated'])
        
        # Commit changes
        db.commit()
        
        return stats
    
    def _parse_adc_record(self, record: Dict[str, Any]) -> MarketTick:
        """Parse ADC record into MarketTick model"""
        
        # Handle different timestamp formats
        timestamp_str = record.get('timestamp')
        if isinstance(timestamp_str, str):
            if 'T' in timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        else:
            timestamp = datetime.utcnow()
        
        return MarketTick(
            source='PRIVATE',
            region=record.get('region', 'west'),
            city=record.get('city'),
            item_id=record.get('item_id'),
            quality=record.get('quality', 0),
            sell_price_min=record.get('sell_price_min'),
            sell_price_max=record.get('sell_price_max'),
            buy_price_min=record.get('buy_price_min'),
            buy_price_max=record.get('buy_price_max'),
            timestamp=timestamp,
            ingested_at=datetime.utcnow()
        )
    
    def _prices_changed(self, existing: MarketTick, new: MarketTick) -> bool:
        """Check if prices have changed"""
        return (
            existing.sell_price_min != new.sell_price_min or
            existing.sell_price_max != new.sell_price_max or
            existing.buy_price_min != new.buy_price_min or
            existing.buy_price_max != new.buy_price_max
        )
    
    def _update_ingest_stats(self, db: Session, source: str, count: int):
        """Update ingestion statistics"""
        stats = db.query(IngestStats).filter(IngestStats.source == source).first()
        
        if not stats:
            stats = IngestStats(source=source)
            db.add(stats)
        
        stats.last_ingest_at = datetime.utcnow()
        stats.total_records += count
        stats.daily_records += count  # TODO: Reset daily counter at midnight
        stats.updated_at = datetime.utcnow()
    
    def get_best_snapshot(
        self, 
        db: Session,
        region: str,
        cities: List[str],
        items: List[str],
        max_age_hours: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Get best available market snapshot, preferring PRIVATE over AODP
        
        Args:
            db: Database session
            region: Server region
            cities: List of cities
            items: List of item IDs
            max_age_hours: Maximum age of data
            
        Returns:
            List of best available price records
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        results = []
        
        for city in cities:
            for item_id in items:
                # Try to get PRIVATE data first
                private_tick = db.query(MarketTick).filter(
                    and_(
                        MarketTick.source == 'PRIVATE',
                        MarketTick.region == region,
                        MarketTick.city == city,
                        MarketTick.item_id == item_id,
                        MarketTick.timestamp >= cutoff_time
                    )
                ).order_by(MarketTick.timestamp.desc()).first()
                
                if private_tick:
                    results.append(self._tick_to_dict(private_tick))
                else:
                    # Fallback to AODP data
                    aodp_tick = db.query(MarketTick).filter(
                        and_(
                            MarketTick.source == 'AODP',
                            MarketTick.region == region,
                            MarketTick.city == city,
                            MarketTick.item_id == item_id,
                            MarketTick.timestamp >= cutoff_time
                        )
                    ).order_by(MarketTick.timestamp.desc()).first()
                    
                    if aodp_tick:
                        results.append(self._tick_to_dict(aodp_tick))
        
        return results
    
    def _tick_to_dict(self, tick: MarketTick) -> Dict[str, Any]:
        """Convert MarketTick to dictionary with age calculation"""
        age_hours = (datetime.utcnow() - tick.timestamp).total_seconds() / 3600
        
        return {
            'source': tick.source,
            'region': tick.region,
            'city': tick.city,
            'item_id': tick.item_id,
            'quality': tick.quality,
            'sell_price_min': tick.sell_price_min,
            'sell_price_max': tick.sell_price_max,
            'buy_price_min': tick.buy_price_min,
            'buy_price_max': tick.buy_price_max,
            'sell_price_min_date': tick.timestamp.isoformat() + 'Z',
            'sell_price_max_date': tick.timestamp.isoformat() + 'Z',
            'buy_price_min_date': tick.timestamp.isoformat() + 'Z',
            'buy_price_max_date': tick.timestamp.isoformat() + 'Z',
            'age_hours': round(age_hours, 2),
            'timestamp': tick.timestamp.isoformat() + 'Z'
        }
    
    def get_stats(self, db: Session) -> Dict[str, Any]:
        """Get ingestion statistics"""
        
        # Get counts by source
        source_counts = db.query(
            MarketTick.source,
            func.count(MarketTick.id).label('count')
        ).group_by(MarketTick.source).all()
        
        # Get latest ingestion times
        latest_ingests = db.query(IngestStats).all()
        
        # Get items/cities without fresh data
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        # Count unique item/city combinations with fresh data
        fresh_data = db.query(
            MarketTick.item_id,
            MarketTick.city
        ).filter(
            MarketTick.timestamp >= cutoff_time
        ).distinct().count()
        
        # Get all unique combinations
        total_combinations = db.query(
            MarketTick.item_id,
            MarketTick.city
        ).distinct().count()
        
        # Get stale items
        stale_items = db.query(
            MarketTick.item_id,
            MarketTick.city,
            func.max(MarketTick.timestamp).label('last_seen')
        ).group_by(
            MarketTick.item_id,
            MarketTick.city
        ).having(
            func.max(MarketTick.timestamp) < cutoff_time
        ).limit(20).all()
        
        return {
            'source_counts': {sc.source: sc.count for sc in source_counts},
            'latest_ingests': [
                {
                    'source': stat.source,
                    'last_ingest_at': stat.last_ingest_at.isoformat() if stat.last_ingest_at else None,
                    'total_records': stat.total_records,
                    'daily_records': stat.daily_records
                }
                for stat in latest_ingests
            ],
            'fresh_data_coverage': {
                'fresh': fresh_data,
                'total': total_combinations,
                'percentage': round((fresh_data / total_combinations * 100) if total_combinations > 0 else 0, 2)
            },
            'stale_items': [
                {
                    'item_id': item.item_id,
                    'city': item.city,
                    'last_seen': item.last_seen.isoformat(),
                    'age_hours': round((datetime.utcnow() - item.last_seen).total_seconds() / 3600, 2)
                }
                for item in stale_items
            ]
        }
    
    def merge_with_aodp(
        self, 
        db: Session,
        aodp_data: List[Dict[str, Any]],
        region: str,
        max_age_hours: int
    ) -> List[Dict[str, Any]]:
        """
        Merge AODP data with private data, preferring private when fresh
        
        Args:
            db: Database session
            aodp_data: Data from AODP API
            region: Server region
            max_age_hours: Maximum age for private data preference
            
        Returns:
            Merged data with source indicators
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        merged = []
        
        for aodp_record in aodp_data:
            city = aodp_record.get('city')
            item_id = aodp_record.get('item_id')
            quality = aodp_record.get('quality', 0)
            
            # Check for private data
            private_tick = db.query(MarketTick).filter(
                and_(
                    MarketTick.source == 'PRIVATE',
                    MarketTick.region == region,
                    MarketTick.city == city,
                    MarketTick.item_id == item_id,
                    MarketTick.quality == quality,
                    MarketTick.timestamp >= cutoff_time
                )
            ).order_by(MarketTick.timestamp.desc()).first()
            
            if private_tick:
                # Use private data
                record = self._tick_to_dict(private_tick)
                record['source_priority'] = 'PRIVATE'
            else:
                # Use AODP data
                record = aodp_record.copy()
                record['source'] = 'AODP'
                record['source_priority'] = 'AODP'
                
                # Calculate age if timestamp available
                if 'sell_price_min_date' in record:
                    try:
                        timestamp = datetime.fromisoformat(record['sell_price_min_date'].replace('Z', '+00:00'))
                        record['age_hours'] = round((datetime.utcnow() - timestamp).total_seconds() / 3600, 2)
                    except:
                        record['age_hours'] = 999
            
            merged.append(record)
        
        return merged