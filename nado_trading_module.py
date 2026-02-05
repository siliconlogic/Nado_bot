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
        
    async def connect(self):
        """Initialize connection to Nado exchange."""
        if not self.client:
            self.client = create_nado_client(
                self.mode,
                self.private_key
            )
            print(f"✓ Connected to Nado ({self.mode.value})")
            print(f"  Using subaccount: {self.subaccount_name}")
            
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
        print(f"✓ Loaded {len(products.perp_products)} perpetual products")
    
    def get_perpetual_products(self) -> List[Dict[str, Any]]:
        """
        Get list of available perpetual products.
        
        Returns:
            List of perpetual products with their details
        """
        if not self._products_cache:
            raise RuntimeError("Not connected. Call connect() first.")
        
        return [
            {
                'product_id': p.product_id,
                'symbol': getattr(p, 'symbol', f'PERP-{p.product_id}'),
                'oracle_price_x18': getattr(p, 'oracle_price_x18', None),
                'price': from_x18(p.oracle_price_x18) if hasattr(p, 'oracle_price_x18') and p.oracle_price_x18 else None
            }
            for p in self._products_cache['perp']
        ]
    
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
        
        return {
            'subaccount': subaccount_hex,
            'health': info.healths if hasattr(info, 'healths') else None,
            'balances': [
                {
                    'product_id': b.product_id,
                    'balance': from_x18(b.balance.amount),
                    'unrealized_pnl': from_x18(b.balance.unrealized_pnl) if hasattr(b.balance, 'unrealized_pnl') else 0
                }
                for b in info.spot_balances + info.perp_balances
            ]
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
        
        # Generate nonce (timestamp in microseconds + random bits)
        nonce = int(time.time() * 1_000_000)
        
        # Calculate expiration (30 days from now for GTC orders)
        if time_in_force == "GTC":
            expiration = int(time.time()) + (30 * 24 * 60 * 60)
        else:
            expiration = int(time.time()) + 300  # 5 minutes for IOC/FOK
        
        # Place order using SDK
        try:
            result = self.client.market.place_order(
                product_id=product_id,
                price_x18=str(price_x18),
                amount_x18=str(amount_x18),
                expiration=expiration,
                nonce=nonce,
                appendix=appendix
            )
            
            order_info = {
                'success': True,
                'order_id': result.get('digest', 'unknown'),
                'product_id': product_id,
                'side': side.value,
                'price': price,
                'size': size,
                'status': result.get('status', 'submitted'),
                'timestamp': time.time()
            }
            
            print(f"✓ {side.value.upper()} limit order placed: {size} @ {price}")
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
        
        try:
            result = self.client.market.cancel_orders(
                product_ids=[product_id],
                digests=[order_digest]
            )
            
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
        
        try:
            if product_id is not None:
                result = self.client.market.cancel_product_orders(
                    product_id=product_id
                )
                message = f"✓ Cancelled all orders for product {product_id}"
            else:
                # Cancel for all perpetual products
                results = []
                for product in self._products_cache['perp']:
                    r = self.client.market.cancel_product_orders(
                        product_id=product.product_id
                    )
                    results.append(r)
                result = results
                message = "✓ Cancelled all orders for all products"
            
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
        
        # Query orders from indexer
        orders_result = self.client.context.indexer_client.get_subaccount_orders(
            subaccount=subaccount_hex,
            product_id=product_id
        )
        
        open_orders = []
        for order in orders_result.orders:
            if order.status == 'open':
                open_orders.append({
                    'digest': order.digest,
                    'product_id': order.product_id,
                    'price': from_x18(order.price_x18),
                    'amount': from_x18(order.amount),
                    'side': 'buy' if float(from_x18(order.amount)) > 0 else 'sell',
                    'timestamp': order.timestamp,
                    'status': order.status
                })
        
        return open_orders
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions.
        
        Returns:
            List of positions with details
        """
        account_info = await self.get_account_info()
        
        positions = []
        for balance in account_info['balances']:
            # Perpetual positions have non-zero balance
            if balance['product_id'] > 0 and balance['balance'] != 0:
                positions.append({
                    'product_id': balance['product_id'],
                    'size': balance['balance'],
                    'unrealized_pnl': balance['unrealized_pnl'],
                    'side': 'long' if balance['balance'] > 0 else 'short'
                })
        
        return positions
    
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
        
        # Get available products
        products = trader.get_perpetual_products()
        print("\nAvailable Perpetuals:")
        for p in products[:5]:  # Show first 5
            print(f"  Product {p['product_id']}: {p['symbol']} - Price: {p['price']}")
        
        # Get account info
        account = await trader.get_account_info()
        print(f"\nAccount Health: {account['health']}")
        print(f"Subaccount: {account['subaccount']}")
        
        # Example: Place a buy limit order for BTC-PERP (product_id=1)
        # Uncomment to actually place orders:
        """
        buy_order = await trader.buy_limit(
            product_id=1,
            price=45000.0,
            size=0.01,
            post_only=True
        )
        print(f"\nBuy Order Result: {buy_order}")
        
        # Place a sell limit order
        sell_order = await trader.sell_limit(
            product_id=1,
            price=46000.0,
            size=0.01,
            post_only=True
        )
        print(f"\nSell Order Result: {sell_order}")
        
        # Get open orders
        open_orders = await trader.get_open_orders(product_id=1)
        print(f"\nOpen Orders: {len(open_orders)}")
        for order in open_orders:
            print(f"  {order['side'].upper()} {order['amount']} @ {order['price']}")
        
        # Get positions
        positions = await trader.get_positions()
        print(f"\nPositions: {len(positions)}")
        for pos in positions:
            print(f"  Product {pos['product_id']}: {pos['side']} {pos['size']}")
        
        # Cancel all orders
        await trader.cancel_all_orders(product_id=1)
        """


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
