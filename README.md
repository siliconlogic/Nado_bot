# Nado.xyz Trading Module

A Python module for trading perpetual futures on Nado.xyz exchange using limit orders.

## Overview

Nado is a decentralized exchange (DEX) built on the Ink L2 network offering:
- Perpetual futures with up to 20x leverage
- Unified margin account (cross-collateral)
- High-performance orderbook (5-15ms latency)
- Spot and perpetuals trading

This module provides a clean Python interface for programmatic trading.

## Installation

```bash
pip install nado-protocol web3 eth-account
```

## Configuration

### Option 1: Using config.py (Recommended)

1. Copy the example config file:
   ```bash
   cp config.example.py config.py
   ```

2. Edit `config.py` and add your private key:
   ```python
   PRIVATE_KEY = "0xYOUR_PRIVATE_KEY_HERE"
   MODE = "mainnet"  # or "testnet"
   ```

3. The `config.py` file is automatically ignored by git (see `.gitignore`)

### Option 2: Using Environment Variables

```bash
export NADO_PRIVATE_KEY="0xYOUR_PRIVATE_KEY_HERE"
export NADO_MODE="mainnet"
```

## Quick Start

```python
import asyncio
from nado_trading_module import NadoTrader
from config import PRIVATE_KEY, MODE

async def main():
    async with NadoTrader(
        private_key=PRIVATE_KEY,
        mode=MODE
    ) as trader:
        
        # Place a buy limit order
        order = await trader.buy_limit(
            product_id=1,      # BTC-PERP
            price=45000.0,     # Limit price
            size=0.1,          # Size in BTC
            post_only=True     # Maker only
        )
        print(f"Order placed: {order['order_id']}")
        
        # Check open orders
        orders = await trader.get_open_orders(product_id=1)
        print(f"Open orders: {len(orders)}")
        
        # Cancel order
        await trader.cancel_order(
            product_id=1,
            order_digest=order['order_id']
        )

asyncio.run(main())
```

## Features

### Order Placement
- **Limit Orders**: Buy and sell with specified price levels
- **Order Types**: GTC, IOC, FOK, Post-Only
- **Reduce-Only**: Close positions without opening new ones
- **Time-in-Force**: Flexible order lifetime management

### Account Management
- View account balances and health
- Track open positions
- Monitor unrealized PnL
- Multi-collateral support

### Order Management
- Cancel individual orders
- Cancel all orders for a product
- Query open orders
- Real-time order status

### Market Data
- Get orderbook depth
- View available products
- Access oracle prices
- Product information

## API Reference

### NadoTrader Class

#### Initialization

```python
trader = NadoTrader(
    private_key="0x...",           # Your Ethereum private key
    mode="mainnet",                # "mainnet" or "testnet" (default: mainnet)
    subaccount_name="default"      # Subaccount name (optional)
)
```

#### Connection Methods

```python
await trader.connect()             # Connect to exchange
await trader.disconnect()          # Disconnect
```

Or use as async context manager:
```python
async with NadoTrader(...) as trader:
    # Trading code here
    pass
```

#### Trading Methods

**Place Buy Limit Order**
```python
result = await trader.buy_limit(
    product_id=1,              # Product ID (1=BTC-PERP, etc.)
    price=45000.0,             # Limit price
    size=0.1,                  # Order size
    reduce_only=False,         # Only reduce existing position
    post_only=False,           # Must be maker order
    time_in_force="GTC"        # GTC, IOC, or FOK
)
```

**Place Sell Limit Order**
```python
result = await trader.sell_limit(
    product_id=1,
    price=46000.0,
    size=0.1,
    reduce_only=False,
    post_only=False,
    time_in_force="GTC"
)
```

**Cancel Order**
```python
await trader.cancel_order(
    product_id=1,
    order_digest="0x..."       # Order ID from order placement
)
```

**Cancel All Orders**
```python
# Cancel all orders for a specific product
await trader.cancel_all_orders(product_id=1)

# Cancel all orders across all products
await trader.cancel_all_orders()
```

#### Query Methods

**Get Account Information**
```python
account = await trader.get_account_info()
# Returns:
# {
#     'subaccount': '0x...',
#     'health': 0.95,
#     'balances': [...]
# }
```

**Get Open Orders**
```python
# All open orders
orders = await trader.get_open_orders()

# Orders for specific product
orders = await trader.get_open_orders(product_id=1)
```

**Get Positions**
```python
positions = await trader.get_positions()
# Returns list of open positions with size and PnL
```

**Get Orderbook**
```python
orderbook = await trader.get_orderbook(
    product_id=1,
    depth=10               # Number of price levels
)
```

**Get Available Products**
```python
products = trader.get_perpetual_products()
# Returns list of perpetual products with IDs and symbols
```

## Product IDs

