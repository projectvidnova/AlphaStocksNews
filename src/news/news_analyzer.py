"""
News Analyzer Module
Analyzes financial news using LLM models for market impact assessment.

Supports multiple backends:
- Ollama (local deployment)
- OpenAI-compatible APIs (Azure AI, vLLM, etc.)

THREAD SAFETY: Lock-free design using atomic Counter for statistics
"""

import asyncio
import aiohttp
import json
import time
from collections import Counter
from typing import Dict, List, Optional, Any

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time
from .models import NewsItem, NewsAnalysis, NewsImpactLevel, NewsSentiment

logger = setup_logger("news_analyzer")


# ============================================================================
# F&O ELIGIBLE STOCKS - Complete NSE F&O Stock Mappings
# Last updated: January 2026
# ============================================================================

INDUSTRY_KEYWORDS = {
    "auto": [
        "auto", "automobile", "vehicle", "car", "ev", "electric vehicle",
        "scooter", "bike", "two-wheeler", "tyre", "tire", "auto components",
        "passenger vehicle", "commercial vehicle", "tractor"
    ],
    "banking_private": [
        "private bank", "bank", "banking", "npa", "credit", "loan", "deposit",
        "interest rate", "hdfc bank", "icici bank", "axis bank", "kotak"
    ],
    "banking_psu": [
        "psu bank", "public sector bank", "sbi", "pnb", "bank of baroda",
        "canara bank", "state bank", "government bank"
    ],
    "finance_nbfc": [
        "nbfc", "housing finance", "consumer finance", "gold loan", "microfinance",
        "asset management", "mutual fund", "amc", "wealth management", "fintech"
    ],
    "finance_insurance": [
        "insurance", "life insurance", "general insurance", "lic", "health insurance",
        "motor insurance", "premium", "underwriting"
    ],
    "finance_capital_markets": [
        "stock exchange", "bse", "nse", "depository", "cdsl", "nsdl", "brokerage",
        "commodity exchange", "mcx", "trading platform"
    ],
    "cement": [
        "cement", "construction materials", "concrete", "clinker", "ultratech",
        "ambuja", "acc", "shree cement"
    ],
    "chemicals": [
        "chemical", "specialty chemical", "agrochemical", "fluorine", "dye",
        "pigment", "adhesive", "industrial chemical"
    ],
    "fertilizers": [
        "fertilizer", "urea", "dap", "npk", "potash", "phosphate", "agri input"
    ],
    "fmcg": [
        "fmcg", "consumer goods", "food", "beverage", "personal care", "home care",
        "packaged food", "dairy", "snacks", "hindustan unilever", "itc", "nestle"
    ],
    "consumer_durables": [
        "consumer durables", "appliances", "ac", "refrigerator", "washing machine",
        "electronics", "lighting", "fan", "wire", "cable"
    ],
    "retail": [
        "retail", "e-commerce", "online shopping", "dmart", "supermarket",
        "fashion retail", "jewellery", "quick commerce", "food delivery"
    ],
    "energy_oil_gas": [
        "oil", "gas", "petroleum", "refinery", "crude", "petrol", "diesel",
        "lng", "city gas", "pipeline", "exploration"
    ],
    "energy_power": [
        "power", "electricity", "thermal power", "hydro power", "power grid",
        "transmission", "distribution", "utility"
    ],
    "energy_renewable": [
        "renewable", "solar", "wind", "green energy", "clean energy",
        "solar panel", "wind turbine", "ev charging"
    ],
    "pharma": [
        "pharma", "pharmaceutical", "drug", "fda", "medicine", "generic",
        "api", "formulation", "clinical trial", "usfda"
    ],
    "healthcare": [
        "hospital", "healthcare", "diagnostic", "pathlab", "clinic",
        "medical devices", "health tech", "telemedicine"
    ],
    "capital_goods": [
        "capital goods", "heavy engineering", "industrial equipment", "turbine",
        "boiler", "transformer", "switchgear", "automation"
    ],
    "defence": [
        "defence", "defense", "aerospace", "shipyard", "missile", "radar",
        "military", "ammunition", "hal", "bhel"
    ],
    "it": [
        "software", "it", "information technology", "digital", "saas", "cloud",
        "cybersecurity", "data analytics", "ai", "artificial intelligence",
        "it services", "technology", "tech"
    ],
    "metals": [
        "steel", "metal", "iron", "aluminium", "aluminum", "copper", "zinc",
        "mining", "ore", "smelting", "foundry"
    ],
    "realty": [
        "real estate", "realty", "housing", "property", "residential",
        "commercial property", "builder", "developer", "township"
    ],
    "infrastructure": [
        "infra", "infrastructure", "road", "highway", "metro", "railway",
        "port", "airport", "construction", "epc"
    ],
    "telecom": [
        "telecom", "5g", "4g", "spectrum", "mobile", "broadband", "fiber",
        "tower", "data center", "isp"
    ],
    "media": [
        "media", "entertainment", "broadcasting", "television", "streaming",
        "ott", "cinema", "multiplex", "advertising"
    ],
    "travel_transport": [
        "aviation", "airline", "airport", "logistics", "shipping", "courier",
        "railway", "container", "freight", "travel", "tourism", "hotel"
    ],
    "food_delivery": [
        "food delivery", "quick commerce", "restaurant", "qsr", "food tech",
        "cloud kitchen", "swiggy", "zomato"
    ],
}

