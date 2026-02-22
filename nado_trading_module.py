"""
Nado.xyz Trading Module
========================
A comprehensive module for connecting to Nado exchange and trading futures with limit orders.

Nado is a decentralized exchange (DEX) on the Ink L2 with perpetuals and spot trading.
This module uses the official nado-protocol Python SDK.

Installation:
    pip install nado-protocol web3 eth-account

Usage:
    from nado_trading_module import NadoTrader
    
    # Initialize trader
    trader = NadoTrader(
        private_key="your_private_key",
        mode="mainnet"  # or "testnet"
    )
    
    # Place a long limit order
    order_id = await trader.buy_limit(
        product_id=1,  # BTC-PERP
        price=45000.0,
        size=0.1
    )
    
    # Place a short limit order
    order_id = await trader.sell_limit(
        product_id=1,
        price=46000.0,
        size=0.1
    )
"""

import asyncio
import time
from typing import Optional, Dict, Any, List
from enum import Enum

from nado_protocol.client import create_nado_client, NadoClientMode
from nado_protocol.utils.math import to_x18, from_x18
from nado_protocol.utils.bytes32 import subaccount_to_hex
from nado_protocol.engine_client.types.execute import (
    PlaceOrderParams,
    CancelOrdersParams,
    CancelProductOrdersParams
)
from nado_protocol.utils.execute import OrderParams


class OrderSide(Enum):
    """Order side enum"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order type enum"""
    LIMIT = "limit"
    MARKET = "market"
    POST_ONLY = "post_only"
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill


