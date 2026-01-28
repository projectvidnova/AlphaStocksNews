# Azure AI Foundry Setup Guide

The AlphaStocks News Agent now uses **Azure AI Foundry** with the **DeepSeek-V3.2** model for news analysis.

## Configuration

### Azure Endpoint Details
- **Base URL**: `https://adithyasaisaladi-1060-resource.services.ai.azure.com`
- **Full API Endpoint**: `https://adithyasaisaladi-1060-resource.services.ai.azure.com/models/chat/completions?api-version=2024-05-01-preview`
- **Model Name**: `DeepSeek-V3.2`
- **Deployment Name**: `DeepSeek-V3.2`
- **API Version**: `2024-05-01-preview`
- **Authentication**: Uses `api-key` header (not `Authorization: Bearer`)

**Note**: The code automatically constructs the full endpoint URL from the base URL and uses the correct authentication header format for Azure.

### Setting Up API Key

#### Option 1: Environment Variable (Recommended)
```bash
# Set temporarily (for current session)
export AZURE_API_KEY="your-api-key-here"

# Or add to your shell profile (~/.bashrc, ~/.zshrc, etc.)
echo 'export AZURE_API_KEY="your-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

#### Option 2: Add to .env.dev file
```bash
# Add this line to your .env.dev file
echo 'AZURE_API_KEY=your-api-key-here' >> .env.dev
```

Then update `run_news_agent.py` to load from dotenv:
```python
from dotenv import load_dotenv
load_dotenv('.env.dev')
```

#### Option 3: Direct Configuration (Not Recommended for Production)
Edit `config/news_agent.json` and set:
```json
{
    "llama": {
        "api_key": "your-api-key-here"
    }
}
```

**⚠️ Warning**: Never commit API keys to version control!

## Running the News Agent

Once the API key is configured:

```bash
# Run the news agent
python run_news_agent.py
```

## Configuration Files Updated

1. **`config/news_agent.json`** - Base configuration with Azure endpoint
2. **`run_news_agent.py`** - Script configuration with environment variable support
3. **`src/news/llama_analyzer.py`** - Updated to support Azure AI Foundry API authentication

## Testing the Configuration

```python
# Quick test to verify Azure connection
import asyncio
import os
from src.news.llama_analyzer import LlamaAnalyzer

async def test():
    analyzer = LlamaAnalyzer(
        base_url="https://adithyasaisaladi-1060-resource.services.ai.azure.com",
        model_name="DeepSeek-V3.2",
        api_type="openai",
        api_key=os.getenv("AZURE_API_KEY")
    )
    
    # Test simple prompt
    response = await analyzer._call_llm(
        "Return JSON: {\"status\": \"ok\", \"message\": \"test\"}"
    )
    print(response)

asyncio.run(test())
```

## Switching Back to Ollama (Local)

To switch back to local Ollama:

1. Update `config/news_agent.json`:
```json
{
    "llama": {
        "base_url": "http://localhost:11434",
        "model_name": "gemma3:4b",
        "api_type": "ollama",
        "api_key": null
    }
}
```

2. Or modify `run_news_agent.py` to use local config:
```python
config["llama"]["base_url"] = "http://localhost:11434"
config["llama"]["model_name"] = "gemma3:4b"
config["llama"]["api_type"] = "ollama"
config["llama"]["api_key"] = None
```

## Troubleshooting

### Error: "401 Unauthorized"
- Check that `AZURE_API_KEY` is set correctly
- Verify the API key is valid in Azure portal

### Error: "404 Not Found"
- Verify the endpoint URL is correct
- Check that the model deployment exists in Azure

### Error: "Timeout"
- Increase `timeout_seconds` in config:
```json
{
    "llama": {
        "timeout_seconds": 120
    }
}
```

### Error: "Model not found"
- Verify `model_name` matches your Azure deployment name
- Check model availability in Azure AI Foundry portal

## Additional Resources

- [Azure AI Foundry Documentation](https://learn.microsoft.com/en-us/azure/ai-studio/)
- [DeepSeek Model Information](https://www.deepseek.com/)
- [OpenAI API Compatibility](https://platform.openai.com/docs/api-reference)