# F&O Stocks with keywords for entity extraction
MAJOR_STOCKS = {
    # Automobile & Auto Components (18 stocks)
    "ASHOKLEY": ["ashok leyland", "ashokley", "ashok"],
    "BAJAJ-AUTO": ["bajaj auto", "bajaj-auto", "bajaj"],
    "BALKRISIND": ["balkrishna industries", "balkrisind", "bkt", "balkrishna"],
    "BHARATFORG": ["bharat forge", "bharatforg"],
    "BOSCHLTD": ["bosch", "boschltd", "bosch india"],
    "EICHERMOT": ["eicher motors", "eichermot", "eicher", "royal enfield"],
    "ESCORTS": ["escorts kubota", "escorts", "kubota"],
    "EXIDEIND": ["exide industries", "exideind", "exide"],
    "HEROMOTOCO": ["hero motocorp", "heromotoco", "hero"],
    "M&M": ["mahindra", "m&m", "mahindra & mahindra", "mahindra and mahindra"],
    "MARUTI": ["maruti", "maruti suzuki", "msil"],
    "MRF": ["mrf", "mrf tyres", "mrf tires"],
    "MOTHERSON": ["motherson", "samvardhana motherson", "sona minda"],
    "SONACOMS": ["sona blw", "sonacoms", "sona comstar"],
    "TATAMOTORS": ["tata motors", "tatamotors", "tata motor"],
    "TIINDIA": ["tube investments", "tiindia", "ti india"],
    "TVSMOTOR": ["tvs motor", "tvsmotor", "tvs"],
    "UNOMINDA": ["uno minda", "unominda", "minda"],
    # Banking - Private (12 stocks)
    "AUBANK": ["au small finance", "aubank", "au bank"],
    "AXISBANK": ["axis bank", "axisbank", "axis"],
    "BANDHANBNK": ["bandhan bank", "bandhanbnk", "bandhan"],
    "CUB": ["city union bank", "cub"],
    "FEDERALBNK": ["federal bank", "federalbnk", "federal"],
    "HDFCBANK": ["hdfc bank", "hdfcbank", "hdfc"],
    "ICICIBANK": ["icici bank", "icicibank", "icici"],
    "IDFCFIRSTB": ["idfc first", "idfcfirstb", "idfc first bank", "idfc"],
    "INDUSINDBK": ["indusind bank", "indusindbk", "indusind"],
    "KOTAKBANK": ["kotak mahindra", "kotakbank", "kotak"],
    "RBLBANK": ["rbl bank", "rblbank", "rbl"],
    "YESBANK": ["yes bank", "yesbank"],
    # Banking - PSU (7 stocks)
    "BANKBARODA": ["bank of baroda", "bankbaroda", "bob"],
    "BANKINDIA": ["bank of india", "bankindia", "boi"],
    "CANBK": ["canara bank", "canbk", "canara"],
    "INDIANB": ["indian bank", "indianb"],
    "PNB": ["punjab national bank", "pnb", "punjab national"],
    "SBIN": ["state bank of india", "sbin", "sbi", "state bank"],
    "UNIONBANK": ["union bank of india", "unionbank", "union bank"],
    # Finance - NBFCs & Insurance (36 stocks)
    "360ONE": ["360 one", "360one", "360 one wam", "iifl wealth"],
    "ABCAPITAL": ["aditya birla capital", "abcapital", "ab capital"],
    "ANGELONE": ["angel one", "angelone", "angel broking"],
    "BAJFINANCE": ["bajaj finance", "bajfinance"],
    "BAJAJFINSV": ["bajaj finserv", "bajajfinsv"],
    "BAJAJHLDNG": ["bajaj holdings", "bajajhldng"],
    "BSE": ["bse", "bombay stock exchange"],
    "CANFINHOME": ["can fin homes", "canfinhome"],
    "CDSL": ["cdsl", "central depository"],
    "CHOLAFIN": ["cholamandalam", "cholafin", "chola finance"],
    "CAMS": ["cams", "computer age management"],
    "HDFCAMC": ["hdfc amc", "hdfcamc", "hdfc asset management"],
    "HDFCLIFE": ["hdfc life", "hdfclife"],
    "HUDCO": ["hudco", "housing urban development"],
    "ICICIGI": ["icici lombard", "icicigi", "icici general insurance"],
    "ICICIPRULI": ["icici prudential", "icicipruli", "icici pru life"],
    "IEX": ["indian energy exchange", "iex"],
    "IRFC": ["irfc", "indian railway finance"],
    "JIOFIN": ["jio financial", "jiofin", "jio finance"],
    "LTF": ["l&t finance", "ltf", "lt finance"],
    "LICHSGFIN": ["lic housing", "lichsgfin", "lic hfl"],
    "LICI": ["lic", "lici", "life insurance corporation"],
    "MANAPPURAM": ["manappuram", "manappuram finance"],
    "MFSL": ["max financial", "mfsl", "max life"],
    "MCX": ["mcx", "multi commodity exchange"],
    "MUTHOOTFIN": ["muthoot finance", "muthootfin", "muthoot"],
    "NAM-INDIA": ["nippon india", "nam-india", "nippon life amc"],
    "NUVAMA": ["nuvama", "nuvama wealth", "edelweiss wealth"],
    "PEL": ["piramal enterprises", "pel", "piramal"],
    "PNBHOUSING": ["pnb housing", "pnbhousing"],
    "PFC": ["power finance corporation", "pfc"],
    "RECLTD": ["rec", "recltd", "rural electrification"],
    "SAMMAANCAP": ["sammaan capital", "sammaancap", "indiabulls housing"],
    "SBICARD": ["sbi cards", "sbicard", "sbi card"],
    "SBILIFE": ["sbi life", "sbilife"],
    "SHRIRAMFIN": ["shriram finance", "shriramfin", "shriram transport"],
    # Cement & Construction Materials (9 stocks)
    "ACC": ["acc", "acc cement", "acc limited"],
    "AMBUJACEM": ["ambuja cements", "ambujacem", "ambuja"],
    "DALBHARAT": ["dalmia bharat", "dalbharat", "dalmia cement"],
    "GRASIM": ["grasim", "grasim industries"],
    "INDIACEM": ["india cements", "indiacem"],
    "JKCEMENT": ["jk cement", "jkcement"],
    "RAMCOCEM": ["ramco cements", "ramcocem", "ramco"],
    "SHREECEM": ["shree cement", "shreecem"],
    "ULTRACEMCO": ["ultratech", "ultracemco", "ultratech cement"],
    # Chemicals & Fertilizers (13 stocks)
    "AARTIIND": ["aarti industries", "aartiind", "aarti"],
    "ATUL": ["atul", "atul ltd"],
    "CHAMBLFERT": ["chambal fertilisers", "chamblfert", "chambal"],
    "COROMANDEL": ["coromandel international", "coromandel"],
    "DEEPAKNTR": ["deepak nitrite", "deepakntr"],
    "GNFC": ["gnfc", "gujarat narmada"],
    "NAVINFLUOR": ["navin fluorine", "navinfluor"],
    "PIIND": ["pi industries", "piind"],
    "PIDILITIND": ["pidilite", "pidilitind", "fevicol"],
    "SOLARINDS": ["solar industries", "solarinds"],
    "SRF": ["srf", "srf limited"],
    "TATACHEM": ["tata chemicals", "tatachem"],
    "UPL": ["upl", "upl limited"],
    # Consumer Goods - FMCG (14 stocks)
    "BALRAMCHIN": ["balrampur chini", "balramchin"],
    "BRITANNIA": ["britannia", "britannia industries"],
    "COLPAL": ["colgate", "colpal", "colgate palmolive"],
    "DABUR": ["dabur", "dabur india"],
    "GODREJCP": ["godrej consumer", "godrejcp", "gcpl"],
    "HINDUNILVR": ["hindustan unilever", "hindunilvr", "hul"],
    "ITC": ["itc", "itc limited"],
    "MARICO": ["marico"],
    "NESTLEIND": ["nestle india", "nestleind", "nestle"],
    "PATANJALI": ["patanjali foods", "patanjali", "ruchi soya"],
    "TATACONSUM": ["tata consumer", "tataconsum", "tata tea"],
    "UBL": ["united breweries", "ubl", "kingfisher beer"],
    "UNITDSPR": ["united spirits", "unitdspr", "diageo india"],
    "VBL": ["varun beverages", "vbl", "pepsi bottler"],
    # Consumer Durables & Retail (19 stocks)
    "ABFRL": ["aditya birla fashion", "abfrl", "pantaloons", "madura fashion"],
    "AMBER": ["amber enterprises", "amber"],
    "ASIANPAINT": ["asian paints", "asianpaint"],
    "DMART": ["dmart", "avenue supermarts", "avenue supermart"],
    "BATAINDIA": ["bata india", "bataindia", "bata"],
    "BERGEPAINT": ["berger paints", "bergepaint", "berger"],
    "BLUESTARCO": ["blue star", "bluestarco"],
    "CROMPTON": ["crompton greaves", "crompton"],
    "DIXON": ["dixon technologies", "dixon"],
    "HAVELLS": ["havells", "havells india"],
    "KALYANKJIL": ["kalyan jewellers", "kalyankjil", "kalyan"],
    "NYKAA": ["nykaa", "fsn e-commerce", "fsn"],
    "PAGEIND": ["page industries", "pageind", "jockey"],
    "POLYCAB": ["polycab", "polycab india"],
    "TITAN": ["titan", "titan company", "tanishq"],
    "TRENT": ["trent", "westside", "zudio"],
    "VOLTAS": ["voltas"],
    "WHIRLPOOL": ["whirlpool india", "whirlpool"],
    "ZOMATO": ["zomato", "eternal"],
    # Energy - Oil, Gas & Power (23 stocks)
    "ADANIENSOL": ["adani energy solutions", "adaniensol"],
    "ADANIGREEN": ["adani green", "adanigreen", "adani green energy"],
    "BPCL": ["bpcl", "bharat petroleum"],
    "COALINDIA": ["coal india", "coalindia", "cil"],
    "GAIL": ["gail", "gail india"],
    "GUJGASLTD": ["gujarat gas", "gujgasltd"],
    "HINDPETRO": ["hpcl", "hindpetro", "hindustan petroleum"],
    "IOC": ["indian oil", "ioc", "iocl"],
    "IGL": ["indraprastha gas", "igl"],
    "JSWENERGY": ["jsw energy", "jswenergy"],
    "MGL": ["mahanagar gas", "mgl"],
    "NHPC": ["nhpc", "nhpc limited"],
    "NTPC": ["ntpc", "ntpc limited"],
    "ONGC": ["ongc", "oil and natural gas"],
    "OIL": ["oil india", "oil"],
    "PETRONET": ["petronet lng", "petronet"],
    "POWERGRID": ["power grid", "powergrid", "pgcil"],
    "PREMIERENE": ["premier energies", "premierene"],
    "RELIANCE": ["reliance", "ril", "reliance industries"],
    "SUZLON": ["suzlon", "suzlon energy"],
    "TATAPOWER": ["tata power", "tatapower"],
    "TORNTPOWER": ["torrent power", "torntpower"],
    "WAAREEENER": ["waaree energies", "waareeener", "waaree"],
    # Healthcare & Pharma (22 stocks)
    "ALKEM": ["alkem", "alkem laboratories"],
    "APOLLOHOSP": ["apollo hospitals", "apollohosp", "apollo"],
    "AUROPHARMA": ["aurobindo pharma", "auropharma", "aurobindo"],
    "BIOCON": ["biocon"],
    "CIPLA": ["cipla"],
    "DIVISLAB": ["divis laboratories", "divislab", "divi's"],
    "LALPATHLAB": ["dr lal pathlabs", "lalpathlab", "lal path"],
    "DRREDDY": ["dr reddy's", "drreddy", "dr reddy"],
    "FORTIS": ["fortis healthcare", "fortis"],
    "GLENMARK": ["glenmark", "glenmark pharma"],
    "GRANULES": ["granules india", "granules"],
    "IPCALAB": ["ipca laboratories", "ipcalab", "ipca"],
    "LAURUSLABS": ["laurus labs", "lauruslabs", "laurus"],
    "LUPIN": ["lupin"],
    "MANKIND": ["mankind pharma", "mankind"],
    "MAXHEALTH": ["max healthcare", "maxhealth", "max hospital"],
    "METROPOLIS": ["metropolis healthcare", "metropolis"],
    "PPLPHARMA": ["piramal pharma", "pplpharma"],
    "SUNPHARMA": ["sun pharma", "sunpharma", "sun pharmaceutical"],
    "SYNGENE": ["syngene", "syngene international"],
    "TORNTPHARM": ["torrent pharma", "torntpharm", "torrent pharmaceuticals"],
    "ZYDUSLIFE": ["zydus lifesciences", "zyduslife", "zydus", "cadila"],
    # Capital Goods & Manufacturing (13 stocks)
    "ABB": ["abb india", "abb"],
    "ASTRAL": ["astral", "astral pipes"],
    "BEL": ["bharat electronics", "bel"],
    "BHEL": ["bharat heavy electricals", "bhel"],
    "CGPOWER": ["cg power", "cgpower", "crompton greaves power"],
    "CUMMINSIND": ["cummins india", "cumminsind", "cummins"],
    "HAL": ["hindustan aeronautics", "hal"],
    "POWERINDIA": ["hitachi energy", "powerindia", "abb power"],
    "KEI": ["kei industries", "kei"],
    "LT": ["l&t", "larsen & toubro", "larsen and toubro", "larsen"],
    "MAZDOCK": ["mazagon dock", "mazdock"],
    "SIEMENS": ["siemens", "siemens india"],
    "SUPREMEIND": ["supreme industries", "supremeind"],
    # Information Technology (18 stocks)
    "BSOFT": ["birlasoft", "bsoft"],
    "COFORGE": ["coforge"],
    "HCLTECH": ["hcl technologies", "hcltech", "hcl tech"],
    "INFY": ["infosys", "infy"],
    "KFINTECH": ["kfin technologies", "kfintech", "kfin"],
    "KPITTECH": ["kpit technologies", "kpittech", "kpit"],
    "LTTS": ["l&t technology services", "ltts"],
    "LTIM": ["ltimindtree", "ltim", "l&t infotech", "mindtree"],
    "MPHASIS": ["mphasis"],
    "OFSS": ["oracle financial", "ofss", "oracle fss"],
    "POLICYBZR": ["policybazaar", "policybzr", "pb fintech"],
    "PERSISTENT": ["persistent systems", "persistent"],
    "PAYTM": ["paytm", "one97", "one 97 communications"],
    "TCS": ["tcs", "tata consultancy services", "tata consultancy"],
    "TATAELXSI": ["tata elxsi", "tataelxsi"],
    "TATATECH": ["tata technologies", "tatatech"],
    "TECHM": ["tech mahindra", "techm"],
    "WIPRO": ["wipro"],
    # Metals & Mining (12 stocks)
    "ADANIENT": ["adani enterprises", "adanient"],
    "APLAPOLLO": ["apl apollo", "aplapollo", "apollo tubes"],
    "HINDALCO": ["hindalco", "hindalco industries"],
    "HINDCOPPER": ["hindustan copper", "hindcopper"],
    "HINDZINC": ["hindustan zinc", "hindzinc"],
    "JINDALSTEL": ["jindal steel", "jindalstel", "jspl"],
    "JSWSTEEL": ["jsw steel", "jswsteel"],
    "NATIONALUM": ["nalco", "nationalum", "national aluminium"],
    "NMDC": ["nmdc"],
    "SAIL": ["sail", "steel authority"],
    "TATASTEEL": ["tata steel", "tatasteel"],
    "VEDL": ["vedanta", "vedl"],
    # Realty & Infrastructure (9 stocks)
    "DLF": ["dlf"],
    "GMRAIRPORT": ["gmr airports", "gmrairport", "gmr infra"],
    "GODREJPROP": ["godrej properties", "godrejprop"],
    "LODHA": ["lodha", "macrotech", "macrotech developers"],
    "NBCC": ["nbcc", "nbcc india"],
    "OBEROIRLTY": ["oberoi realty", "oberoirlty", "oberoi"],
    "PRESTIGE": ["prestige estates", "prestige"],
    "RVNL": ["rvnl", "rail vikas nigam"],
    "PHOENIXLTD": ["phoenix mills", "phoenixltd", "phoenix"],
    # Telecom & Media (8 stocks)
    "BHARTIARTL": ["bharti airtel", "bhartiartl", "airtel"],
    "INDUSTOWER": ["indus towers", "industower"],
    "NAUKRI": ["naukri", "info edge"],
    "PVRINOX": ["pvr inox", "pvrinox", "pvr", "inox"],
    "SUNTV": ["sun tv", "suntv", "sun tv network"],
    "TATACOMM": ["tata communications", "tatacomm", "tata comm"],
    "IDEA": ["vodafone idea", "idea", "vi"],
    "ZEEL": ["zee entertainment", "zeel", "zee"],
    # Travel, Transport & Logistics (8 stocks)
    "ADANIPORTS": ["adani ports", "adaniports", "apsez"],
    "CONCOR": ["concor", "container corporation"],
    "DELHIVERY": ["delhivery"],
    "INDHOTEL": ["indian hotels", "indhotel", "taj hotels"],
    "IRCTC": ["irctc", "indian railway catering"],
    "INDIGO": ["indigo", "interglobe aviation"],
    "JUBLFOOD": ["jubilant foodworks", "jublfood", "dominos india"],
    "SWIGGY": ["swiggy"],
}

