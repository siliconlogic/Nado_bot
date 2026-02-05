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

# Alternative: Load from environment variable
# Uncomment the lines below to use environment variables instead:
"""
import os
PRIVATE_KEY = os.environ.get('NADO_PRIVATE_KEY', 'your_private_key_here')
MODE = os.environ.get('NADO_MODE', 'mainnet')
"""
