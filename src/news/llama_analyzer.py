"""
Llama Model Analyzer
Integrates with locally running Llama model for news analysis.

Supports:
- Ollama (recommended for local deployment)
- llama.cpp server
- vLLM server

THREAD SAFETY: Lock-free design using atomic Counter for statistics
"""

import asyncio
import aiohttp
import json
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time
from .models import (
    NewsItem, NewsAnalysis, NewsImpactLevel, 
    NewsSentiment
)

logger = setup_logger("llama_analyzer")


# Stock and Industry mappings for Indian market
INDUSTRY_KEYWORDS = {
    "banking": ["bank", "banking", "npa", "credit", "loan", "rbi", "nbfc", "deposit", "interest rate"],
    "auto": ["auto", "vehicle", "car", "ev", "electric vehicle", "automobile", "scooter", "bike", "two-wheeler"],
    "it": ["software", "tech", "it", "digital", "saas", "infosys", "tcs", "wipro", "technology"],
    "pharma": ["pharma", "drug", "fda", "medicine", "hospital", "healthcare", "biotech"],
    "aviation": ["aviation", "airline", "aircraft", "airport", "indigo", "spicejet", "air india"],
    "oil_gas": ["oil", "gas", "petroleum", "ongc", "reliance", "fuel", "crude", "petrol", "diesel"],
    "metal": ["steel", "metal", "iron", "aluminium", "copper", "tata steel", "mining", "zinc"],
    "fmcg": ["fmcg", "consumer", "food", "beverage", "hindustan unilever", "itc", "nestle"],
    "telecom": ["telecom", "5g", "airtel", "jio", "vodafone", "spectrum", "mobile", "telecom"],
    "realty": ["real estate", "realty", "housing", "property", "dlf", "godrej", "construction"],
    "agriculture": ["agriculture", "farm", "crop", "fertilizer", "monsoon", "kharif", "rabi", "agri"],
    "sme": ["sme", "small business", "msme", "startup", "entrepreneur"],
    "infrastructure": ["infra", "infrastructure", "road", "highway", "metro", "railway"],
    "power": ["power", "electricity", "solar", "renewable", "energy", "thermal", "wind"],
    "insurance": ["insurance", "life insurance", "general insurance", "lic", "icici prudential"],
}

