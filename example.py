#!/usr/bin/env python3
"""
Simple Nado Trading Example
============================
Demonstrates basic trading operations on Nado.xyz

Before running:
1. Install dependencies: pip install nado-protocol web3 eth-account
2. Copy config.example.py to config.py and add your private key
3. This uses MAINNET by default - for testing, set MODE="testnet" in config.py
   and get testnet USDT0 from: https://testnet.nado.xyz/portfolio/faucet
"""

import asyncio
import os
from nado_trading_module import NadoTrader

# Try to import from config.py, fallback to environment variable
try:
    from config import PRIVATE_KEY, MODE
except ImportError:
    print("⚠️  config.py not found. Please create it from config.example.py")
    print("   Or set NADO_PRIVATE_KEY environment variable")
    PRIVATE_KEY = os.environ.get('NADO_PRIVATE_KEY', 'your_private_key_here')
    MODE = os.environ.get('NADO_MODE', 'mainnet')


async def simple_trading_example():
    """Simple example showing basic trading operations."""
    
    if PRIVATE_KEY == 'your_private_key_here':
        print("⚠️  Please set your private key!")
        print("   Either:")
        print("   1. Create config.py from config.example.py and add your key")
        print("   2. Set NADO_PRIVATE_KEY environment variable")
        return
    
    print("=" * 60)
    print("Nado.xyz Trading Example")
    print("=" * 60)
    
    # Initialize trader with context manager (auto-connects/disconnects)
    async with NadoTrader(PRIVATE_KEY, mode=MODE) as trader:
        
        # Step 1: View available products
        print("\n📊 Available Perpetual Products:")
        print("-" * 60)
        products = trader.get_perpetual_products()
        for p in products[:10]:  # Show first 10
            price_str = f"${p['price']:,.2f}" if p['price'] else "N/A"
            print(f"  {p['product_id']:2d}. {p['symbol']:12s} {price_str:>15s}")
        
        # Step 2: Check account status
        print("\n💰 Account Information:")
        print("-" * 60)
        account = await trader.get_account_info()
        print(f"  Subaccount: {account['subaccount'][:16]}...")
        print(f"  Health:     {account['health']:.4f}")
        
        print("\n  Balances:")
        for balance in account['balances'][:5]:  # Show first 5
            if balance['balance'] != 0:
                print(f"    Product {balance['product_id']}: {balance['balance']:,.8f}")
        
        # Step 3: Get orderbook for BTC-PERP (usually product_id=1)
        btc_product_id = 1
        print(f"\n📖 Orderbook for Product {btc_product_id}:")
        print("-" * 60)
        
        try:
            orderbook = await trader.get_orderbook(btc_product_id, depth=3)
            
            print("  Asks (Sell Orders):")
            for i, ask in enumerate(orderbook['asks'][:3], 1):
                print(f"    {i}. ${ask['price']:,.2f}  -  {ask['size']:.8f}")
            
            print("  ---")
            
            print("  Bids (Buy Orders):")
            for i, bid in enumerate(orderbook['bids'][:3], 1):
                print(f"    {i}. ${bid['price']:,.2f}  -  {bid['size']:.8f}")
            
            best_bid = orderbook['bids'][0]['price']
            best_ask = orderbook['asks'][0]['price']
            spread = best_ask - best_bid
            print(f"\n  Spread: ${spread:,.2f}")
            
        except Exception as e:
            print(f"  ⚠️  Could not fetch orderbook: {str(e)}")
            best_bid = 45000  # Fallback values for example
            best_ask = 45100
        
        # Step 4: Place example orders (commented out by default)
        print("\n📝 Order Placement Example:")
        print("-" * 60)
        print("  The following code shows how to place orders.")
        print("  Uncomment the code block below to actually place orders.\n")
        
        # UNCOMMENT THE FOLLOWING BLOCK TO PLACE REAL ORDERS:
        """
        # Calculate order prices (slightly away from market)
        buy_price = best_bid - 50   # $50 below best bid
        sell_price = best_ask + 50  # $50 above best ask
        order_size = 0.001          # Small size for testing
        
        print(f"  Placing BUY order: {order_size} BTC @ ${buy_price:,.2f}")
        buy_result = await trader.buy_limit(
            product_id=btc_product_id,
            price=buy_price,
            size=order_size,
            post_only=True  # Ensure we're a maker
        )
        
        if buy_result['success']:
            print(f"  ✅ Buy order placed! ID: {buy_result['order_id'][:16]}...")
        else:
            print(f"  ❌ Buy order failed: {buy_result.get('error', 'Unknown error')}")
        
        print(f"\n  Placing SELL order: {order_size} BTC @ ${sell_price:,.2f}")
        sell_result = await trader.sell_limit(
            product_id=btc_product_id,
            price=sell_price,
            size=order_size,
            post_only=True
        )
        
        if sell_result['success']:
            print(f"  ✅ Sell order placed! ID: {sell_result['order_id'][:16]}...")
        else:
            print(f"  ❌ Sell order failed: {sell_result.get('error', 'Unknown error')}")
        
        # Step 5: View open orders
        print("\n📋 Open Orders:")
        print("-" * 60)
        await asyncio.sleep(1)  # Give orders time to register
        
        open_orders = await trader.get_open_orders(product_id=btc_product_id)
        
        if open_orders:
            for order in open_orders:
                side_emoji = "🟢" if order['side'] == 'buy' else "🔴"
                print(f"  {side_emoji} {order['side'].upper():4s} "
                      f"{abs(order['amount']):,.8f} @ ${order['price']:,.2f}")
        else:
            print("  No open orders")
        
        # Step 6: Cancel all orders
        print("\n🗑️  Cancelling Orders:")
        print("-" * 60)
        cancel_result = await trader.cancel_all_orders(product_id=btc_product_id)
        if cancel_result['success']:
            print(f"  ✅ All orders cancelled for product {btc_product_id}")
        else:
            print(f"  ⚠️  Error cancelling: {cancel_result.get('error', 'Unknown')}")
        """
        
        # Step 7: View positions
        print("\n📈 Current Positions:")
        print("-" * 60)
        positions = await trader.get_positions()
        
        if positions:
            for pos in positions:
                side_emoji = "🟢" if pos['side'] == 'long' else "🔴"
                pnl_emoji = "💚" if pos['unrealized_pnl'] >= 0 else "❤️"
                print(f"  {side_emoji} Product {pos['product_id']}: "
                      f"{pos['side'].upper():5s} {abs(pos['size']):,.8f} "
                      f"{pnl_emoji} PnL: ${pos['unrealized_pnl']:,.2f}")
        else:
            print("  No open positions")
    
    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


