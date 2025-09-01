# Albion Market Helper - Private Data Ingestion System

## Overview

This system allows you to capture and store your own market data locally while playing Albion Online, giving you fresher and more reliable data than public sources. The system prioritizes YOUR data (marked as PRIVATE) over public AODP data.

## How It Works

1. **Albion Data Client (ADC)** runs on your PC and captures market data when you open the market
2. **Your backend** receives and stores this data with source='PRIVATE'
3. **The app** prefers PRIVATE data when fresh, falls back to AODP when needed
4. **Frontend** shows data source and age for transparency

## Installation

### 1. Install Albion Data Client

Download from: https://github.com/ao-data/albiondata-client/releases

Install to default location: `C:\Program Files\Albion Data Client\`

### 2. Database Setup

The backend automatically creates SQLite database on first run. For production, consider PostgreSQL:

```python
# In .env for PostgreSQL
DATABASE_URL=postgresql://user:password@localhost/albion_market
```

### 3. Run ADC with Private Ingestion

#### Option A: Private Only (Recommended)
Your data stays local, not shared with AODP:
```batch
albiondata-client.exe -d -p "http://localhost:8000/api/ingest/adc"
```

#### Option B: Dual Mode
Share with AODP AND keep local copy:
```batch
albiondata-client.exe -i "http+pow://pow.west.albion-online-data.com,http://localhost:8000/api/ingest/adc"
```

#### Option C: Use the Setup Script
Run `setup_adc.bat` and choose your mode.

### 4. Verify It's Working

1. Start your backend: `python -m uvicorn app:app --reload`
2. Run ADC with one of the options above
3. Open Albion Online and check some market prices
4. Visit http://localhost:8000/api/private/stats
5. You should see your PRIVATE data count increasing

## API Endpoints

### Ingest Endpoint
```
POST /api/ingest/adc
```
Receives data from ADC. Automatically deduplicates and stores with source='PRIVATE'.

### Stats Endpoint
```
GET /api/private/stats
```
Shows:
- Record counts by source (PRIVATE vs AODP)
- Last ingestion time
- Fresh data coverage percentage
- Stale items that need market checks

### Enhanced Market Endpoints

#### Prices V2
```
POST /api/market/prices/v2
```
Returns prices with source indicators and age information.

#### Opportunities V2
```
POST /api/market/opportunities/v2
```
Returns ALL routes (including negative profit) with:
- Source for buy/sell data (PRIVATE/AODP)
- Age in hours for each price point
- Profit can be negative (frontend filters)

## Frontend Features

### Data Status Panel
Shows real-time statistics:
- Private vs AODP record counts
- Fresh data coverage percentage
- Last ingestion timestamp
- List of stale items needing updates

### Enhanced Results Table
- **Color coding**: Green for profit, red for loss
- **Source badges**: P for PRIVATE, A for AODP
- **Age indicator**: Shows oldest data age in hours
- **Filters**:
  - Show only profitable routes
  - Minimum profit (silver)
  - Minimum profit percentage
- **Export**: Includes source and age in CSV

## Data Priority System

The system uses this priority order:
1. **PRIVATE data** within max_age_hours
2. **AODP data** if no private data available
3. Returns nothing if both are stale

## Breeding Calculator Updates

The breeding calculator now also uses private data for:
- Animal prices (if buying instead of breeding)
- Material prices (planks, leather)
- Mount selling prices
- Food prices

Each result shows:
- `source_buy`: Where material prices came from
- `source_sell`: Where selling prices came from
- `age_buy_hours` / `age_sell_hours`: Data freshness

## Troubleshooting

### ADC Not Capturing Data
- Run as Administrator
- Check Windows Firewall isn't blocking
- Try with `-l` flag if multiple network adapters:
  ```batch
  albiondata-client.exe -l "YOUR-MAC-ADDRESS" -p "http://localhost:8000/api/ingest/adc"
  ```

### No Private Data Showing
- Verify backend is running on port 8000
- Check backend console for ingest logs
- Open more market tabs in-game
- Check http://localhost:8000/api/private/stats

### Database Issues
- SQLite locks: Restart backend
- For production: Use PostgreSQL
- Clear old data: Delete `albion_market.db` and restart

## Performance Tips

1. **Market Checking Strategy**
   - Focus on items shown as "stale" in stats
   - Check your common trade routes daily
   - Use quick price check (hover) for faster updates

2. **Database Maintenance**
   ```sql
   -- Clean old data (>7 days)
   DELETE FROM market_ticks 
   WHERE timestamp < datetime('now', '-7 days');
   ```

3. **Batch Operations**
   - Open multiple market tabs quickly
   - ADC captures all visible data
   - More efficient than checking one by one

## Security Notes

- ADC only reads network packets, doesn't modify game
- Complies with Albion Online ToS
- Your private data stays local unless you choose dual mode
- No login/authentication required

## Advanced: NATS Subscription (Optional)

For continuous data stream from AODP:

```python
# workers/nats_consumer.py
import nats

async def consume():
    nc = await nats.connect("nats://public:thenewalbiondata@nats.albion-online-data.com:4222")
    
    async def message_handler(msg):
        # Parse and store as source='AODP'
        pass
    
    await nc.subscribe("marketorders.deduped", cb=message_handler)
```

Topics available:
- `marketorders.deduped` - Processed market orders
- `markethistories.deduped` - Price history
- `goldprices.deduped` - Gold prices

## Data Verification

### Breeding Data (Confirmed)

#### Growth Times (Premium)
| Tier | Hours | Food Units |
|------|-------|------------|
| T4   | 46    | 30         |
| T5   | 70    | 90         |
| T6   | 94    | 272        |
| T7   | 118   | 805        |
| T8   | 142   | 2,367      |

#### Mount Recipes
- **T7 Transport Ox**: T7 Ox + 30× T7 Planks
- **T4 Riding Horse**: T4 Horse + 20× T4 Leather

#### Nutrition
- All vegetables/herbs provide 48 nutrition per unit
- Total nutrition = Food Units × 48

## Contributing

1. Test with different network configurations
2. Report stale data patterns
3. Optimize SQL queries for large datasets
4. Add more NATS topics support

## License

MIT - This tool enhances your Albion Online experience while respecting the game's ToS.