# Major stock symbols for entity extraction - NSE symbols
MAJOR_STOCKS = {
    # Banking
    "HDFCBANK": ["hdfc bank", "hdfcbank", "hdfc"],
    "ICICIBANK": ["icici bank", "icicibank", "icici"],
    "SBIN": ["sbi", "state bank", "sbin", "state bank of india"],
    "AXISBANK": ["axis bank", "axisbank", "axis"],
    "KOTAKBANK": ["kotak", "kotakbank", "kotak mahindra"],
    "INDUSINDBK": ["indusind", "indusind bank"],
    "BANDHANBNK": ["bandhan", "bandhan bank"],
    "FEDERALBNK": ["federal bank", "federal"],
    "IDFCFIRSTB": ["idfc first", "idfc"],
    "PNB": ["pnb", "punjab national"],
    "BANKBARODA": ["bank of baroda", "bob"],
    "CANBK": ["canara bank"],
    
    # IT
    "TCS": ["tcs", "tata consultancy"],
    "INFY": ["infosys", "infy"],
    "WIPRO": ["wipro"],
    "HCLTECH": ["hcl tech", "hcltech", "hcl technologies"],
    "TECHM": ["tech mahindra", "techm"],
    "LTIM": ["ltimindtree", "ltim", "l&t infotech"],
    "MPHASIS": ["mphasis"],
    "COFORGE": ["coforge"],
    
    # Auto
    "TATAMOTORS": ["tata motors", "tatamotors", "tata motor"],
    "MARUTI": ["maruti", "maruti suzuki"],
    "M&M": ["mahindra", "m&m", "mahindra & mahindra"],
    "BAJAJ-AUTO": ["bajaj auto", "bajaj-auto"],
    "HEROMOTOCO": ["hero motocorp", "heromotoco", "hero"],
    "EICHERMOT": ["eicher", "royal enfield"],
    "ASHOKLEY": ["ashok leyland", "ashokley"],
    "TVSMOTOR": ["tvs motor", "tvs"],
    
    # Oil & Gas
    "RELIANCE": ["reliance", "ril", "reliance industries"],
    "ONGC": ["ongc", "oil and natural gas"],
    "IOC": ["indian oil", "ioc", "iocl"],
    "BPCL": ["bpcl", "bharat petroleum"],
    "HINDPETRO": ["hpcl", "hindustan petroleum"],
    "GAIL": ["gail", "gail india"],
    
    # Pharma
    "SUNPHARMA": ["sun pharma", "sunpharma", "sun pharmaceutical"],
    "DRREDDY": ["dr reddy", "drreddy", "dr. reddy"],
    "CIPLA": ["cipla"],
    "DIVISLAB": ["divis lab", "divislab", "divi's"],
    "LUPIN": ["lupin"],
    "AUROPHARMA": ["aurobindo", "auropharma"],
    "BIOCON": ["biocon"],
    
    # Aviation
    "INDIGO": ["indigo", "interglobe"],
    "SPICEJET": ["spicejet"],
    
    # Metals
    "TATASTEEL": ["tata steel", "tatasteel"],
    "JSWSTEEL": ["jsw steel", "jswsteel"],
    "HINDALCO": ["hindalco", "hindalco industries"],
    "VEDL": ["vedanta", "vedl"],
    "COALINDIA": ["coal india", "coalindia"],
    "NMDC": ["nmdc"],
    
    # FMCG
    "HINDUNILVR": ["hindustan unilever", "hul", "hindunilvr"],
    "ITC": ["itc"],
    "NESTLEIND": ["nestle", "nestleind", "nestle india"],
    "BRITANNIA": ["britannia"],
    "DABUR": ["dabur"],
    "MARICO": ["marico"],
    "GODREJCP": ["godrej consumer", "godrejcp"],
    "COLPAL": ["colgate", "colpal"],
    
    # Telecom
    "BHARTIARTL": ["airtel", "bharti airtel", "bhartiartl"],
    "IDEA": ["vodafone idea", "vi", "idea"],
    
    # Power
    "NTPC": ["ntpc"],
    "POWERGRID": ["power grid", "powergrid"],
    "ADANIGREEN": ["adani green", "adanigreen"],
    "TATAPOWER": ["tata power", "tatapower"],
    "ADANIPOWER": ["adani power", "adanipower"],
    
    # Infrastructure
    "LT": ["l&t", "larsen", "larsen & toubro"],
    "ADANIENT": ["adani enterprises", "adanient"],
    "ADANIPORTS": ["adani ports", "adaniports"],
    
    # Realty
    "DLF": ["dlf"],
    "GODREJPROP": ["godrej properties", "godrejprop"],
    "OBEROIRLTY": ["oberoi realty", "oberoirlty"],
    
    # Insurance
    "SBILIFE": ["sbi life", "sbilife"],
    "HDFCLIFE": ["hdfc life", "hdfclife"],
    "ICICIPRULI": ["icici prudential", "icicipruli"],
    "LICI": ["lic", "lici", "life insurance corporation"],
    
    # Others
    "ZOMATO": ["zomato"],
    "PAYTM": ["paytm", "one97"],
    "NYKAA": ["nykaa", "fsn e-commerce"],
    "POLICYBZR": ["policybazaar", "pb fintech"],
}

# Index keywords
INDEX_KEYWORDS = {
    "NIFTY 50": ["nifty", "nifty 50", "nifty50"],
    "NIFTY BANK": ["bank nifty", "banknifty", "nifty bank"],
    "NIFTY IT": ["nifty it", "it index"],
    "NIFTY PHARMA": ["nifty pharma", "pharma index"],
    "NIFTY AUTO": ["nifty auto", "auto index"],
    "NIFTY METAL": ["nifty metal", "metal index"],
    "NIFTY FMCG": ["nifty fmcg", "fmcg index"],
    "NIFTY REALTY": ["nifty realty", "realty index"],
    "SENSEX": ["sensex", "bse sensex"],
}