async def market_making_example():
    """Example of a simple market-making strategy."""
    
    if PRIVATE_KEY == 'your_private_key_here':
        print("⚠️  Please set your private key in config.py")
        print("   Or set NADO_PRIVATE_KEY environment variable")
        return
    
    print("\n🤖 Market Making Strategy Example")
    print("=" * 60)
    print("This example places orders on both sides of the market")
    print("and continuously updates them based on the orderbook.")
    print("=" * 60)
    
    async with NadoTrader(PRIVATE_KEY, mode=MODE) as trader:
        
        product_id = 1  # BTC-PERP
        order_size = 0.001
        spread_offset = 20  # $20 from mid-price
        
        print(f"\nStarting market making on product {product_id}")
        print(f"Order size: {order_size} BTC")
        print(f"Spread offset: ${spread_offset}")
        
        # This is just a demonstration - a real market maker would run in a loop
        for iteration in range(1):  # Just 1 iteration for demo
            
            # Get current orderbook
            orderbook = await trader.get_orderbook(product_id, depth=5)
            best_bid = orderbook['bids'][0]['price']
            best_ask = orderbook['asks'][0]['price']
            mid_price = (best_bid + best_ask) / 2
            
            print(f"\nIteration {iteration + 1}:")
            print(f"  Mid price: ${mid_price:,.2f}")
            print(f"  Spread: ${best_ask - best_bid:,.2f}")
            
            # Cancel existing orders
            await trader.cancel_all_orders(product_id)
            
            # Place new orders
            buy_price = mid_price - spread_offset
            sell_price = mid_price + spread_offset
            
            # Place buy order
            await trader.buy_limit(
                product_id=product_id,
                price=buy_price,
                size=order_size,
                post_only=True
            )
            print(f"  📝 Buy order: {order_size} @ ${buy_price:,.2f}")
            
            # Place sell order
            await trader.sell_limit(
                product_id=product_id,
                price=sell_price,
                size=order_size,
                post_only=True
            )
            print(f"  📝 Sell order: {order_size} @ ${sell_price:,.2f}")
            
            # In a real implementation, you would:
            # 1. Sleep for some interval
            # 2. Check if orders were filled
            # 3. Update prices based on new market conditions
            # 4. Manage inventory and risk
            
        print("\n⚠️  This is a simplified example.")
        print("A production market maker would:")
        print("  - Run continuously in a loop")
        print("  - Monitor fills and adjust inventory")
        print("  - Implement risk management")
        print("  - Handle errors and reconnections")
        print("  - Use more sophisticated pricing")


if __name__ == "__main__":
    print("\nChoose an example to run:")
    print("1. Simple Trading Example (recommended)")
    print("2. Market Making Example")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        asyncio.run(simple_trading_example())
    elif choice == "2":
        asyncio.run(market_making_example())
    else:
        print("Invalid choice. Running simple example...")
        asyncio.run(simple_trading_example())