INDEX_KEYWORDS = {
    "NIFTY 50": ["nifty", "nifty 50", "nifty50"],
    "NIFTY BANK": ["bank nifty", "banknifty", "nifty bank"],
    "NIFTY IT": ["nifty it", "it index"],
    "NIFTY PHARMA": ["nifty pharma", "pharma index"],
    "NIFTY AUTO": ["nifty auto", "auto index"],
    "NIFTY METAL": ["nifty metal", "metal index"],
    "NIFTY FMCG": ["nifty fmcg", "fmcg index"],
    "NIFTY REALTY": ["nifty realty", "realty index"],
    "NIFTY FINANCIAL": ["nifty financial", "finnifty", "nifty fin service"],
    "NIFTY MIDCAP": ["nifty midcap", "midcap index"],
    "SENSEX": ["sensex", "bse sensex"],
}

class NewsAnalyzer:
    """
    Analyzes financial news for market impact using LLM models.

    Supports multiple backends:
    - Ollama (local, default port 11434)
    - OpenAI-compatible APIs (Azure AI, vLLM, etc.)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "llama3.2:latest",
        timeout_seconds: int = 60,
        max_concurrent: int = 3,
        temperature: float = 0.3,
        api_type: str = "ollama",
        api_key: Optional[str] = None,
        rate_limit_delay: float = 0.0,
    ):
        """
        Initialize the news analyzer.

        Args:
            base_url: LLM server URL
            model_name: Model identifier
            timeout_seconds: Request timeout
            max_concurrent: Max parallel requests
            temperature: LLM temperature (lower = more consistent)
            api_type: "ollama" or "openai"
            api_key: API key for authentication
            rate_limit_delay: Delay between API calls (seconds)
        """
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.temperature = temperature
        self.api_type = api_type
        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

        # Lock-free statistics
        self.stats = Counter({
            "analyses_completed": 0,
            "analyses_failed": 0,
            "fallback_used": 0,
            "total_processing_time_ms": 0,
        })

        logger.info(f"NewsAnalyzer initialized: model={model_name}, api_type={api_type}")

    async def analyze_news(self, news_item: NewsItem) -> Optional[NewsAnalysis]:
        """Analyze a single news item for market impact."""
        start_time = get_current_time()

        async with self.semaphore:
            try:
                logger.info(f"🤖 Analyzing: {news_item.title[:50]}...")

                prompt = self._build_prompt(news_item)
                response = await self._call_llm(prompt)
                analysis = self._parse_response(news_item, response)

                processing_time = (get_current_time() - start_time).total_seconds() * 1000
                analysis.processing_time_ms = processing_time

                self.stats["analyses_completed"] += 1
                self.stats["total_processing_time_ms"] += int(processing_time)

                stocks_str = f"{len(analysis.affected_stocks)} stocks" if analysis.affected_stocks else "no stocks"
                logger.info(
                    f"✅ {news_item.title[:40]}... → "
                    f"{analysis.impact_level.value}/{analysis.sentiment.value}/{stocks_str} ({processing_time:.0f}ms)"
                )

                return analysis

            except Exception as e:
                self.stats["analyses_failed"] += 1
                logger.error(f"Analysis failed for {news_item.news_id[:8]}: {e}")
                try:
                    return self._fallback_analysis(news_item, str(e))
                except Exception:
                    return None

    async def analyze_batch(self, news_items: List[NewsItem]) -> List[NewsAnalysis]:
        """Analyze multiple news items in parallel."""
        if not news_items:
            return []

        logger.info(f"Batch analysis: {len(news_items)} items")
        tasks = [self.analyze_news(item) for item in news_items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        analyses = [r for r in results if isinstance(r, NewsAnalysis)]
        logger.info(f"Batch complete: {len(analyses)}/{len(news_items)} successful")
        return analyses

    def _build_prompt(self, news_item: NewsItem) -> str:
        """Build the analysis prompt."""
        content = news_item.description
        if news_item.raw_content:
            content = news_item.raw_content[:3000]

        return f"""You are a financial analyst for Indian stock markets (NSE/BSE).
