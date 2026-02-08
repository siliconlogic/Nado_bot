"""
Configuration Template for Nado Trading Bot
============================================
This is a template file. Copy this file to config.py and add your settings.

Steps to use:
1. Copy this file: cp config.example.py config.py
2. Edit config.py and add your private key
3. Never commit config.py to version control
"""

# Your Ethereum private key (with or without 0x prefix)
# Replace with your actual private key
PRIVATE_KEY = "your_private_key_here"

# Trading mode: "mainnet" or "testnet"
MODE = "mainnet"

# Subaccount name (optional, default is "default")
SUBACCOUNT_NAME = "default"

# ============================================
# Trading Order Settings
# ============================================

# Default product ID to trade (e.g., 8 for SOL-PERP, 2 for BTC-PERP, 4 for ETH-PERP)
DEFAULT_PRODUCT_ID = 8

# Default order size
DEFAULT_ORDER_SIZE = 1.0

# Order price offset from current market price (in USD)
# For buy orders: order will be placed at (market_price - PRICE_OFFSET_USD)
# For sell orders: order will be placed at (market_price + PRICE_OFFSET_USD)
PRICE_OFFSET_USD = 1.0

# Order settings
POST_ONLY = True  # Only maker orders (won't execute immediately)
REDUCE_ONLY = False  # Set to True to only reduce existing positions
TIME_IN_FORCE = "GTC"  # GTC (Good Till Cancel), IOC (Immediate or Cancel), FOK (Fill or Kill)

# Alternative: Load from environment variable
# Uncomment the lines below to use environment variables instead:
"""
import os
PRIVATE_KEY = os.environ.get('NADO_PRIVATE_KEY', 'your_private_key_here')
MODE = os.environ.get('NADO_MODE', 'mainnet')
"""