class LlamaAnalyzer:
    """
    Analyzes news using locally running Llama model.
    
    Supports:
    - Ollama API (default, port 11434)
    - llama.cpp server
    - vLLM server
    - OpenAI-compatible APIs
    """
    
    def __init__(self,
                 base_url: str = "http://localhost:11434",
                 model_name: str = "llama3.2:latest",
                 timeout_seconds: int = 60,
                 max_concurrent: int = 3,
                 temperature: float = 0.3,
                 api_type: str = "ollama",
                 api_key: Optional[str] = None,
                 rate_limit_delay: float = 0.0):
        """
        Initialize Llama analyzer.
        
        Args:
            base_url: Ollama/llama.cpp server URL or Azure AI Foundry endpoint
            model_name: Model to use (e.g., "llama3.2:latest", "mistral", "DeepSeek-V3.2")
            timeout_seconds: Request timeout
            max_concurrent: Max parallel analysis requests
            temperature: LLM temperature (lower = more consistent)
            api_type: API type - "ollama", "openai", or "llamacpp"
            api_key: API key for authentication (required for Azure/OpenAI)
            rate_limit_delay: Delay in seconds between API calls (for rate limiting)
        """
        self.base_url = base_url.rstrip('/')
        self.model_name = model_name
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.temperature = temperature
        self.api_type = api_type
        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0
        
        # Atomic statistics (lock-free)
        self.stats = Counter({
            "analyses_completed": 0,
            "analyses_failed": 0,
            "fallback_used": 0,
            "total_processing_time_ms": 0,
        })
        
        logger.info(f"LlamaAnalyzer initialized with model {model_name} at {base_url} (api_type={api_type})")
    
    async def analyze_news(self, news_item: NewsItem) -> Optional[NewsAnalysis]:
        """
        Analyze a single news item for market impact.
        
        Args:
            news_item: NewsItem to analyze
            
        Returns:
            NewsAnalysis result or None if failed
        """
        start_time = get_current_time()
        
        async with self.semaphore:
            try:
                # Build the analysis prompt
                prompt = self._build_analysis_prompt(news_item)
                
                # Call Llama model
                response = await self._call_llama(prompt)
                
                # Parse the response
                analysis = self._parse_analysis_response(news_item, response)
                
                # Calculate processing time
                processing_time = (get_current_time() - start_time).total_seconds() * 1000
                analysis.processing_time_ms = processing_time
                
                self.stats["analyses_completed"] += 1
                self.stats["total_processing_time_ms"] += int(processing_time)
                
                logger.info(
                    f"Analyzed news {news_item.news_id[:8]}: "
                    f"impact={analysis.impact_level.value}, "
                    f"sentiment={analysis.sentiment.value}, "
                    f"stocks={analysis.affected_stocks}, "
                    f"time={processing_time:.0f}ms"
                )
                
                return analysis
                
            except Exception as e:
                self.stats["analyses_failed"] += 1
                logger.error(f"Failed to analyze news {news_item.news_id[:8]}: {e}")
                
                # Return fallback analysis instead of None
                try:
                    return self._fallback_analysis(news_item, str(e))
                except Exception:
                    return None
    
    async def analyze_batch(self, news_items: List[NewsItem]) -> List[NewsAnalysis]:
        """
        Analyze multiple news items in parallel.
        
        Args:
            news_items: List of NewsItem objects
            
        Returns:
            List of successful NewsAnalysis results
        """
        if not news_items:
            return []
        
        logger.info(f"Starting batch analysis of {len(news_items)} news items")
        
        tasks = [self.analyze_news(item) for item in news_items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful analyses
        analyses = []
        for i, result in enumerate(results):
            if isinstance(result, NewsAnalysis):
                analyses.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Batch analysis error for item {i}: {result}")
        
        logger.info(f"Batch analysis complete: {len(analyses)}/{len(news_items)} successful")
        return analyses
    
    def _build_analysis_prompt(self, news_item: NewsItem) -> str:
        """Build the analysis prompt for Llama."""
        
        # Build article content section
        content_section = f"NEWS DESCRIPTION: {news_item.description}"
        
        if news_item.raw_content:
            # Truncate if too long
            content = news_item.raw_content[:3000] if len(news_item.raw_content) > 3000 else news_item.raw_content
            content_section = f"""NEWS DESCRIPTION: {news_item.description}

FULL ARTICLE CONTENT:
{content}"""
            logger.debug(f"Using full article content ({len(content)} chars) for analysis")
        
        prompt = f"""You are a financial analyst specializing in Indian stock markets (NSE/BSE).
Analyze the following news article and provide a structured assessment of its market impact.

NEWS TITLE: {news_item.title}

{content_section}

SOURCE: {news_item.source_feed}
PUBLISHED: {news_item.published_date.strftime('%Y-%m-%d %H:%M IST')}

Provide your analysis in the following JSON format ONLY (no additional text):
{{
    "impact_level": "critical|high|medium|low|neutral",
    "sentiment": "very_bullish|bullish|neutral|bearish|very_bearish",
    "confidence_score": 0.0-1.0,
    "affected_industries": ["industry1", "industry2"],
    "affected_stocks": ["SYMBOL1", "SYMBOL2"],
    "affected_indices": ["NIFTY 50", "NIFTY BANK"],
    "expected_direction": "UP|DOWN|SIDEWAYS",
    "expected_move_pct": 0.0-10.0,
    "time_horizon": "immediate|intraday|short_term|medium_term",
    "analysis_summary": "Brief 1-2 sentence summary",
    "key_points": ["point1", "point2", "point3"]
}}

CRITICAL RULES FOR affected_stocks:
- ONLY include stocks that are EXPLICITLY MENTIONED BY NAME in the title or description
- DO NOT add generic sector representatives (e.g., don't add HDFCBANK just because news mentions "banking sector")
- DO NOT infer or assume stocks - if company name is not in the text, DO NOT include it
- If news says "Fino Payments Bank", only include stocks for Fino Payments, NOT other banks
- Leave affected_stocks EMPTY if no specific company names are mentioned
- Examples: "HDFC Bank" → ["HDFCBANK"], "Reliance Industries" → ["RELIANCE"], "banking sector" → []

OTHER GUIDELINES:
- Use UPPERCASE NSE symbols for stocks (e.g., HDFCBANK, RELIANCE, TCS)
- Be conservative with impact_level - only use "critical" for major events like RBI policy, earnings surprises, M&A
- confidence_score reflects your certainty in the analysis (0.0 = uncertain, 1.0 = very confident)
- expected_move_pct should be realistic for Indian markets (typically 0.5% to 3%)
- Focus on actionable insights for intraday/swing trading
- For neutral/general news, use impact_level "low" or "neutral"
- time_horizon: "immediate" (minutes), "intraday" (same day), "short_term" (1-5 days), "medium_term" (1-4 weeks)
"""
        return prompt
    
    async def _call_llama(self, prompt: str) -> str:
        """
        Call the Llama model API.
        
        Args:
            prompt: The analysis prompt
            
        Returns:
            Model response text
        """
        # Rate limiting: wait if needed
        if self.rate_limit_delay > 0:
            import time
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.rate_limit_delay:
                wait_time = self.rate_limit_delay - time_since_last
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            self.last_request_time = time.time()
        
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            if self.api_type == "ollama":
                return await self._call_ollama(session, prompt)
            elif self.api_type == "openai":
                return await self._call_openai_compatible(session, prompt)
            else:
                return await self._call_ollama(session, prompt)
    
    async def _call_ollama(self, session: aiohttp.ClientSession, prompt: str) -> str:
        """Call Ollama API."""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
                "top_p": 0.9,
            }
        }
        
        async with session.post(
            f"{self.base_url}/api/generate",
            json=payload
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Ollama API error {response.status}: {error_text}")
            
            result = await response.json()
            return result.get("response", "")
    
    async def _call_openai_compatible(self, session: aiohttp.ClientSession, prompt: str) -> str:
        """Call OpenAI-compatible API (e.g., vLLM, Azure AI Foundry, text-generation-inference)."""
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a financial analyst. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"}
        }
        
        # Prepare headers with API key if provided
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            # Azure uses 'api-key' header, OpenAI uses 'Authorization: Bearer'
            if "azure.com" in self.base_url:
                headers["api-key"] = self.api_key
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Determine endpoint URL
        # Azure AI Foundry uses /openai/v1/chat/completions (OpenAI-compatible)
        if "azure.com" in self.base_url:
            endpoint = f"{self.base_url}/openai/v1/chat/completions"
        else:
            endpoint = f"{self.base_url}/v1/chat/completions"
        
        # Debug logging
        logger.debug(f"Calling API endpoint: {endpoint}")
        logger.debug(f"Headers: {', '.join(headers.keys())}")
        
        async with session.post(
            endpoint,
            json=payload,
            headers=headers
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"API request failed - Status: {response.status}, Endpoint: {endpoint}, Error: {error_text}")
                raise Exception(f"OpenAI API error {response.status}: {error_text}")
            
            result = await response.json()
            return result["choices"][0]["message"]["content"]
    
    def _parse_analysis_response(self, news_item: NewsItem, response: str) -> NewsAnalysis:
        """
        Parse Llama response into NewsAnalysis object.
        
        Args:
            news_item: Original news item
            response: Llama model response
            
        Returns:
            NewsAnalysis object
        """
        try:
            # Clean response - extract JSON if wrapped in markdown
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            # Parse JSON response
            data = json.loads(response)
            
            # Validate and convert impact_level
            impact_str = data.get("impact_level", "neutral").lower()
            try:
                impact_level = NewsImpactLevel(impact_str)
            except ValueError:
                impact_level = NewsImpactLevel.NEUTRAL
            
            # Validate and convert sentiment
            sentiment_str = data.get("sentiment", "neutral").lower()
            try:
                sentiment = NewsSentiment(sentiment_str)
            except ValueError:
                sentiment = NewsSentiment.NEUTRAL
            
            # Normalize stock symbols to uppercase
            affected_stocks = [s.upper().strip() for s in data.get("affected_stocks", [])]
            
            # Filter valid stock symbols
            affected_stocks = [s for s in affected_stocks if s and len(s) <= 20]
            
            # VALIDATE: Verify stocks are actually mentioned in the news text
            affected_stocks = self._validate_mentioned_stocks(news_item, affected_stocks)
            
            return NewsAnalysis(
                news_id=news_item.news_id,
                impact_level=impact_level,
                sentiment=sentiment,
                confidence_score=min(1.0, max(0.0, float(data.get("confidence_score", 0.5)))),
                affected_industries=data.get("affected_industries", []),
                affected_stocks=affected_stocks,
                affected_indices=data.get("affected_indices", []),
                expected_direction=data.get("expected_direction", "SIDEWAYS").upper(),
                expected_move_pct=min(10.0, max(0.0, float(data.get("expected_move_pct", 0.0)))),
                time_horizon=data.get("time_horizon", "intraday"),
                analysis_summary=data.get("analysis_summary", ""),
                key_points=data.get("key_points", []),
                model_used=self.model_name,
                analysis_timestamp=get_current_time(),
                processing_time_ms=0  # Set by caller
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response, using fallback: {e}")
            self.stats["fallback_used"] += 1
            return self._fallback_analysis(news_item, response)
        except Exception as e:
            logger.warning(f"Error parsing analysis response: {e}")
            self.stats["fallback_used"] += 1
            return self._fallback_analysis(news_item, str(e))
    
    def _fallback_analysis(self, news_item: NewsItem, error_info: str = "") -> NewsAnalysis:
        """
        Fallback analysis using keyword extraction when LLM fails.
        
        Uses predefined keyword dictionaries to extract entities.
        """
        self.stats["fallback_used"] += 1
        
        # Combine title and description for analysis
        text = f"{news_item.title} {news_item.description}".lower()
        
        # Extract industries
        affected_industries = []
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                affected_industries.append(industry)
        
        # Extract stocks - only if explicitly mentioned
        affected_stocks = []
        for symbol, keywords in MAJOR_STOCKS.items():
            # Require at least one keyword to appear as a distinct word/phrase
            for kw in keywords:
                kw_lower = kw.lower()
                # Check if keyword appears as whole word (not substring)
                if f" {kw_lower} " in f" {text} " or text.startswith(kw_lower) or text.endswith(kw_lower):
                    affected_stocks.append(symbol)
                    break
        
        # Extract indices
        affected_indices = []
        for index, keywords in INDEX_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                affected_indices.append(index)
        
        # Basic sentiment detection
        sentiment = NewsSentiment.NEUTRAL
        bullish_words = ["growth", "profit", "surge", "rally", "gain", "rise", "up", "positive", "beat", "strong"]
        bearish_words = ["fall", "drop", "loss", "decline", "down", "negative", "miss", "weak", "crash", "plunge"]
        
        bullish_count = sum(1 for w in bullish_words if w in text)
        bearish_count = sum(1 for w in bearish_words if w in text)
        
        if bullish_count > bearish_count + 1:
            sentiment = NewsSentiment.BULLISH
        elif bearish_count > bullish_count + 1:
            sentiment = NewsSentiment.BEARISH
        
        # Determine direction based on sentiment
        if sentiment in [NewsSentiment.BULLISH, NewsSentiment.VERY_BULLISH]:
            direction = "UP"
        elif sentiment in [NewsSentiment.BEARISH, NewsSentiment.VERY_BEARISH]:
            direction = "DOWN"
        else:
            direction = "SIDEWAYS"
        
        return NewsAnalysis(
            news_id=news_item.news_id,
            impact_level=NewsImpactLevel.LOW,
            sentiment=sentiment,
            confidence_score=0.3,  # Low confidence for fallback
            affected_industries=affected_industries[:3],  # Limit to top 3
            affected_stocks=affected_stocks[:5],  # Limit to top 5
            affected_indices=affected_indices[:2],  # Limit to top 2
            expected_direction=direction,
            expected_move_pct=0.5 if affected_stocks else 0.0,
            time_horizon="intraday",
            analysis_summary=f"Keyword-based analysis (LLM unavailable: {error_info[:50]})",
            key_points=["Analysis based on keyword matching only", "Low confidence - verify manually"],
            model_used=f"{self.model_name} (fallback)",
            analysis_timestamp=get_current_time(),
            processing_time_ms=0
        )
    
    def _validate_mentioned_stocks(self, news_item: NewsItem, stocks: List[str]) -> List[str]:
        """
        Validate that extracted stocks are actually mentioned in the news text.
        Prevents false positives like HDFCBANK appearing in unrelated news.
        
        Args:
            news_item: The news item being analyzed
            stocks: List of stock symbols to validate
            
        Returns:
            Filtered list of stocks that are actually mentioned
        """
        if not stocks:
            return []
        
        # Combine title and description for checking
        text = f"{news_item.title} {news_item.description}".lower()
        
        validated_stocks = []
        for symbol in stocks:
            # Get the keywords for this stock
            if symbol not in MAJOR_STOCKS:
                continue
            
            keywords = MAJOR_STOCKS[symbol]
            
            # Check if any keyword for this stock appears in the text
            for kw in keywords:
                kw_lower = kw.lower()
                # Require keyword to appear as whole word/phrase, not substring
                if f" {kw_lower} " in f" {text} " or text.startswith(kw_lower) or text.endswith(kw_lower):
                    validated_stocks.append(symbol)
                    break
        
        # Log if stocks were filtered out
        if len(validated_stocks) < len(stocks):
            removed = set(stocks) - set(validated_stocks)
            logger.debug(
                f"Filtered out unmentioned stocks: {removed} from news: {news_item.title[:50]}..."
            )
        
        return validated_stocks
    
    async def check_health(self) -> bool:
        """
        Check if Llama server is healthy.
        
        Returns:
            True if server is responding, False otherwise
        """
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5)
            ) as session:
                if self.api_type == "ollama":
                    async with session.get(f"{self.base_url}/api/tags") as response:
                        return response.status == 200
                else:
                    async with session.get(f"{self.base_url}/v1/models") as response:
                        return response.status == 200
        except Exception as e:
            logger.warning(f"Llama health check failed: {e}")
            return False
    
    async def list_models(self) -> List[str]:
        """
        List available models on the server.
        
        Returns:
            List of model names
        """
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                if self.api_type == "ollama":
                    async with session.get(f"{self.base_url}/api/tags") as response:
                        if response.status == 200:
                            data = await response.json()
                            return [m["name"] for m in data.get("models", [])]
                return []
        except Exception as e:
            logger.warning(f"Failed to list models: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        stats = dict(self.stats)
        if stats["analyses_completed"] > 0:
            stats["avg_processing_time_ms"] = (
                stats["total_processing_time_ms"] / stats["analyses_completed"]
            )
        else:
            stats["avg_processing_time_ms"] = 0
        return stats
    
    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = Counter({
            "analyses_completed": 0,
            "analyses_failed": 0,
            "fallback_used": 0,
            "total_processing_time_ms": 0,
        })