Common perpetual products (testnet):
- 1: BTC-PERP
- 2: ETH-PERP
- 3: Other perpetuals

Use `get_perpetual_products()` to see all available products.

## Order Parameters Explained

### Time in Force
- **GTC** (Good Till Cancel): Order stays open until filled or cancelled (default)
- **IOC** (Immediate or Cancel): Execute immediately or cancel
- **FOK** (Fill or Kill): Must fill completely or cancel

### Order Execution Types
- **Default**: Normal limit order
- **Post-Only**: Must be maker (won't execute immediately)
- **IOC**: Immediate execution or cancel
- **FOK**: Full execution or cancel

### Reduce Only
When `reduce_only=True`, the order can only decrease your position size, not increase it. Useful for closing positions without risk of opening new ones.

## Complete Example

```python
import asyncio
from nado_trading_module import NadoTrader

async def trading_bot():
    """Example trading bot using the Nado module."""
    
    # Initialize
    trader = NadoTrader(
        private_key="your_private_key",
        mode="mainnet"
    )
    
    try:
        await trader.connect()
        
        # Get market info
        products = trader.get_perpetual_products()
        btc_product = next(p for p in products if 'BTC' in p['symbol'])
        product_id = btc_product['product_id']
        current_price = btc_product['price']
        
        print(f"BTC-PERP price: ${current_price:,.2f}")
        
        # Get orderbook
        orderbook = await trader.get_orderbook(product_id, depth=5)
        best_bid = orderbook['bids'][0]['price']
        best_ask = orderbook['asks'][0]['price']
        
        print(f"Best bid: ${best_bid:,.2f}")
        print(f"Best ask: ${best_ask:,.2f}")
        
        # Place orders on both sides
        buy_price = best_bid - 10  # 10 below best bid
        sell_price = best_ask + 10  # 10 above best ask
        
        buy_order = await trader.buy_limit(
            product_id=product_id,
            price=buy_price,
            size=0.01,
            post_only=True
        )
        
        sell_order = await trader.sell_limit(
            product_id=product_id,
            price=sell_price,
            size=0.01,
            post_only=True
        )
        
        print(f"\nOrders placed:")
        print(f"  Buy: {buy_order['order_id']}")
        print(f"  Sell: {sell_order['order_id']}")
        
        # Check status
        await asyncio.sleep(2)
        open_orders = await trader.get_open_orders(product_id)
        print(f"\nOpen orders: {len(open_orders)}")
        
        # Cancel all
        await trader.cancel_all_orders(product_id)
        print("\nAll orders cancelled")
        
    finally:
        await trader.disconnect()

if __name__ == "__main__":
    asyncio.run(trading_bot())
```

## Error Handling

```python
try:
    result = await trader.buy_limit(
        product_id=1,
        price=45000.0,
        size=0.1
    )
    
    if not result['success']:
        print(f"Order failed: {result['error']}")
    else:
        print(f"Order placed: {result['order_id']}")
        
except Exception as e:
    print(f"Error: {str(e)}")
```

## Important Notes

1. **Private Keys**: 
   - **NEVER commit your `config.py` file to version control**
   - Use `config.example.py` as a template
   - The `.gitignore` file already excludes `config.py`
   - For production, use environment variables:
     ```python
     import os
     private_key = os.environ.get('NADO_PRIVATE_KEY')
     ```

2. **Rate Limits**: 
   - With spot leverage: 600 orders/minute
   - Without spot leverage: 30 orders/minute

3. **Precision**: Nado uses 18 decimal precision internally (x18 format). The module handles conversion automatically.

4. **Testing**: The module defaults to mainnet. For testing, explicitly set `mode="testnet"`. Get free testnet USDT0 from the faucet at https://testnet.nado.xyz/portfolio/faucet

5. **Margin**: Nado uses unified margin (cross-collateral). Your entire account balance backs all positions.

## Troubleshooting

### Signature Errors
- Ensure your private key is correct
- Check that you're using the right network (testnet vs mainnet)
- Verify your account has been initialized with a deposit

### Order Rejection
- Check if you have sufficient collateral
- Verify the product ID exists
- Ensure price and size are within valid ranges
- Check rate limits

### Connection Issues
- Verify network connectivity
- Check if Nado's API is operational
- Ensure correct mode ("testnet" vs "mainnet")

## Resources

- [Nado Documentation](https://docs.nado.xyz)
- [Python SDK Docs](https://nadohq.github.io/nado-python-sdk/)
- [Nado Website](https://nado.xyz)
- [Testnet Faucet](https://testnet.nado.xyz/portfolio/faucet)

## License

This module is provided as-is for educational and commercial use. 

## Disclaimer

Trading cryptocurrencies and derivatives carries significant risk. This software is provided without warranty. Always test thoroughly on testnet before using real funds.