class NadoTrader:
    """
    Main trading class for Nado.xyz exchange.
    
    Handles connection management, order placement, cancellation,
    and position tracking for futures (perpetuals) trading.
    """
    
    def __init__(
        self,
        private_key: str,
        mode: str = "mainnet",
        subaccount_name: str = "default"
    ):
        """
        Initialize the Nado trader.
        
        Args:
            private_key: Ethereum private key (with or without 0x prefix)
            mode: "mainnet" or "testnet" (default: "mainnet")
            subaccount_name: Subaccount name (max 12 characters)
                Note: The SDK currently uses "default" as the subaccount.
                This parameter is stored for future use but may not affect
                the actual subaccount used by the SDK.
        """
        self.private_key = private_key
        self.mode = NadoClientMode.MAINNET if mode.lower() == "mainnet" else NadoClientMode.TESTNET
        self.subaccount_name = subaccount_name
        self.client = None
        self._products_cache = None
        self._ticker_map = {}
        self._pending_orders = {}  # Track orders not yet indexed: {digest: order_info}
        
    async def connect(self):
        """Initialize connection to Nado exchange."""
        if not self.client:
            self.client = create_nado_client(
                self.mode,
                self.private_key
            )
            print(f"✓ Connected to Nado ({self.mode.value}, subaccount: {self.subaccount_name})")
            
            # Cache products
            await self._load_products()
            
    async def disconnect(self):
        """Close connection to Nado exchange."""
        if self.client:
            # The SDK doesn't require explicit disconnection
            self.client = None
            print("✓ Disconnected from Nado")
    
    async def _load_products(self):
        """Load and cache available products."""
        products = self.client.context.engine_client.get_all_products()
        self._products_cache = {
            'spot': products.spot_products,
            'perp': products.perp_products
        }

        # Load ticker information from indexer
        try:
            tickers = self.client.context.indexer_client.get_tickers()
            self._ticker_map = {
                v['product_id']: v['base_currency']
                for v in tickers.values()
                if isinstance(v, dict) and 'product_id' in v and 'base_currency' in v
            }
        except Exception as e:
            print(f"⚠️  Could not load tickers: {e}")
            self._ticker_map = {}
    
    def get_perpetual_products(self) -> List[Dict[str, Any]]:
        """
        Get list of available perpetual products.

        Note: Product IDs are not sequential. Nado uses sparse numbering
        (typically even numbers: 2, 4, 6, 8, etc.) and not all IDs are active.

        Returns:
            List of perpetual products with their details including actual ticker symbols
        """
        if not self._products_cache:
            raise RuntimeError("Not connected. Call connect() first.")

        # Use dictionary to ensure uniqueness by product_id
        products_dict = {}

        for p in self._products_cache['perp']:
            product_id = p.product_id

            # Skip if already processed (only keep first occurrence)
            if product_id in products_dict:
                continue

            # Get ticker symbol from the ticker map loaded from indexer API
            symbol = self._ticker_map.get(product_id, f'PERP-{product_id}')

            # Calculate max leverage from risk weights
            # The initial margin weights determine the max leverage:
            # max_leverage = 1 / |1 - initial_weight|
            max_leverage = None
            if hasattr(p, 'risk'):
                risk = p.risk

                # Try to get long weight initial (most products use this)
                if hasattr(risk, 'long_weight_initial_x18'):
                    long_weight_initial = from_x18(int(risk.long_weight_initial_x18))
                    # Calculate max leverage: 1 / |1 - weight|
                    margin_fraction = abs(1.0 - long_weight_initial)
                    if margin_fraction > 0:
                        max_leverage = 1.0 / margin_fraction

                # Alternatively, could use short weight initial
                elif hasattr(risk, 'short_weight_initial_x18'):
                    short_weight_initial = from_x18(int(risk.short_weight_initial_x18))
                    margin_fraction = abs(short_weight_initial - 1.0)
                    if margin_fraction > 0:
                        max_leverage = 1.0 / margin_fraction

            products_dict[product_id] = {
                'product_id': product_id,
                'symbol': symbol,
                'oracle_price_x18': getattr(p, 'oracle_price_x18', None),
                'price': from_x18(p.oracle_price_x18) if hasattr(p, 'oracle_price_x18') and p.oracle_price_x18 else None,
                'max_leverage': max_leverage
            }

        # Convert to sorted list by product_id
        products = sorted(products_dict.values(), key=lambda x: x['product_id'])

        return products
    
    async def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information including balances and positions.
        
        Returns:
            Dictionary with account details
        """
        self._ensure_connected()
        
        # Get wallet address and derive subaccount using the SDK utility
        wallet_address = self.client.context.signer.address
        subaccount_hex = subaccount_to_hex(wallet_address, self.subaccount_name)
        
        info = self.client.context.engine_client.get_subaccount_info(subaccount_hex)

        # Calculate unrealized PnL for each balance
        balances = []
        for b in info.spot_balances + info.perp_balances:
            amount = from_x18(int(b.balance.amount)) if b.balance.amount != '0' else 0

            # Calculate PnL for perp positions
            unrealized_pnl = 0
            if amount != 0 and b.product_id in {p.product_id for p in self._products_cache['perp']}:
                # Get current price from the fresh info object (more accurate)
                # The info object contains the actual risk prices used for calculations
                product_risk = next((p for p in self._products_cache['perp'] if p.product_id == b.product_id), None)

                # Try to get price from the risk object in the fresh info
                current_price = None
                if hasattr(product_risk, 'risk') and hasattr(product_risk.risk, 'price_x18'):
                    current_price = from_x18(int(product_risk.risk.price_x18))
                elif hasattr(product_risk, 'oracle_price_x18'):
                    current_price = from_x18(int(product_risk.oracle_price_x18))

                if current_price:
                    v_quote = from_x18(int(b.balance.v_quote_balance))

                    # Debug for first position
                    if amount != 0:
                        print(f"\n🔍 PnL Calculation for Product {b.product_id}:")
                        print(f"  Amount: {amount}")
                        print(f"  Current Price: ${current_price:,.2f}")
                        print(f"  v_quote_balance: ${v_quote:,.2f}")
                        position_value = amount * current_price
                        print(f"  Position Value: ${position_value:,.2f}")
                        unrealized_pnl = position_value + v_quote
                        print(f"  Calculated PnL: ${unrealized_pnl:,.2f}\n")
                    else:
                        # PnL = position_value + v_quote_balance
                        position_value = amount * current_price
                        unrealized_pnl = position_value + v_quote

            balances.append({
                'product_id': b.product_id,
                'balance': amount,
                'unrealized_pnl': unrealized_pnl
            })

        return {
            'subaccount': subaccount_hex,
            'health': info.healths if hasattr(info, 'healths') else None,
            'balances': balances
        }
    
    async def buy_limit(
        self,
        product_id: int,
        price: float,
        size: float,
        reduce_only: bool = False,
        post_only: bool = False,
        time_in_force: str = "GTC"  # GTC, IOC, FOK
    ) -> Dict[str, Any]:
        """
        Place a limit buy order (long position).
        
        Args:
            product_id: Product ID (e.g., 1 for BTC-PERP)
            price: Limit price
            size: Order size (positive value)
            reduce_only: Only reduce existing position
            post_only: Order must be maker (won't execute immediately)
            time_in_force: GTC (Good Till Cancel), IOC (Immediate or Cancel), FOK (Fill or Kill)
            
        Returns:
            Order result with order ID and status
        """
        return await self._place_limit_order(
            product_id=product_id,
            price=price,
            size=abs(size),  # Ensure positive
            side=OrderSide.BUY,
            reduce_only=reduce_only,
            post_only=post_only,
            time_in_force=time_in_force
        )
    
    async def sell_limit(
        self,
        product_id: int,
        price: float,
        size: float,
        reduce_only: bool = False,
        post_only: bool = False,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """
        Place a limit sell order (short position).
        
        Args:
            product_id: Product ID (e.g., 1 for BTC-PERP)
            price: Limit price
            size: Order size (positive value)
            reduce_only: Only reduce existing position
            post_only: Order must be maker (won't execute immediately)
            time_in_force: GTC (Good Till Cancel), IOC (Immediate or Cancel), FOK (Fill or Kill)
            
        Returns:
            Order result with order ID and status
        """
        return await self._place_limit_order(
            product_id=product_id,
            price=price,
            size=abs(size),  # Ensure positive
            side=OrderSide.SELL,
            reduce_only=reduce_only,
            post_only=post_only,
            time_in_force=time_in_force
        )
    
    async def _place_limit_order(
        self,
        product_id: int,
        price: float,
        size: float,
        side: OrderSide,
        reduce_only: bool = False,
        post_only: bool = False,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """
        Internal method to place a limit order.
        
        Args:
            product_id: Product ID
            price: Limit price
            size: Order size (positive)
            side: BUY or SELL
            reduce_only: Only reduce existing position
            post_only: Must be maker order
            time_in_force: Order time in force
            
        Returns:
            Order placement result
        """
        self._ensure_connected()
        
        # Convert to x18 format (Nado uses 18 decimal precision)
        price_x18 = to_x18(price)
        
        # Amount is positive for buy, negative for sell
        if side == OrderSide.BUY:
            amount_x18 = to_x18(size)
        else:
            amount_x18 = to_x18(-size)
        
        # Build order appendix manually
        # Appendix structure (128 bits):
        # | value | reserved | trigger | reduce only | order type | isolated | version |
        # | 64    | 50       | 2       | 1           | 2          | 1        | 8       |
        # | 127..64 | 63..14 | 13..12  | 11          | 10..9      | 8        | 7..0    |
        
        version = 1  # Version 1
        isolated = 0  # Cross margin (not isolated)
        
        # Order type: 0=DEFAULT, 1=IOC, 2=FOK, 3=POST_ONLY
        if post_only:
            order_type = 3
        elif time_in_force == "IOC":
            order_type = 1
        elif time_in_force == "FOK":
            order_type = 2
        else:
            order_type = 0
        
        reduce_only_bit = 1 if reduce_only else 0
        trigger_type = 0  # NONE (0=NONE, 1=PRICE, 2=TWAP, 3=TWAP_CUSTOM)

        # Build the appendix as a 128-bit integer
        appendix = (
            version |
            (isolated << 8) |
            (order_type << 9) |
            (reduce_only_bit << 11) |
            (trigger_type << 12)
        )

        # Calculate expiration (30 days from now for GTC orders)
        if time_in_force == "GTC":
            expiration = int(time.time()) + (30 * 24 * 60 * 60)
        else:
            expiration = int(time.time()) + 300  # 5 minutes for IOC/FOK
        
        # Get wallet address and derive subaccount using the SDK utility
        wallet_address = self.client.context.signer.address
        subaccount_hex = subaccount_to_hex(wallet_address, self.subaccount_name)

        # Create OrderParams object
        # Note: nonce is set to None to let the SDK auto-generate it with proper recv_time buffer
        order_params = OrderParams(
            sender=subaccount_hex,
            priceX18=price_x18,
            amount=amount_x18,
            expiration=expiration,
            nonce=None,  # SDK will auto-generate with 90-second recv_time buffer
            appendix=appendix
        )

        # Create PlaceOrderParams object
        place_order_params = PlaceOrderParams(
            product_id=product_id,
            order=order_params
        )

        # Place order using SDK
        try:
            result = self.client.market.place_order(params=place_order_params)

            # Extract digest from the response
            digest = result.data.digest if result.data else 'unknown'

            order_info = {
                'success': True,
                'order_id': digest,
                'product_id': product_id,
                'side': side.value,
                'price': price,
                'size': size,
                'status': result.status,
                'timestamp': time.time()
            }

            # Track this order locally until indexer picks it up
            self._pending_orders[digest] = {
                'digest': digest,
                'product_id': product_id,
                'price': price,
                'amount': size if side == OrderSide.BUY else -size,
                'filled': 0,
                'side': side.value,
                'timestamp': time.time(),
                'local': True  # Mark as locally tracked
            }

            print(f"✓ Order placed: {side.value.upper()} {size} @ ${price}")
            return order_info
            
        except Exception as e:
            print(f"✗ Error placing order: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'product_id': product_id,
                'side': side.value,
                'price': price,
                'size': size
            }
    
    async def cancel_order(self, product_id: int, order_digest: str) -> Dict[str, Any]:
        """
        Cancel a specific order.

        Args:
            product_id: Product ID of the order
            order_digest: Order digest (ID) to cancel

        Returns:
            Cancellation result
        """
        self._ensure_connected()

        # Get wallet address and derive subaccount
        wallet_address = self.client.context.signer.address
        subaccount_hex = subaccount_to_hex(wallet_address, self.subaccount_name)

        try:
            # Create CancelOrdersParams object
            cancel_params = CancelOrdersParams(
                sender=subaccount_hex,
                productIds=[product_id],
                digests=[order_digest],
                nonce=None  # Will be auto-generated
            )

            result = self.client.market.cancel_orders(params=cancel_params)

            # Remove from pending orders if it was locally tracked
            if order_digest in self._pending_orders:
                del self._pending_orders[order_digest]

            return {
                'success': True,
                'cancelled': result,
                'order_digest': order_digest
            }
        except Exception as e:
            print(f"✗ Error cancelling order: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'order_digest': order_digest
            }
    
    async def cancel_all_orders(self, product_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Cancel all orders for a product or all products.

        Args:
            product_id: Product ID to cancel orders for (None = all products)

        Returns:
            Cancellation result
        """
        self._ensure_connected()

        # Get wallet address and derive subaccount
        wallet_address = self.client.context.signer.address
        subaccount_hex = subaccount_to_hex(wallet_address, self.subaccount_name)

        try:
            if product_id is not None:
                # Create CancelProductOrdersParams object
                cancel_params = CancelProductOrdersParams(
                    sender=subaccount_hex,
                    productIds=[product_id],
                    nonce=None  # Will be auto-generated
                )
                result = self.client.market.cancel_product_orders(params=cancel_params)
                message = f"✓ Cancelled all orders for product {product_id}"

                # Remove pending orders for this product
                digests_to_remove = [
                    digest for digest, order in self._pending_orders.items()
                    if order['product_id'] == product_id
                ]
                for digest in digests_to_remove:
                    del self._pending_orders[digest]
            else:
                # Cancel for all perpetual products
                results = []
                for product in self._products_cache['perp']:
                    cancel_params = CancelProductOrdersParams(
                        sender=subaccount_hex,
                        productIds=[product.product_id],
                        nonce=None  # Will be auto-generated
                    )
                    r = self.client.market.cancel_product_orders(params=cancel_params)
                    results.append(r)
                result = results
                message = "✓ Cancelled all orders for all products"

                # Clear all pending orders
                self._pending_orders.clear()

            print(message)
            return {
                'success': True,
                'result': result
            }
        except Exception as e:
            print(f"✗ Error cancelling orders: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_order_by_digest(self, order_digest: str) -> Optional[Dict[str, Any]]:
        """
        Get order details by digest.

        Args:
            order_digest: Order digest (ID) to query

        Returns:
            Order details if found, None otherwise
        """
        self._ensure_connected()

        try:
            orders_result = self.client.context.indexer_client.get_historical_orders_by_digest(
                digests=[order_digest]
            )

            if orders_result.orders and len(orders_result.orders) > 0:
                order = orders_result.orders[0]
                return {
                    'digest': order.digest,
                    'product_id': order.product_id,
                    'price': from_x18(order.price_x18),
                    'amount': from_x18(order.amount),
                    'base_filled': from_x18(order.base_filled),
                    'quote_filled': from_x18(order.quote_filled),
                    'side': 'buy' if float(order.amount) > 0 else 'sell',
                    'timestamp': order.timestamp
                }
            return None
        except Exception as e:
            print(f"⚠️  Error querying order {order_digest[:16]}...: {e}")
            return None

    async def get_open_orders(self, product_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders.

        Args:
            product_id: Filter by product ID (None = all products)

        Returns:
            List of open orders
        """
        self._ensure_connected()

        # Get wallet address and derive subaccount using the SDK utility
        wallet_address = self.client.context.signer.address
        subaccount_hex = subaccount_to_hex(wallet_address, self.subaccount_name)

        # Query open orders from engine (real-time, no lag)
        if product_id is not None:
            # Get orders for specific product
            # Returns SubaccountOpenOrdersData with .orders list
            orders_result = self.client.context.engine_client.get_subaccount_open_orders(
                product_id=product_id,
                sender=subaccount_hex
            )
            orders_list = orders_result.orders if hasattr(orders_result, 'orders') else []
        else:
            # Get orders for all perpetual products
            # Returns SubaccountMultiProductsOpenOrdersData with .product_orders list
            all_product_ids = [p.product_id for p in self._products_cache['perp']]
            orders_result = self.client.context.engine_client.get_subaccount_multi_products_open_orders(
                product_ids=all_product_ids,
                sender=subaccount_hex
            )

            # Multi-products returns SubaccountMultiProductsOpenOrdersData with .product_orders
            # Each ProductOpenOrdersData contains product_id and orders list
            orders_list = []
            if hasattr(orders_result, 'product_orders'):
                for product_orders in orders_result.product_orders:
                    if hasattr(product_orders, 'orders'):
                        orders_list.extend(product_orders.orders)

        open_orders = []

        # Parse orders from engine response
        for order in orders_list:
            try:
                # Convert amount to float for side determination
                amount = from_x18(order.amount)

                # Engine returns OrderData objects with:
                # - price_x18: price in x18 format
                # - amount: order amount (positive=buy, negative=sell)
                # - unfilled_amount: remaining unfilled amount
                # - digest: order ID
                # - placed_at: timestamp when order was placed
                open_orders.append({
                    'digest': order.digest,
                    'product_id': order.product_id,
                    'price': from_x18(order.price_x18),
                    'amount': amount,
                    'unfilled_amount': from_x18(order.unfilled_amount) if hasattr(order, 'unfilled_amount') else abs(amount),
                    'side': 'buy' if amount > 0 else 'sell',
                    'placed_at': order.placed_at if hasattr(order, 'placed_at') else None,
                    'expiration': order.expiration if hasattr(order, 'expiration') else None
                })
            except Exception as e:
                # If we can't parse the order, skip it
                print(f"⚠️  Skipping order: {e}")
                continue

        return open_orders
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions.

        Returns:
            List of positions with details
        """
        account_info = await self.get_account_info()

        # Get valid perpetual product IDs
        valid_product_ids = {p.product_id for p in self._products_cache['perp']}

        positions = []
        for balance in account_info['balances']:
            # Only show positions for active perpetual products with non-zero balance
            if (balance['product_id'] in valid_product_ids and
                balance['balance'] != 0):
                positions.append({
                    'product_id': balance['product_id'],
                    'size': balance['balance'],
                    'unrealized_pnl': balance['unrealized_pnl'],
                    'side': 'long' if balance['balance'] > 0 else 'short'
                })

        return positions
    
    async def get_funding_rate(self, product_id: int) -> Dict[str, Any]:
        """
        Get the current funding rate for a perpetual product.

        Args:
            product_id: Product ID (e.g., 2 for BTC-PERP)

        Returns:
            Dictionary with funding rate details
        """
        self._ensure_connected()

        result = self.client.context.indexer_client.get_perp_funding_rate(product_id)

        funding_rate = from_x18(int(result.funding_rate_x18))

        return {
            'product_id': result.product_id,
            'funding_rate': funding_rate,
            'update_time': result.update_time
        }

    async def get_orderbook(self, product_id: int, depth: int = 10) -> Dict[str, Any]:
        """
        Get orderbook for a product.
        
        Args:
            product_id: Product ID
            depth: Number of price levels to retrieve
            
        Returns:
            Orderbook with bids and asks
        """
        self._ensure_connected()
        
        orderbook = self.client.market.get_market_depth(
            product_id=product_id,
            depth=depth
        )
        
        return {
            'product_id': product_id,
            'bids': [
                {'price': from_x18(b.price_x18), 'size': from_x18(b.size_x18)}
                for b in orderbook.bids[:depth]
            ],
            'asks': [
                {'price': from_x18(a.price_x18), 'size': from_x18(a.size_x18)}
                for a in orderbook.asks[:depth]
            ],
            'timestamp': time.time()
        }
    
    def _ensure_connected(self):
        """Ensure client is connected."""
        if not self.client:
            raise RuntimeError("Not connected to Nado. Call connect() first.")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# Example usage
async def main():
    """Example usage of the Nado trading module."""
    
    # Try to import from config.py
    try:
        from config import PRIVATE_KEY, MODE
    except ImportError:
        print("⚠️  config.py not found. Please create it from config.example.py")
        import os
        PRIVATE_KEY = os.environ.get('NADO_PRIVATE_KEY', 'your_private_key_here')
        MODE = os.environ.get('NADO_MODE', 'mainnet')
    
    if PRIVATE_KEY == 'your_private_key_here':
        print("⚠️  Please set your private key in config.py")
        return
    
    # Using async context manager
    async with NadoTrader(PRIVATE_KEY, mode=MODE) as trader:

        # Get available products (for symbol lookup)
        products = trader.get_perpetual_products()
        product_map = {p['product_id']: p['symbol'] for p in products}

        # Display all available products
        print(f"\n📊 Available Products: {len(products)}")
        for p in products:
            price_str = f"${p['price']:>10,.2f}" if p['price'] else "N/A".rjust(10)
            print(f"  ID: {p['product_id']:2d} | {p['symbol']:8s} | Price: {price_str}")

        # Example: Place a buy limit order (LONG)
        # buy_order = await trader.buy_limit(
        #     product_id=8,      # SOL-PERP
        #     price=86.0,        # Buy at $85
        #     size=1.8,          # Size: 1.8 SOL
        #     post_only=True     # Only maker (won't execute immediately)
        # )

        # Example: Place a sell limit order (SHORT)
        # sell_order = await trader.sell_limit(
        #     product_id=8,      # SOL-PERP
        #     price=89.0,        # Sell at $90
        #     size=1.8,          # Size: 1.8 SOL
        #     post_only=True     # Only maker (won't execute immediately)
        # )

        # Wait a moment for orders to be placed
        await asyncio.sleep(1)

        # Get all open orders
        open_orders = await trader.get_open_orders()

        print(f"\n📋 Open Orders: {len(open_orders)}")
        if len(open_orders) == 0:
            print("  No open orders")
        else:
            for order in open_orders:
                size = abs(float(order['amount']))
                unfilled = float(order.get('unfilled_amount', size))
                price = float(order['price'])
                order_value = unfilled * price
                market = product_map.get(order['product_id'], f"Product {order['product_id']}")
                print(f"  {market:8s} | {order['side'].upper():4s} | Size: {size:>8.4f} | Unfilled: {unfilled:>8.4f} | Price: ${price:>8.2f} | Value: ${order_value:>10.2f}")

        # Get all open positions
        positions = await trader.get_positions()

        print(f"\n📊 Open Positions: {len(positions)}")
        if len(positions) == 0:
            print("  No open positions")
        else:
            for pos in positions:
                market = product_map.get(pos['product_id'], f"Product {pos['product_id']}")
                size = abs(pos['size'])
                pnl = pos['unrealized_pnl']
                pnl_str = f"${pnl:>10.2f}" if pnl != 0 else "$      0.00"
                print(f"  {market:8s} | {pos['side'].upper():5s} | Size: {size:>10.4f} | Unrealized PnL: {pnl_str}")

        # Cancel all orders
        # await trader.cancel_all_orders(product_id=8)
        


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
