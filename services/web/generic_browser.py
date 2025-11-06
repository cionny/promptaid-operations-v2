"""
Generic Browser Manager Implementation

This module provides a generic, configurable browser manager that can be
used with different website configurations. It separates browser lifecycle
management from site-specific logic.

Features:
- Configurable browser settings (locale, viewport, timeouts)
- Retry logic with exponential backoff
- Rate limiting support
- Context management for multiple sessions
- Resource cleanup and error recovery

Usage:
    config = BrowserConfig(locale="it-IT", timezone_id="Europe/Rome")
    manager = GenericBrowserManager(config)
    context = await manager.get_context("my_session")
    page = await context.new_page()
    success = await manager.navigate_with_retry(page, "https://example.com")
"""

import asyncio
import time
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from .base import IBrowserManager, BrowserConfig, NavigationError


class GenericBrowserManager(IBrowserManager):
    """Generic browser manager with configurable behavior"""
    
    def __init__(self, config: BrowserConfig):
        self.config = config
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.contexts: Dict[str, BrowserContext] = {}
        
    async def initialize(self):
        """Initialize Playwright and browser if not already done"""
        if self.playwright is None:
            self.playwright = await async_playwright().start()
            
        if self.browser is None:
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.headless,
                args=self.config.browser_args
            )
            
    async def get_context(self, context_id: str = "default") -> BrowserContext:
        """Get or create a browser context with configuration settings"""
        await self.initialize()
        
        if context_id not in self.contexts:
            self.contexts[context_id] = await self.browser.new_context(
                viewport=self.config.viewport,
                locale=self.config.locale,
                timezone_id=self.config.timezone_id,
                user_agent=self.config.user_agent,
                extra_http_headers=self.config.extra_headers
            )
            
            # Set timeouts
            self.contexts[context_id].set_default_timeout(self.config.default_timeout)
            self.contexts[context_id].set_default_navigation_timeout(self.config.navigation_timeout)
            
        return self.contexts[context_id]
        
    async def navigate_with_retry(self, page: Page, url: str, max_retries: int = 3) -> bool:
        """Navigate to URL with configurable retry logic"""
        for attempt in range(max_retries):
            try:
                print(f"🌐 Navigating to {url} (attempt {attempt + 1}/{max_retries})")
                
                await page.goto(url, wait_until="networkidle")
                
                # Basic success check - page loaded without error
                title = await page.title()
                if title and "error" not in title.lower():
                    print(f"✅ Successfully loaded page: {title}")
                    return True
                    
            except Exception as e:
                print(f"⚠️  Navigation attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    print(f"🔄 Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    
        print(f"❌ Failed to navigate to {url} after {max_retries} attempts")
        raise NavigationError(f"Failed to navigate to {url} after {max_retries} attempts")
        
    async def apply_rate_limiting(self, delay_ms: Optional[int] = None):
        """Apply rate limiting delay"""
        delay = delay_ms if delay_ms is not None else self.config.rate_limit_ms
        await asyncio.sleep(delay / 1000.0)
        
    async def close_context(self, context_id: str = "default"):
        """Close a specific browser context"""
        if context_id in self.contexts:
            await self.contexts[context_id].close()
            del self.contexts[context_id]
            print(f"🔒 Closed browser context: {context_id}")
            
    async def close_all(self):
        """Close all browser resources"""
        # Close all contexts
        for context_id in list(self.contexts.keys()):
            await self.close_context(context_id)
            
        # Close browser
        if self.browser:
            await self.browser.close()
            self.browser = None
            print("🔒 Closed browser")
            
        # Stop playwright
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
            print("🔒 Stopped Playwright")


# Factory function for easy instantiation
def create_browser_manager(config: BrowserConfig) -> GenericBrowserManager:
    """Factory function to create a browser manager with configuration"""
    return GenericBrowserManager(config)