Analyze this news and provide a JSON assessment of market impact.

TITLE: {news_item.title}
CONTENT: {content}
SOURCE: {news_item.source_feed}
DATE: {news_item.published_date.strftime('%Y-%m-%d %H:%M IST')}

Respond with ONLY this JSON format:
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
    "analysis_summary": "Brief summary",
    "key_points": ["point1", "point2"]
}}

RULES:
- Extract company names from title AND content
- Use UPPERCASE NSE symbols (HDFCBANK, TCS, RELIANCE)
- Only include stocks explicitly mentioned
- Be conservative with impact_level
- expected_move_pct: typically 0.5% to 3%"""

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM API."""
        if self.rate_limit_delay > 0:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - elapsed)
            self.last_request_time = time.time()

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            if self.api_type == "ollama":
                return await self._call_ollama(session, prompt)
            else:
                return await self._call_openai(session, prompt)

    async def _call_ollama(self, session: aiohttp.ClientSession, prompt: str) -> str:
        """Call Ollama API."""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": self.temperature, "top_p": 0.9},
        }

        async with session.post(f"{self.base_url}/api/generate", json=payload) as resp:
            if resp.status != 200:
                raise Exception(f"Ollama error {resp.status}: {await resp.text()}")
            result = await resp.json()
            return result.get("response", "")

    async def _call_openai(self, session: aiohttp.ClientSession, prompt: str) -> str:
        """Call OpenAI-compatible API."""
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a financial analyst. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            if "azure.com" in self.base_url:
                headers["api-key"] = self.api_key
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"

        endpoint = f"{self.base_url}/openai/v1/chat/completions" if "azure.com" in self.base_url else f"{self.base_url}/v1/chat/completions"

        async with session.post(endpoint, json=payload, headers=headers) as resp:
            if resp.status != 200:
                raise Exception(f"API error {resp.status}: {await resp.text()}")
            result = await resp.json()
            return result["choices"][0]["message"]["content"]

    def _parse_response(self, news_item: NewsItem, response: str) -> NewsAnalysis:
        """Parse LLM response into NewsAnalysis."""
        try:
            # Clean markdown formatting
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            data = json.loads(response.strip())

            impact_level = NewsImpactLevel(data.get("impact_level", "neutral").lower())
            sentiment = NewsSentiment(data.get("sentiment", "neutral").lower())

            affected_stocks = [s.upper().strip() for s in data.get("affected_stocks", [])]
            affected_stocks = [s for s in affected_stocks if s and len(s) <= 20]
            affected_stocks = self._validate_stocks(news_item, affected_stocks)

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
                processing_time_ms=0,
            )

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Parse failed, using fallback: {e}")
            self.stats["fallback_used"] += 1
            return self._fallback_analysis(news_item, str(e))

    def _fallback_analysis(self, news_item: NewsItem, error: str = "") -> NewsAnalysis:
        """Keyword-based fallback when LLM fails."""
        self.stats["fallback_used"] += 1
        text = f"{news_item.title} {news_item.description}".lower()

        # Extract industries
        industries = [ind for ind, kws in INDUSTRY_KEYWORDS.items() if any(kw in text for kw in kws)]

        # Extract stocks
        stocks = []
        for symbol, keywords in MAJOR_STOCKS.items():
            for kw in keywords:
                if f" {kw.lower()} " in f" {text} ":
                    stocks.append(symbol)
                    break

        # Extract indices
        indices = [idx for idx, kws in INDEX_KEYWORDS.items() if any(kw in text for kw in kws)]

        # Sentiment detection
        bullish = ["growth", "profit", "surge", "rally", "gain", "rise", "positive", "beat", "strong"]
        bearish = ["fall", "drop", "loss", "decline", "down", "negative", "miss", "weak", "crash"]
        b_count = sum(1 for w in bullish if w in text)
        s_count = sum(1 for w in bearish if w in text)

        if b_count > s_count + 1:
            sentiment = NewsSentiment.BULLISH
            direction = "UP"
        elif s_count > b_count + 1:
            sentiment = NewsSentiment.BEARISH
            direction = "DOWN"
        else:
            sentiment = NewsSentiment.NEUTRAL
            direction = "SIDEWAYS"

        return NewsAnalysis(
            news_id=news_item.news_id,
            impact_level=NewsImpactLevel.LOW,
            sentiment=sentiment,
            confidence_score=0.3,
            affected_industries=industries[:3],
            affected_stocks=stocks[:5],
            affected_indices=indices[:2],
            expected_direction=direction,
            expected_move_pct=0.5 if stocks else 0.0,
            time_horizon="intraday",
            analysis_summary=f"Keyword analysis (LLM error: {error[:30]})",
            key_points=["Keyword-based analysis", "Low confidence"],
            model_used=f"{self.model_name} (fallback)",
            analysis_timestamp=get_current_time(),
            processing_time_ms=0,
        )

    def _validate_stocks(self, news_item: NewsItem, stocks: List[str]) -> List[str]:
        """Validate stocks are mentioned in news text."""
        if not stocks:
            return []

        text = f"{news_item.title} {news_item.description}".lower()
        validated = []

        for symbol in stocks:
            if symbol not in MAJOR_STOCKS:
                continue
            for kw in MAJOR_STOCKS[symbol]:
                if f" {kw.lower()} " in f" {text} ":
                    validated.append(symbol)
                    break

        return validated

    async def check_health(self) -> bool:
        """Check if LLM server is healthy."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                if self.api_type == "ollama":
                    async with session.get(f"{self.base_url}/api/tags") as resp:
                        return resp.status == 200
                else:
                    async with session.get(f"{self.base_url}/v1/models") as resp:
                        return resp.status == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def list_models(self) -> List[str]:
        """List available models."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                if self.api_type == "ollama":
                    async with session.get(f"{self.base_url}/api/tags") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return [m["name"] for m in data.get("models", [])]
                return []
        except Exception as e:
            logger.warning(f"List models failed: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        stats = dict(self.stats)
        if stats["analyses_completed"] > 0:
            stats["avg_processing_time_ms"] = stats["total_processing_time_ms"] / stats["analyses_completed"]
        else:
            stats["avg_processing_time_ms"] = 0
        return stats

    def reset_stats(self):
        """Reset statistics."""
        self.stats = Counter({
            "analyses_completed": 0,
            "analyses_failed": 0,
            "fallback_used": 0,
            "total_processing_time_ms": 0,
        })


# Backward compatibility alias
LlamaAnalyzer = NewsAnalyzer
