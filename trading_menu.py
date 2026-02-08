"""
Interactive Trading Menu for Nado Exchange
===========================================
A user-friendly menu interface for trading on Nado.xyz

Features:
- View available products and prices
- Place buy limit orders
- Place sell limit orders (close positions)
- Cancel all open orders
- Settings loaded from config.py

Usage:
    python trading_menu.py
"""

import asyncio
import sys
from typing import Optional

from nado_trading_module import NadoTrader

# Import configuration
try:
    from config import (
        PRIVATE_KEY,
        MODE,
        SUBACCOUNT_NAME,
        DEFAULT_PRODUCT_ID,
        DEFAULT_ORDER_SIZE,
        PRICE_OFFSET_USD,
        POST_ONLY,
        REDUCE_ONLY,
        TIME_IN_FORCE
    )
except ImportError:
    print("⚠️  config.py not found. Please create it from config.example.py")
    sys.exit(1)

if PRIVATE_KEY == 'your_private_key_here':
    print("⚠️  Please set your private key in config.py")
    sys.exit(1)


class TradingMenu:
    """Interactive trading menu for Nado exchange."""

    def __init__(self):
        self.trader: Optional[NadoTrader] = None
        self.products = []
        self.product_map = {}

    async def initialize(self):
        """Initialize connection to Nado exchange."""
        print("\n" + "="*60)
        print("🚀 Nado Trading Bot - Interactive Menu")
        print("="*60)

        self.trader = NadoTrader(
            private_key=PRIVATE_KEY,
            mode=MODE,
            subaccount_name=SUBACCOUNT_NAME
        )

        await self.trader.connect()

        # Load products
        self.products = self.trader.get_perpetual_products()
        self.product_map = {p['product_id']: p for p in self.products}

    async def cleanup(self):
        """Cleanup and disconnect."""
        if self.trader:
            await self.trader.disconnect()

    def display_menu(self):
        """Display the main menu."""
        print("\n" + "-"*60)
        print("📋 MAIN MENU")
        print("-"*60)
        print("1) Show information about products")
        print("2) Place buy limit order")
        print("3) Place sell limit order (close position)")
        print("4) Cancel all open orders")
        print("5) View open orders")
        print("6) View open positions")
        print("0) Exit")
        print("-"*60)

    async def show_products_info(self):
        """Display information about available products."""
        print("\n" + "="*60)
        print(f"📊 Available Products: {len(self.products)}")
        print("="*60)

        for p in self.products:
            price_str = f"${p['price']:>10,.2f}" if p['price'] else "N/A".rjust(10)

            # Format leverage information
            leverage_str = f"{p['max_leverage']:>4.0f}x" if p.get('max_leverage') else " N/A"

            default_marker = " ⭐" if p['product_id'] == DEFAULT_PRODUCT_ID else ""
            print(f"  ID: {p['product_id']:2d} | {p['symbol']:10s} | Price: {price_str} | Max Leverage: {leverage_str}{default_marker}")

        if DEFAULT_PRODUCT_ID in self.product_map:
            print(f"\n⭐ Default trading product: {self.product_map[DEFAULT_PRODUCT_ID]['symbol']} (ID: {DEFAULT_PRODUCT_ID})")

        input("\nPress Enter to continue...")

    async def place_buy_order(self):
        """Place a buy limit order."""
        print("\n" + "="*60)
        print("📈 PLACE BUY LIMIT ORDER")
        print("="*60)

        # Get product ID
        product_id_input = input(f"Product ID (default: {DEFAULT_PRODUCT_ID}): ").strip()
        product_id = int(product_id_input) if product_id_input else DEFAULT_PRODUCT_ID

        if product_id not in self.product_map:
            print(f"❌ Invalid product ID: {product_id}")
            return

        product_symbol = self.product_map[product_id]['symbol']
        current_price = self.product_map[product_id].get('price')

        # Show current price and orderbook
        try:
            orderbook = await self.trader.get_orderbook(product_id, depth=5)
            if orderbook['bids'] and orderbook['asks']:
                best_bid = orderbook['bids'][0]['price']
                best_ask = orderbook['asks'][0]['price']
                print(f"\n📊 {product_symbol} Market:")
                print(f"   Best Bid: ${best_bid:,.2f}")
                print(f"   Best Ask: ${best_ask:,.2f}")
                current_price = best_bid  # Use best bid for buy orders
        except Exception as e:
            print(f"⚠️  Could not fetch orderbook: {e}")

        # Get order size
        size_input = input(f"Order size (default: {DEFAULT_ORDER_SIZE}): ").strip()
        size = float(size_input) if size_input else DEFAULT_ORDER_SIZE

        # Get order price
        if current_price:
            suggested_price = current_price - PRICE_OFFSET_USD
            print(f"\nSuggested price: ${suggested_price:,.2f} (market ${current_price:,.2f} - offset ${PRICE_OFFSET_USD})")
        else:
            suggested_price = None

        price_input = input(f"Order price (USD){f' (default: {suggested_price:.2f})' if suggested_price else ''}: ").strip()

        if not price_input and suggested_price:
            price = suggested_price
        elif price_input:
            price = float(price_input)
        else:
            print("❌ Price is required")
            return

        # Confirm order
        order_value = size * price
        print(f"\n📋 Order Summary:")
        print(f"   Product:    {product_symbol} (ID: {product_id})")
        print(f"   Side:       BUY (LONG)")
        print(f"   Size:       {size}")
        print(f"   Price:      ${price:,.2f}")
        print(f"   Value:      ${order_value:,.2f}")
        print(f"   Post Only:  {POST_ONLY}")

        confirm = input("\n✅ Place this order? (y/n): ").strip().lower()

        if confirm == 'y':
            try:
                result = await self.trader.buy_limit(
                    product_id=product_id,
                    price=price,
                    size=size,
                    post_only=POST_ONLY,
                    reduce_only=REDUCE_ONLY,
                    time_in_force=TIME_IN_FORCE
                )

                if result.get('success'):
                    print(f"\n✅ Order placed successfully!")
                    print(f"   Order ID: {result.get('order_id', 'N/A')[:16]}...")
                else:
                    print(f"\n❌ Order failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"\n❌ Error placing order: {e}")
        else:
            print("\n❌ Order cancelled")

        input("\nPress Enter to continue...")

    async def place_sell_order(self):
        """Place a sell limit order (close position)."""
        print("\n" + "="*60)
        print("📉 PLACE SELL LIMIT ORDER (CLOSE POSITION)")
        print("="*60)

        # Show current positions
        positions = await self.trader.get_positions()
        if positions:
            print("\n💼 Current Positions:")
            for pos in positions:
                product_symbol = self.product_map.get(pos['product_id'], {}).get('symbol', f"Product {pos['product_id']}")
                size = abs(pos['size'])
                pnl = pos['unrealized_pnl']
                print(f"   {product_symbol:10s} | {pos['side'].upper():5s} | Size: {size:>10.4f} | PnL: ${pnl:>10.2f}")
        else:
            print("\n⚠️  No open positions")

        # Get product ID
        product_id_input = input(f"\nProduct ID (default: {DEFAULT_PRODUCT_ID}): ").strip()
        product_id = int(product_id_input) if product_id_input else DEFAULT_PRODUCT_ID

        if product_id not in self.product_map:
            print(f"❌ Invalid product ID: {product_id}")
            return

        product_symbol = self.product_map[product_id]['symbol']
        current_price = self.product_map[product_id].get('price')

        # Show current price and orderbook
        try:
            orderbook = await self.trader.get_orderbook(product_id, depth=5)
            if orderbook['bids'] and orderbook['asks']:
                best_bid = orderbook['bids'][0]['price']
                best_ask = orderbook['asks'][0]['price']
                print(f"\n📊 {product_symbol} Market:")
                print(f"   Best Bid: ${best_bid:,.2f}")
                print(f"   Best Ask: ${best_ask:,.2f}")
                current_price = best_ask  # Use best ask for sell orders
        except Exception as e:
            print(f"⚠️  Could not fetch orderbook: {e}")

        # Get order size
        size_input = input(f"Order size (default: {DEFAULT_ORDER_SIZE}): ").strip()
        size = float(size_input) if size_input else DEFAULT_ORDER_SIZE

        # Get order price
        if current_price:
            suggested_price = current_price + PRICE_OFFSET_USD
            print(f"\nSuggested price: ${suggested_price:,.2f} (market ${current_price:,.2f} + offset ${PRICE_OFFSET_USD})")
        else:
            suggested_price = None

        price_input = input(f"Order price (USD){f' (default: {suggested_price:.2f})' if suggested_price else ''}: ").strip()

        if not price_input and suggested_price:
            price = suggested_price
        elif price_input:
            price = float(price_input)
        else:
            print("❌ Price is required")
            return

        # Confirm order
        order_value = size * price
        print(f"\n📋 Order Summary:")
        print(f"   Product:    {product_symbol} (ID: {product_id})")
        print(f"   Side:       SELL (SHORT/CLOSE)")
        print(f"   Size:       {size}")
        print(f"   Price:      ${price:,.2f}")
        print(f"   Value:      ${order_value:,.2f}")
        print(f"   Post Only:  {POST_ONLY}")

        confirm = input("\n✅ Place this order? (y/n): ").strip().lower()

        if confirm == 'y':
            try:
                result = await self.trader.sell_limit(
                    product_id=product_id,
                    price=price,
                    size=size,
                    post_only=POST_ONLY,
                    reduce_only=REDUCE_ONLY,
                    time_in_force=TIME_IN_FORCE
                )

                if result.get('success'):
                    print(f"\n✅ Order placed successfully!")
                    print(f"   Order ID: {result.get('order_id', 'N/A')[:16]}...")
                else:
                    print(f"\n❌ Order failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"\n❌ Error placing order: {e}")
        else:
            print("\n❌ Order cancelled")

        input("\nPress Enter to continue...")

    async def cancel_all_orders(self):
        """Cancel all open orders."""
        print("\n" + "="*60)
        print("🗑️  CANCEL ALL OPEN ORDERS")
        print("="*60)

        # Show current open orders
        open_orders = await self.trader.get_open_orders()

        if not open_orders:
            print("\n⚠️  No open orders to cancel")
            input("\nPress Enter to continue...")
            return

        print(f"\n📋 Current Open Orders: {len(open_orders)}")
        for order in open_orders:
            size = abs(float(order['amount']))
            unfilled = float(order.get('unfilled_amount', size))
            price = float(order['price'])
            product_symbol = self.product_map.get(order['product_id'], {}).get('symbol', f"Product {order['product_id']}")
            print(f"   {product_symbol:10s} | {order['side'].upper():4s} | Size: {size:>8.4f} | Price: ${price:>8.2f}")

        confirm = input(f"\n⚠️  Cancel ALL {len(open_orders)} orders? (y/n): ").strip().lower()

        if confirm == 'y':
            try:
                result = await self.trader.cancel_all_orders()

                if result.get('success'):
                    print(f"\n✅ All orders cancelled successfully!")
                else:
                    print(f"\n❌ Cancellation failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"\n❌ Error cancelling orders: {e}")
        else:
            print("\n❌ Cancellation aborted")

        input("\nPress Enter to continue...")

    async def view_open_orders(self):
        """View all open orders."""
        print("\n" + "="*60)
        print("📋 OPEN ORDERS")
        print("="*60)

        open_orders = await self.trader.get_open_orders()

        if not open_orders:
            print("\n⚠️  No open orders")
        else:
            print(f"\nTotal: {len(open_orders)} orders\n")
            for order in open_orders:
                size = abs(float(order['amount']))
                unfilled = float(order.get('unfilled_amount', size))
                price = float(order['price'])
                order_value = unfilled * price
                product_symbol = self.product_map.get(order['product_id'], {}).get('symbol', f"Product {order['product_id']}")
                print(f"   {product_symbol:10s} | {order['side'].upper():4s} | Size: {size:>8.4f} | Unfilled: {unfilled:>8.4f} | Price: ${price:>8.2f} | Value: ${order_value:>10.2f}")

        input("\nPress Enter to continue...")

    async def view_positions(self):
        """View all open positions."""
        print("\n" + "="*60)
        print("💼 OPEN POSITIONS")
        print("="*60)

        positions = await self.trader.get_positions()

        if not positions:
            print("\n⚠️  No open positions")
        else:
            print(f"\nTotal: {len(positions)} positions\n")
            total_pnl = 0
            for pos in positions:
                product_symbol = self.product_map.get(pos['product_id'], {}).get('symbol', f"Product {pos['product_id']}")
                size = abs(pos['size'])
                pnl = pos['unrealized_pnl']
                total_pnl += pnl
                pnl_str = f"${pnl:>10.2f}"
                print(f"   {product_symbol:10s} | {pos['side'].upper():5s} | Size: {size:>10.4f} | Unrealized PnL: {pnl_str}")

            print(f"\n   Total Unrealized PnL: ${total_pnl:>10.2f}")

        input("\nPress Enter to continue...")

    async def run(self):
        """Run the interactive menu."""
        try:
            await self.initialize()

            while True:
                self.display_menu()
                choice = input("\nEnter your choice: ").strip()

                if choice == '1':
                    await self.show_products_info()
                elif choice == '2':
                    await self.place_buy_order()
                elif choice == '3':
                    await self.place_sell_order()
                elif choice == '4':
                    await self.cancel_all_orders()
                elif choice == '5':
                    await self.view_open_orders()
                elif choice == '6':
                    await self.view_positions()
                elif choice == '0':
                    print("\n👋 Goodbye!")
                    break
                else:
                    print("\n❌ Invalid choice. Please try again.")
                    input("\nPress Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()


async def main():
    """Main entry point."""
    menu = TradingMenu()
    await menu.run()


if __name__ == "__main__":
    asyncio.run(main())
